import os
import sqlite3
import json
import time
from typing import Dict, Any, Optional, List
from BlurDetector import BlurResult, FaceBlurDetail

class HashCacheManager:
    """知覚ハッシュ(dHash)、EXIF撮影日時、ピントスコアをSQLiteに永続保存するマネージャー"""

    _instance = None

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(HashCacheManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return

        if not db_path:
            cache_dir = os.path.expanduser("~/.cache/PhotoIsOutOfFocus")
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, "image_cache.db")

        self.db_path = db_path
        self._init_db()
        self._initialized = True

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_cache (
                    file_path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL,
                    dhash TEXT,
                    exif_timestamp REAL,
                    composite_score REAL,
                    blur_result_json TEXT,
                    updated_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_path_mtime ON image_cache(file_path, mtime)")
            conn.commit()

    def get_cached_item(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        指定されたファイルのキャッシュデータを取得。
        ファイルのmtimeおよびsizeが変更されている場合は None を返す。
        """
        if not os.path.exists(file_path):
            return None

        try:
            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size
        except Exception:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM image_cache WHERE file_path = ?",
                (os.path.abspath(file_path),)
            )
            row = cursor.fetchone()

            if row:
                # mtime と size が一致しているかチェック
                if abs(row["mtime"] - current_mtime) < 0.001 and row["size"] == current_size:
                    blur_result = None
                    if row["blur_result_json"]:
                        try:
                            d = json.loads(row["blur_result_json"])
                            faces = [
                                FaceBlurDetail(
                                    face_index=f["face_index"],
                                    box=tuple(f["box"]),
                                    score=f["score"],
                                    is_blurry=f["is_blurry"],
                                    status_text=f["status_text"]
                                )
                                for f in d.get("faces", [])
                            ]
                            blur_result = BlurResult(
                                image_path=d["image_path"],
                                is_blurry=d["is_blurry"],
                                overall_score=d["overall_score"],
                                max_grid_score=d["max_grid_score"],
                                top_k_score=d["top_k_score"],
                                face_detected=d["face_detected"],
                                face_count=d["face_count"],
                                faces=faces,
                                threshold=d["threshold"],
                                reason_text=d["reason_text"]
                            )
                        except Exception as e:
                            print(f"Error parsing cached blur_result: {e}")

                    # dhash 安全な int 変換 (str / float / int 対応)
                    dhash_val = row["dhash"]
                    if dhash_val is not None:
                        try:
                            if isinstance(dhash_val, str):
                                dhash_val = int(dhash_val, 16) if len(dhash_val) == 16 else int(float(dhash_val))
                            elif isinstance(dhash_val, float):
                                dhash_val = int(dhash_val)
                            elif isinstance(dhash_val, int):
                                if dhash_val < 0:
                                    dhash_val += (1 << 64)
                        except Exception:
                            dhash_val = None

                    return {
                        "file_path": row["file_path"],
                        "dhash": dhash_val,
                        "exif_timestamp": row["exif_timestamp"],
                        "composite_score": row["composite_score"],
                        "blur_result": blur_result
                    }

        return None

    def save_cached_item(
        self,
        file_path: str,
        dhash: Optional[int] = None,
        exif_timestamp: Optional[float] = None,
        composite_score: Optional[float] = None,
        blur_result: Optional[BlurResult] = None
    ):
        """1件の画像メタデータをキャッシュに保存"""
        if not os.path.exists(file_path):
            return

        try:
            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size
        except Exception:
            return

        abs_path = os.path.abspath(file_path)
        blur_json = None
        if blur_result:
            try:
                blur_json = json.dumps({
                    "image_path": blur_result.image_path,
                    "is_blurry": blur_result.is_blurry,
                    "overall_score": blur_result.overall_score,
                    "max_grid_score": blur_result.max_grid_score,
                    "top_k_score": blur_result.top_k_score,
                    "face_detected": blur_result.face_detected,
                    "face_count": blur_result.face_count,
                    "faces": [
                        {
                            "face_index": f.face_index,
                            "box": list(f.box),
                            "score": f.score,
                            "is_blurry": f.is_blurry,
                            "status_text": f.status_text
                        }
                        for f in blur_result.faces
                    ],
                    "threshold": blur_result.threshold,
                    "reason_text": blur_result.reason_text
                })
            except Exception as e:
                print(f"Error encoding blur_result to json: {e}")

        dhash_str = None
        if dhash is not None:
            try:
                dhash_int = int(dhash)
                dhash_str = f"{dhash_int:016x}"
            except Exception:
                dhash_str = None

        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO image_cache 
                (file_path, mtime, size, dhash, exif_timestamp, composite_score, blur_result_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    mtime = excluded.mtime,
                    size = excluded.size,
                    dhash = COALESCE(excluded.dhash, dhash),
                    exif_timestamp = COALESCE(excluded.exif_timestamp, exif_timestamp),
                    composite_score = COALESCE(excluded.composite_score, composite_score),
                    blur_result_json = COALESCE(excluded.blur_result_json, blur_result_json),
                    updated_at = excluded.updated_at
            """, (abs_path, current_mtime, current_size, dhash_str, exif_timestamp, composite_score, blur_json, now))
            conn.commit()

    def bulk_get_cached_items(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """複数ファイルのキャッシュをまとめて一括取得"""
        results = {}
        for path in file_paths:
            cached = self.get_cached_item(path)
            if cached:
                results[os.path.abspath(path)] = cached
        return results
