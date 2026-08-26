import os
import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from PIL import Image, ExifTags
from BlurDetector import BlurDetector, BlurResult
from HashCacheManager import HashCacheManager

@dataclass
class BurstPhotoItem:
    """連続写真グループ内の個々の画像情報"""
    image_path: str
    timestamp: float  # Unixエポック秒（サブ秒含む）
    timestamp_str: str
    blur_result: Optional[BlurResult] = None
    composite_score: float = 0.0
    is_recommended_keep: bool = False
    marked_for_deletion: bool = False

@dataclass
class BurstGroup:
    """連続写真グループ"""
    group_id: int
    items: List[BurstPhotoItem] = field(default_factory=list)

    @property
    def start_time_str(self) -> str:
        if not self.items:
            return ""
        return self.items[0].timestamp_str

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def deletion_count(self) -> int:
        return sum(1 for item in self.items if item.marked_for_deletion)

    @property
    def keep_count(self) -> int:
        return sum(1 for item in self.items if not item.marked_for_deletion)

    def recommend_best_photo(self):
        """グループ内で最もスコアの高い画像を推奨保持に選定する"""
        if not self.items:
            return

        best_item = max(self.items, key=lambda x: x.composite_score)
        
        for item in self.items:
            if item == best_item:
                item.is_recommended_keep = True
                item.marked_for_deletion = False
            else:
                item.is_recommended_keep = False
                item.marked_for_deletion = True

def extract_image_timestamp(image_path: str) -> float:
    """
    画像の撮影日時 (EXIF DateTimeOriginal / DateTimeDigitized / DateTime + SubSecTimeOriginal) を抽出する。
    EXIF撮影日時が存在しない場合は、ファイルの更新日時 (mtime) を代わりに使用する。
    """
    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if exif:
                tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
                
                dt_str = tag_map.get('DateTimeOriginal') or tag_map.get('DateTimeDigitized') or tag_map.get('DateTime')
                subsec_str = tag_map.get('SubSecTimeOriginal') or tag_map.get('SubSecTime') or '0'
                
                if dt_str and isinstance(dt_str, str):
                    try:
                        dt = datetime.datetime.strptime(dt_str.strip(), "%Y:%m:%d %H:%M:%S")
                        
                        subsec = 0.0
                        if subsec_str and isinstance(subsec_str, (str, int, float)):
                            try:
                                subsec = float(f"0.{str(subsec_str).strip()}")
                            except ValueError:
                                subsec = 0.0
                                
                        return dt.timestamp() + subsec
                    except Exception:
                        pass
    except Exception:
        pass

    try:
        return os.path.getmtime(image_path)
    except Exception:
        return 0.0

def calculate_composite_focus_score(result: BlurResult) -> float:
    """
    BlurResult から総合評価スコアを算出する。
    """
    if not result:
        return 0.0

    if result.face_detected and result.faces:
        max_face_score = max(f.score for f in result.faces)
        return max(max_face_score, result.max_grid_score)
    else:
        return max(result.max_grid_score * 0.7 + result.top_k_score * 0.3, result.overall_score)

class BurstPhotoDetector:
    """連続写真のグループ化とフォーカス評価を行うクラス (SQLiteキャッシュ連携)"""

    def __init__(self, time_threshold_seconds: float = 3.0, blur_threshold: float = 100.0):
        self.time_threshold_seconds = time_threshold_seconds
        self.blur_threshold = blur_threshold
        self.blur_detector = BlurDetector(threshold=blur_threshold)
        self.cache_mgr = HashCacheManager()

    def find_burst_groups(
        self,
        image_paths: List[str],
        is_cancelled_func: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[BurstGroup]:
        """
        画像ファイルリストから撮影日時の近い連続写真をグループ化し、
        ピントスコア判定を行ってバーストグループ一覧を返す。
        （SQLite永続キャッシュに対応）
        """
        if not image_paths:
            return []

        total_files = len(image_paths)
        raw_items: List[BurstPhotoItem] = []

        # 1. 各画像のタイムスタンプを抽出（キャッシュ優先 -> EXIF -> mtime）
        for idx, path in enumerate(image_paths):
            if is_cancelled_func and is_cancelled_func():
                return []

            cached = self.cache_mgr.get_cached_item(path)
            ts = None
            if cached and cached.get("exif_timestamp") is not None:
                ts = cached["exif_timestamp"]
                if progress_callback:
                    progress_callback(idx + 1, total_files, f"⚡ キャッシュ利用 (撮影日時): {os.path.basename(path)}")
            else:
                if progress_callback:
                    progress_callback(idx + 1, total_files, f"タイムスタンプ解析中: {os.path.basename(path)}")
                ts = extract_image_timestamp(path)
                self.cache_mgr.save_cached_item(path, exif_timestamp=ts)

            dt_formatted = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            raw_items.append(BurstPhotoItem(image_path=path, timestamp=ts, timestamp_str=dt_formatted))

        raw_items.sort(key=lambda x: x.timestamp)

        # 2. 連続撮影時間差 (time_threshold_seconds) に基づいてグループ化
        burst_clusters: List[List[BurstPhotoItem]] = []
        current_cluster: List[BurstPhotoItem] = []

        for item in raw_items:
            if not current_cluster:
                current_cluster.append(item)
            else:
                prev_item = current_cluster[-1]
                time_diff = abs(item.timestamp - prev_item.timestamp)
                if time_diff <= self.time_threshold_seconds:
                    current_cluster.append(item)
                else:
                    if len(current_cluster) >= 2:
                        burst_clusters.append(current_cluster)
                    current_cluster = [item]

        if len(current_cluster) >= 2:
            burst_clusters.append(current_cluster)

        # 3. 各グループ内の画像に対してピント評価を実行 (キャッシュ優先)
        result_groups: List[BurstGroup] = []
        processed_count = 0
        total_burst_items = sum(len(c) for c in burst_clusters)

        for g_idx, cluster in enumerate(burst_clusters):
            if is_cancelled_func and is_cancelled_func():
                return []

            group = BurstGroup(group_id=g_idx + 1, items=cluster)

            for item in cluster:
                if is_cancelled_func and is_cancelled_func():
                    return []
                
                processed_count += 1
                cached = self.cache_mgr.get_cached_item(item.image_path)

                if cached and cached.get("blur_result") is not None and cached.get("composite_score") is not None:
                    item.blur_result = cached["blur_result"]
                    item.composite_score = cached["composite_score"]
                    if progress_callback:
                        progress_callback(
                            processed_count, total_burst_items,
                            f"⚡ キャッシュ利用 (ピントスコア): {os.path.basename(item.image_path)}"
                        )
                else:
                    if progress_callback:
                        progress_callback(
                            processed_count, total_burst_items,
                            f"ピント解析中 ({g_idx + 1}/{len(burst_clusters)}グループ): {os.path.basename(item.image_path)}"
                        )

                    try:
                        blur_res = self.blur_detector.detect_blur(item.image_path, threshold=self.blur_threshold)
                        item.blur_result = blur_res
                        item.composite_score = round(calculate_composite_focus_score(blur_res), 2)
                        self.cache_mgr.save_cached_item(
                            item.image_path,
                            composite_score=item.composite_score,
                            blur_result=blur_res
                        )
                    except Exception as e:
                        print(f"Blur detection error for {item.image_path}: {e}")
                        item.composite_score = 0.0

            group.recommend_best_photo()
            result_groups.append(group)

        return result_groups
