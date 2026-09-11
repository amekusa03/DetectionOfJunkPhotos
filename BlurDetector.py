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
from i18n import t

@dataclass
class FaceBlurDetail:
    face_index: int
    box: Tuple[int, int, int, int]  # (x, y, w, h)
    score: float
    is_blurry: bool
    status_text: str = ""

    def __post_init__(self):
        if not self.status_text:
            self.status_text = t("status.blurry") if self.is_blurry else t("status.sharp")

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
        return t("status.blurry") if self.is_blurry else t("status.sharp")

    def summary(self) -> str:
        if self.face_detected:
            faces_str = ", ".join([f"Face {f.face_index}: {f.score:.1f}({f.status_text})" for f in self.faces])
            return f"{self.status_text} | Faces: {self.face_count} ({faces_str})"
        else:
            return f"{self.status_text} (Avg: {self.overall_score:.1f}, Max: {self.max_grid_score:.1f})"

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
        """
        self.threshold = threshold
        self.target_face_size = target_face_size
        self.target_full_size = target_full_size
        self.grid_shape = grid_shape
        
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        else:
            print(f"Warning: Haar cascade file not found at {cascade_path}")
            self.face_cascade = None

    def _eval_grid_sharpness(self, gray_image: np.ndarray) -> Tuple[float, float, List[float]]:
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
        
        top_k = max(1, len(scores) // 5)
        top_k_avg = float(np.mean(scores[:top_k])) if scores else 0.0

        return max_score, top_k_avg, scores

    def detect_blur(
        self,
        image_input: Union[str, np.ndarray],
        threshold: Optional[float] = None
    ) -> BlurResult:
        effective_threshold = threshold if threshold is not None else self.threshold
        image_path = ""

        if isinstance(image_input, str):
            image_path = image_input
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
        elif isinstance(image_input, np.ndarray):
            image = image_input
        else:
            raise TypeError("image_input must be file path (str) or np.ndarray")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        faces = []
        if self.face_cascade is not None and not self.face_cascade.empty():
            try:
                faces = self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
            except Exception as e:
                print(f"Warning: face detection failed ({e}). Falling back to full image detection.")
                faces = []

        max_grid_score, top_k_score, _ = self._eval_grid_sharpness(gray)
        resized_full = cv2.resize(gray, self.target_full_size)
        overall_score = float(cv2.Laplacian(resized_full, cv2.CV_64F).var())

        if len(faces) == 0:
            is_blurry = True
            reason = ""

            if max_grid_score >= effective_threshold or top_k_score >= effective_threshold:
                is_blurry = False
                reason = t("reason.sharp_subject")
            elif overall_score >= effective_threshold:
                is_blurry = False
                reason = t("reason.uniform_sharp")
            else:
                is_blurry = True
                reason = t("reason.overall_blurry")

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
                status_text=t("status.blurry") if is_face_blurry else t("status.sharp")
            ))

        mean_face_score = float(np.mean(scores)) if scores else 0.0
        
        if max_face_score >= effective_threshold or mean_face_score >= effective_threshold:
            is_blurry = False
            reason = t("reason.face_focused")
        else:
            if max_grid_score >= effective_threshold * 1.2:
                is_blurry = False
                reason = t("reason.face_soft_fallback")
            else:
                is_blurry = True
                reason = t("reason.face_blurry")

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
            print(f"=== [{target_path}] ===")
            print(f"Status: {result.status_text}")
            print(f"Reason: {result.reason_text}")
            print(f"Overall Score: {result.overall_score}")
            print(f"Max Grid Score: {result.max_grid_score}")
            print(f"Top 20% Score: {result.top_k_score}")
            print(f"Faces Detected: {result.face_detected}")
            print(f"Face Count: {result.face_count}")
            if result.faces:
                for f in result.faces:
                    print(f"  - Face {f.face_index}: Score={f.score} ({f.status_text}) Box={f.box}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python BlurDetector.py <image_path> [threshold]")
