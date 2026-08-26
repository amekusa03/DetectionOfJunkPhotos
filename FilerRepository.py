import os
import shutil
import subprocess
from BaseNodeObject import BaseNodeObject, DirectoryNodeObject, ImageNodeObject
from BlurDetector import BlurDetector, BlurResult
from BurstPhotoManager import BurstPhotoDetector, BurstGroup
from SimilarPhotoManager import SimilarPhotoDetector, SimilarGroup

class FilerRepository:
    """ローカルのファイルシステムからノード（オブジェクト）を取得し、操作するラッパー"""
    
    def get_directory_node(self, dir_path: str) -> DirectoryNodeObject:
        """指定されたパスのディレクトリノードを作成し、中身のノード群を詰めて返す"""
        dir_node = DirectoryNodeObject(dir_path)
        
        if not os.path.isdir(dir_path):
            return dir_node

        try:
            for entry in os.scandir(dir_path):
                dir_node.children.append(BaseNodeObject.create(entry.path))
        except PermissionError:
            pass # アクセス権限がない場合は空のまま返す
            
        return dir_node

    def create_directory(self, parent_path: str, name: str) -> bool:
        """指定された親ディレクトリ配下に新しいディレクトリを作成する"""
        target_path = os.path.join(parent_path, name)
        try:
            os.makedirs(target_path, exist_ok=False)
            return True
        except Exception:
            return False

    def create_file(self, parent_path: str, name: str) -> bool:
        """指定された親ディレクトリ配下に新しい空ファイルを作成する"""
        target_path = os.path.join(parent_path, name)
        try:
            with open(target_path, 'x'):
                pass
            return True
        except Exception:
            return False

    def rename_node(self, node_path: str, new_name: str) -> bool:
        """ノードの名前を変更する"""
        if not os.path.exists(node_path):
            return False
        parent_dir = os.path.dirname(node_path)
        new_path = os.path.join(parent_dir, new_name)
        try:
            os.rename(node_path, new_path)
            return True
        except Exception:
            return False

    def delete_node(self, node_path: str) -> bool:
        """ノード（ファイルまたはディレクトリ）を物理削除する"""
        if not os.path.exists(node_path):
            return False
        try:
            if os.path.isdir(node_path):
                shutil.rmtree(node_path)
            else:
                os.remove(node_path)
            return True
        except Exception:
            return False

    def send_to_trash(self, node_path: str) -> bool:
        """ノード（ファイルまたはディレクトリ）をごみ箱に移動する"""
        if not os.path.exists(node_path):
            return False
        
        # 1. send2trash ライブラリを試行
        try:
            import send2trash
            send2trash.send2trash(node_path)
            return True
        except Exception as e:
            print(f"send2trash warning for {node_path}: {e}")

        # 2. Linux gio trash フォールバック
        try:
            res = subprocess.run(["gio", "trash", node_path], check=True, capture_output=True)
            if res.returncode == 0:
                return True
        except Exception as e:
            print(f"gio trash warning for {node_path}: {e}")

        return False

    def search_blurry_images(
        self,
        dir_path: str,
        recursive: bool = True,
        threshold: float = 100.0,
        is_cancelled_func = None,
        progress_callback = None,
        found_callback = None
    ):
        """
        指定されたディレクトリ配下の画像ファイルを探索し、ピンぼけ判定された画像のBlurResultリストを返す
        """
        if not os.path.isdir(dir_path):
            return []

        image_files = []
        if recursive:
            for root, _, files in os.walk(dir_path):
                if is_cancelled_func and is_cancelled_func():
                    return []
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                        image_files.append(os.path.join(root, file))
        else:
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                            image_files.append(entry.path)
            except Exception:
                pass

        total_files = len(image_files)
        detector = BlurDetector(threshold=threshold)
        blurry_results = []

        for idx, img_path in enumerate(image_files):
            if is_cancelled_func and is_cancelled_func():
                break

            if progress_callback:
                progress_callback(idx + 1, total_files, img_path)

            try:
                result = detector.detect_blur(img_path, threshold=threshold)
                if result and result.is_blurry:
                    blurry_results.append(result)
                    if found_callback:
                        found_callback(result)
            except Exception as e:
                print(f'Error detecting blur for {img_path}: {e}')

        return blurry_results

    def search_burst_photo_groups(
        self,
        dir_path: str,
        recursive: bool = True,
        time_threshold: float = 3.0,
        blur_threshold: float = 100.0,
        is_cancelled_func = None,
        progress_callback = None
    ) -> list[BurstGroup]:
        """
        指定されたディレクトリ配下から連続写真グループを抽出・ピント評価して返す
        """
        if not os.path.isdir(dir_path):
            return []

        image_files = []
        if recursive:
            for root, _, files in os.walk(dir_path):
                if is_cancelled_func and is_cancelled_func():
                    return []
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                        image_files.append(os.path.join(root, file))
        else:
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                            image_files.append(entry.path)
            except Exception:
                pass

        if not image_files:
            return []

        detector = BurstPhotoDetector(time_threshold_seconds=time_threshold, blur_threshold=blur_threshold)
        return detector.find_burst_groups(
            image_paths=image_files,
            is_cancelled_func=is_cancelled_func,
            progress_callback=progress_callback
        )

    def search_similar_photo_groups(
        self,
        dir_path: str,
        recursive: bool = True,
        max_hash_distance: int = 10,
        blur_threshold: float = 100.0,
        is_cancelled_func = None,
        progress_callback = None
    ) -> list[SimilarGroup]:
        """
        指定されたディレクトリ配下から見た目の類似する画像グループを抽出・ピント評価して返す
        """
        if not os.path.isdir(dir_path):
            return []

        image_files = []
        if recursive:
            for root, _, files in os.walk(dir_path):
                if is_cancelled_func and is_cancelled_func():
                    return []
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                        image_files.append(os.path.join(root, file))
        else:
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
                            image_files.append(entry.path)
            except Exception:
                pass

        if not image_files:
            return []

        detector = SimilarPhotoDetector(max_hash_distance=max_hash_distance, blur_threshold=blur_threshold)
        return detector.find_similar_groups(
            image_paths=image_files,
            is_cancelled_func=is_cancelled_func,
            progress_callback=progress_callback
        )
