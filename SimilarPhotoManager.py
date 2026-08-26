import os
import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from PIL import Image
from BlurDetector import BlurDetector, BlurResult
from BurstPhotoManager import calculate_composite_focus_score
from HashCacheManager import HashCacheManager

@dataclass
class SimilarPhotoItem:
    """類似写真グループ内の個々の画像情報"""
    image_path: str
    dhash: int
    blur_result: Optional[BlurResult] = None
    composite_score: float = 0.0
    is_recommended_keep: bool = False
    marked_for_deletion: bool = False

@dataclass
class SimilarGroup:
    """類似写真グループ"""
    group_id: int
    items: List[SimilarPhotoItem] = field(default_factory=list)

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


def compute_dhash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """
    画像の dHash (Difference Hash) を算出する (デフォルト64ビット)。
    """
    try:
        with Image.open(image_path) as img:
            gray = img.convert('L').resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
            pixels = list(gray.getdata())

            diff = []
            for row in range(hash_size):
                row_start = row * (hash_size + 1)
                for col in range(hash_size):
                    left = pixels[row_start + col]
                    right = pixels[row_start + col + 1]
                    diff.append(left > right)

            decimal_value = 0
            for bit in diff:
                decimal_value = (decimal_value << 1) | int(bit)

            return decimal_value
    except Exception as e:
        print(f"dHash error for {image_path}: {e}")
        return None

def hamming_distance(hash1: Any, hash2: Any) -> int:
    """2つの64ビット整数のハミング距離（ビット相違数）を計算する (型変換安全版)"""
    try:
        h1 = int(hash1)
        h2 = int(hash2)
        x = h1 ^ h2
        return bin(x).count('1')
    except Exception as e:
        print(f"Error in hamming_distance ({hash1}, {hash2}): {e}")
        return 999


class SimilarPhotoDetector:
    """視覚的類似度（dHash）による画像グループ化とフォーカス評価を行うクラス (SQLiteキャッシュ連携)"""

    def __init__(self, max_hash_distance: int = 10, blur_threshold: float = 100.0):
        self.max_hash_distance = max_hash_distance
        self.blur_threshold = blur_threshold
        self.blur_detector = BlurDetector(threshold=blur_threshold)
        self.cache_mgr = HashCacheManager()

    def find_similar_groups(
        self,
        image_paths: List[str],
        is_cancelled_func: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[SimilarGroup]:
        """
        画像ファイルリストからdHash（知覚ハッシュ）を算出し、
        ハミング距離が一定値以下の類似画像群をクラスタリングしてピント評価を行う。
        （SQLite永続キャッシュに対応）
        """
        if not image_paths:
            return []

        total_files = len(image_paths)
        valid_items: List[SimilarPhotoItem] = []

        # 1. 各画像の dHash を算出 (キャッシュ優先)
        for idx, path in enumerate(image_paths):
            if is_cancelled_func and is_cancelled_func():
                return []

            cached = self.cache_mgr.get_cached_item(path)
            h = None
            if cached and cached.get("dhash") is not None:
                try:
                    h = int(cached["dhash"])
                    if progress_callback:
                        progress_callback(idx + 1, total_files, f"⚡ キャッシュ利用 (dHash): {os.path.basename(path)}")
                except Exception:
                    h = None

            if h is None:
                if progress_callback:
                    progress_callback(idx + 1, total_files, f"知覚ハッシュ(dHash)計算中: {os.path.basename(path)}")
                h_calc = compute_dhash(path)
                if h_calc is not None:
                    h = int(h_calc)
                    self.cache_mgr.save_cached_item(path, dhash=h)

            if h is not None:
                valid_items.append(SimilarPhotoItem(image_path=path, dhash=int(h)))

        if not valid_items:
            return []

        # 2. ハミング距離によるグラフクラスタリング
        n = len(valid_items)
        parent = list(range(n))

        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        for i in range(n):
            if is_cancelled_func and is_cancelled_func():
                return []
            for j in range(i + 1, n):
                dist = hamming_distance(valid_items[i].dhash, valid_items[j].dhash)
                if dist <= self.max_hash_distance:
                    union(i, j)

        clusters_dict: Dict[int, List[SimilarPhotoItem]] = {}
        for i in range(n):
            root = find(i)
            if root not in clusters_dict:
                clusters_dict[root] = []
            clusters_dict[root].append(valid_items[i])

        similar_clusters = [c for c in clusters_dict.values() if len(c) >= 2]

        # 3. 各類似グループのピント評価 (キャッシュ優先)
        result_groups: List[SimilarGroup] = []
        processed_count = 0
        total_cluster_items = sum(len(c) for c in similar_clusters)

        for g_idx, cluster in enumerate(similar_clusters):
            if is_cancelled_func and is_cancelled_func():
                return []

            group = SimilarGroup(group_id=g_idx + 1, items=cluster)

            for item in cluster:
                if is_cancelled_func and is_cancelled_func():
                    return []

                processed_count += 1
                cached = self.cache_mgr.get_cached_item(item.image_path)
                
                if cached and cached.get("blur_result") is not None and cached.get("composite_score") is not None:
                    item.blur_result = cached["blur_result"]
                    item.composite_score = float(cached["composite_score"])
                    if progress_callback:
                        progress_callback(
                            processed_count, total_cluster_items,
                            f"⚡ キャッシュ利用 (ピントスコア): {os.path.basename(item.image_path)}"
                        )
                else:
                    if progress_callback:
                        progress_callback(
                            processed_count, total_cluster_items,
                            f"ピント解析中 ({g_idx + 1}/{len(similar_clusters)}グループ): {os.path.basename(item.image_path)}"
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
