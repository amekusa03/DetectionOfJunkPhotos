"""
BlurDetector.py

ピンぼけ（ボケ）画像検出モジュール
OpenCVのラプラシアンフィルタ分散法、グリッド領域解析、および顔検出を用いて
画像または検出された顔領域の鮮鋭度（フォーカス度）を測定します。
背景ボケ（被写界深度が浅い写真）による誤判定を自動防止する機能を備えています。
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Union

@dataclass
class FaceBlurDetail:
    face_index: int
    box: Tuple[int, int, int, int]  # (x, y, w, h)
    score: float
    is_blurry: bool
    status_text: str

@dataclass
class BlurResult:
    image_path: str
    is_blurry: bool
    overall_score: float
    max_grid_score: float = 0.0
    top_k_score: float = 0.0
    face_detected: bool = False
    face_count: int = 0
    faces: List[FaceBlurDetail] = field(default_factory=list)
    threshold: float = 100.0
    reason_text: str = ""

    @property
    def status_text(self) -> str:
        return "ピンぼけ" if self.is_blurry else "鮮明"

    def summary(self) -> str:
        if self.face_detected:
            faces_str = ", ".join([f"顔{f.face_index}: {f.score:.1f}({f.status_text})" for f in self.faces])
            return f"総合判定: {self.status_text} | 検出顔数: {self.face_count} ({faces_str})"
        else:
            return f"総合判定: {self.status_text} (全体平均: {self.overall_score:.1f}, 最大領域: {self.max_grid_score:.1f})"

class BlurDetector:
    def __init__(
        self,
        threshold: float = 100.0,
        target_face_size: Tuple[int, int] = (200, 200),
        target_full_size: Tuple[int, int] = (500, 500),
        grid_shape: Tuple[int, int] = (5, 5)
    ):
        """
        ピンぼけ検出器の初期化
        
        Args:
            threshold (float): 鮮鋭度スコアの閾値（これ未満ならピンぼけ）
            target_face_size (Tuple[int, int]): 顔領域を評価する際の規格化サイズ (w, h)
            target_full_size (Tuple[int, int]): 画像全体を評価する際の規格化サイズ (w, h)
            grid_shape (Tuple[int, int]): グリッド分割の縦横数 (rows, cols)
        """
        self.threshold = threshold
        self.target_face_size = target_face_size
        self.target_full_size = target_full_size
        self.grid_shape = grid_shape

        # CascadeClassifierの互換性取得
        self.face_cascade = None
        cascade_cls = getattr(cv2, 'CascadeClassifier', None)
        if cascade_cls is None:
            try:
                from cv2 import objdetect
                cascade_cls = getattr(objdetect, 'CascadeClassifier', None)
            except Exception:
                cascade_cls = None

        if cascade_cls is not None:
            try:
                cascade_path = getattr(cv2.data, 'haarcascades', '') + 'haarcascade_frontalface_default.xml'
                if os.path.exists(cascade_path):
                    detector = cascade_cls(cascade_path)
                    if not detector.empty():
                        self.face_cascade = detector
            except Exception as e:
                print(f"Warning: Could not load CascadeClassifier: {e}")
                self.face_cascade = None

    def _eval_grid_sharpness(self, gray_image: np.ndarray) -> Tuple[float, float, List[float]]:
        """
        画像を N x M のグリッドに分割し、各ブロックの鮮鋭度（Laplacian variance）を計算する
        
        Returns:
            Tuple[float, float, List[float]]: (max_grid_score, top_k_avg_score, all_grid_scores)
        """
        resized = cv2.resize(gray_image, self.target_full_size)
        h, w = resized.shape
        rows, cols = self.grid_shape
        bh, bw = h // rows, w // cols

        scores = []
        for r in range(rows):
            for c in range(cols):
                cell = resized[r*bh:(r+1)*bh, c*bw:(c+1)*bw]
                cell_var = float(cv2.Laplacian(cell, cv2.CV_64F).var())
                scores.append(cell_var)

        scores.sort(reverse=True)
        max_score = scores[0] if scores else 0.0
        
        # 上位20%（5x5なら上位5ブロック）の平均値を計算
        top_k = max(1, len(scores) // 5)
        top_k_avg = float(np.mean(scores[:top_k])) if scores else 0.0

        return max_score, top_k_avg, scores

    def detect_blur(
        self,
        image_input: Union[str, np.ndarray],
        threshold: Optional[float] = None
    ) -> BlurResult:
        """
        画像のピンぼけ検出を実行する
        
        Args:
            image_input (Union[str, np.ndarray]): 画像ファイルのパス、またはOpenCV画像配列(BGR)
            threshold (Optional[float]): 固有の閾値を指定（省略時はself.threshold）
            
        Returns:
            BlurResult: ピンぼけ検出結果
        """
        effective_threshold = threshold if threshold is not None else self.threshold
        image_path = ""

        if isinstance(image_input, str):
            image_path = image_input
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"画像を読み込めませんでした（フォーマット非対応）: {image_path}")
        elif isinstance(image_input, np.ndarray):
            image = image_input
        else:
            raise TypeError("image_input はファイルパス(str)または np.ndarray である必要があります")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 顔検出
        faces = []
        if self.face_cascade is not None and not self.face_cascade.empty():
            try:
                faces = self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
            except Exception as e:
                print(f"Warning: face detection failed ({e}). Falling back to full image detection.")
                faces = []

        # 全体 / グリッド領域の鮮鋭度評価
        max_grid_score, top_k_score, _ = self._eval_grid_sharpness(gray)
        resized_full = cv2.resize(gray, self.target_full_size)
        overall_score = float(cv2.Laplacian(resized_full, cv2.CV_64F).var())

        if len(faces) == 0:
            # 顔未検出時：全体平均、グリッド最高値、上位平均を総合判定
            # 背景がボケていても、画面内の主要領域(max_grid_scoreまたはtop_k_score)が閾値を超えていれば鮮明とみなす
            is_blurry = True
            reason = ""

            if max_grid_score >= effective_threshold or top_k_score >= effective_threshold:
                is_blurry = False
                reason = "画面内に十分鮮明な被写体・領域を検出 (背景ボケ考慮)"
            elif overall_score >= effective_threshold:
                is_blurry = False
                reason = "画像全体が均一に鮮明"
            else:
                is_blurry = True
                reason = "画面全体および各領域で鮮鋭度が低下（全体的にピンぼけ）"

            return BlurResult(
                image_path=image_path,
                is_blurry=is_blurry,
                overall_score=round(overall_score, 2),
                max_grid_score=round(max_grid_score, 2),
                top_k_score=round(top_k_score, 2),
                face_detected=False,
                face_count=0,
                faces=[],
                threshold=effective_threshold,
                reason_text=reason
            )

        # 顔検出時
        face_details: List[FaceBlurDetail] = []
        scores = []
        max_face_score = 0.0

        for i, (x, y, w, h) in enumerate(faces):
            face_roi = gray[y:y+h, x:x+w]
            face_resized = cv2.resize(face_roi, self.target_face_size)
            
            score = float(cv2.Laplacian(face_resized, cv2.CV_64F).var())
            is_face_blurry = score < effective_threshold
            
            if score > max_face_score:
                max_face_score = score

            scores.append(score)
            face_details.append(FaceBlurDetail(
                face_index=i + 1,
                box=(int(x), int(y), int(w), int(h)),
                score=round(score, 2),
                is_blurry=is_face_blurry,
                status_text="ピンぼけ" if is_face_blurry else "鮮明"
            ))

        # 顔判定ロジック:
        # メインの顔（最高スコアの顔）が閾値以上、または過半数の顔にピントが合っていれば鮮明と判定
        mean_face_score = float(np.mean(scores)) if scores else 0.0
        
        if max_face_score >= effective_threshold or mean_face_score >= effective_threshold:
            is_blurry = False
            reason = "主要な顔領域にフォーカスが合っています"
        else:
            # 顔領域でのスコアが低くても、背景ではなくグリッド領域全体で明確な主被写体があるかフォールバック確認
            if max_grid_score >= effective_threshold * 1.2:
                is_blurry = False
                reason = "顔領域はややソフトですが画面内に鮮明な焦点領域を検出"
            else:
                is_blurry = True
                reason = "検出された顔領域のフォーカスが甘くボケています"

        return BlurResult(
            image_path=image_path,
            is_blurry=is_blurry,
            overall_score=round(mean_face_score, 2),
            max_grid_score=round(max_grid_score, 2),
            top_k_score=round(top_k_score, 2),
            face_detected=True,
            face_count=len(faces),
            faces=face_details,
            threshold=effective_threshold,
            reason_text=reason
        )

if __name__ == "__main__":
    import sys
    detector = BlurDetector(threshold=100.0)
    
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
        th = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
        try:
            result = detector.detect_blur(target_path, threshold=th)
            print(f"=== ピンぼけ検出結果 [{target_path}] ===")
            print(f"ステータス   : {result.status_text}")
            print(f"判定理由     : {result.reason_text}")
            print(f"全体スコア   : {result.overall_score}")
            print(f"最大領域スコア: {result.max_grid_score}")
            print(f"上位20%スコア: {result.top_k_score}")
            print(f"顔検出あり   : {'はい' if result.face_detected else 'いいえ'}")
            print(f"検出顔数     : {result.face_count}")
            if result.faces:
                for f in result.faces:
                    print(f"  - 顔 {f.face_index}: スコア={f.score} ({f.status_text}) 領域={f.box}")
        except Exception as e:
            print(f"エラー: {e}")
    else:
        print("使用法: python BlurDetector.py <画像ファイルパス> [閾値(デフォルト:100.0)]")
