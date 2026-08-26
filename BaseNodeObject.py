from PySide6.QtCore import QObject, Signal
import os
from typing import Optional

def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 Bytes"
    for unit in ['Bytes', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class BaseNodeObject(QObject):
    """ファイルやディレクトリのベースとなるデータオブジェクト"""
    updated = Signal(object) # 状態が変わったらGUIに通知する信号

    def __init__(self, path: str):
        super().__init__()
        self.path = os.path.abspath(path)
        self.name = os.path.basename(path)
        self._is_selected = False
        self.size = 0

    @property
    def is_selected(self):
        return self._is_selected

    @is_selected.setter
    def is_selected(self, value: bool):
        if self._is_selected != value:
            self._is_selected = value
            self.updated.emit(self) # 選択状態が変わったら再描画を促す

    @property
    def exists(self) -> bool:
        return os.path.exists(self.path)

    @property
    def modified_time(self) -> float:
        try:
            return os.path.getmtime(self.path) if self.exists else 0.0
        except Exception:
            return 0.0

    @property
    def created_time(self) -> float:
        try:
            return os.path.getctime(self.path) if self.exists else 0.0
        except Exception:
            return 0.0

    @property
    def icon(self) -> str:
        return "📄"

    @property
    def type_name(self) -> str:
        return "File"

    @property
    def size_str(self) -> str:
        return "-"

    @property
    def has_preview(self) -> bool:
        return False

    @classmethod
    def create(cls, path: str) -> "BaseNodeObject":
        """パスから適切なサブクラスのインスタンスを生成して返すファクトリメソッド"""
        if os.path.isdir(path):
            return DirectoryNodeObject(path)
        
        ext = os.path.splitext(path)[1].lower()
        if ext in ImageNodeObject.SUPPORTED_EXTENSIONS:
            return ImageNodeObject(path)
        return FileNodeObject(path)


class FileNodeObject(BaseNodeObject):
    """ファイルを表すオブジェクト（サイズや拡張子などの情報を持つ）"""
    def __init__(self, path: str):
        super().__init__(path)
        self.size = os.path.getsize(path) if os.path.exists(path) else 0
        self.extension = os.path.splitext(self.name)[1]

    @property
    def size_str(self) -> str:
        return format_size(self.size)

    @property
    def icon(self) -> str:
        ext = self.extension.lower()
        if ext in ['.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z']:
            return "📦"
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            return "🎵"
        elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
            return "🎥"
        elif ext in ['.py', '.js', '.ts', '.html', '.css', '.cpp', '.c', '.h', '.go', '.rs', '.java', '.sh', '.bat']:
            return "⚙️"
        elif ext in ['.txt', '.md', '.ini', '.cfg', '.json', '.yaml', '.yml', '.xml']:
            return "📄"
        elif ext in ['.pdf']:
            return "📕"
        elif ext in ['.doc', '.docx', '.odt']:
            return "📘"
        elif ext in ['.xls', '.xlsx', '.ods']:
            return "📗"
        else:
            return "📄"

    @property
    def type_name(self) -> str:
        ext = self.extension.lower()
        if ext in ['.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z']:
            return f"{ext[1:].upper()} Archive"
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            return f"{ext[1:].upper()} Audio"
        elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
            return f"{ext[1:].upper()} Video"
        elif ext in ['.py', '.js', '.ts', '.html', '.css', '.cpp', '.c', '.h', '.go', '.rs', '.java', '.sh', '.bat']:
            return f"{ext[1:].upper()} Script/Code"
        elif ext in ['.txt', '.md', '.ini', '.cfg', '.json', '.yaml', '.yml', '.xml']:
            return "Text Document"
        elif ext in ['.pdf']:
            return "PDF Document"
        elif ext in ['.doc', '.docx', '.odt']:
            return "Word Document"
        elif ext in ['.xls', '.xlsx', '.ods']:
            return "Spreadsheet"
        else:
            return f"{ext[1:].upper() if ext else 'Unknown'} File" if ext else "File"


class DirectoryNodeObject(BaseNodeObject):
    """ディレクトリを表すオブジェクト（配下の子オブジェクトリストを持つ）"""
    def __init__(self, path: str):
        super().__init__(path)
        self.size = -1
        self.children: list[BaseNodeObject] = []

    @property
    def icon(self) -> str:
        return "📁"

    @property
    def type_name(self) -> str:
        return "Folder"


class ImageNodeObject(FileNodeObject):
    """画像ファイルを表すオブジェクト"""
    SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}

    def __init__(self, path: str):
        super().__init__(path)
        self._blur_result = None

    @property
    def icon(self) -> str:
        return "🖼️"

    @property
    def type_name(self) -> str:
        ext = self.extension.lower()
        return f"{ext[1:].upper()} Image"

    @property
    def has_preview(self) -> bool:
        # SVG is not natively supported by QPixmap without extra setup
        return self.extension.lower() not in ['.svg']

    def detect_blur(self, threshold: float = 100.0, force_recheck: bool = False):
        """ピンぼけ検出を実行（キャッシュ対応）"""
        if self._blur_result is None or force_recheck or self._blur_result.threshold != threshold:
            try:
                from BlurDetector import BlurDetector
                detector = BlurDetector(threshold=threshold)
                self._blur_result = detector.detect_blur(self.path, threshold=threshold)
            except Exception as e:
                print(f"Blur detection error: {e}")
                self._blur_result = None
        return self._blur_result
