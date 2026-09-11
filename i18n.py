# -*- coding: utf-8 -*-
"""
i18n.py - Internationalization (English / Japanese) Support
Supports dynamic language switching, persistent settings, and formatted translations.
"""

from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal, QSettings

class I18nManager(QObject):
    language_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._settings = QSettings("Antigravity", "PhotoFiler")
        saved_lang = self._settings.value("language", "ja")
        self._current_lang = saved_lang if saved_lang in ("en", "ja") else "ja"

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang: str):
        if lang in ("en", "ja") and lang != self._current_lang:
            self._current_lang = lang
            self._settings.setValue("language", lang)
            self.language_changed.emit(lang)

    def t(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self._current_lang, TRANSLATIONS["en"])
        val = lang_dict.get(key)
        if val is None:
            val = TRANSLATIONS["en"].get(key, default if default is not None else key)
        if kwargs:
            try:
                return val.format(**kwargs)
            except Exception:
                return val
        return val

_i18n = I18nManager()

def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    return _i18n.t(key, default=default, **kwargs)

def get_current_language() -> str:
    return _i18n.current_language

def set_language(lang: str):
    _i18n.set_language(lang)

def get_i18n_manager() -> I18nManager:
    return _i18n

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ja": {
        # App General
        "app.title": "Antigravity Filer - 写真＆ファイルマネージャー",
        "app.language": "言語 (Language)",
        "app.lang_en": "English",
        "app.lang_ja": "日本語",

        # Toolbar & Navigation
        "nav.back": "戻る",
        "nav.forward": "進む",
        "nav.up": "上へ",
        "nav.refresh": "更新",
        "nav.path_placeholder": "パスを入力してEnter...",
        "nav.filter_placeholder": "🔍 ファイル名で絞り込み...",

        # Tools
        "tool.blur_search": "🔍 ピンぼけ検索",
        "tool.blur_search_tip": "開いているフォルダ配下のピンぼけ画像を検索",
        "tool.burst_search": "📸 連続写真整理",
        "tool.burst_search_tip": "連続写真を抽出してピント最高1枚を保持・他をごみ箱へ整理",
        "tool.similar_search": "🖼️ 類似写真整理",
        "tool.similar_search_tip": "構図や見た目の似ている写真を抽出しピント最高1枚を保持・他をごみ箱へ整理",

        # Sidebar Shortcuts
        "sidebar.home": "🏠 ホーム",
        "sidebar.pictures": "🖼️ ピクチャ",
        "sidebar.documents": "📁 ドキュメント",
        "sidebar.downloads": "⬇️ ダウンロード",
        "sidebar.desktop": "💻 デスクトップ",
        "sidebar.root": "🗄️ ルート",

        # File Table
        "table.col_name": "名前",
        "table.col_size": "サイズ",
        "table.col_type": "種類",
        "table.col_mtime": "更新日時",

        # Preview Panel
        "preview.title": "プレビュー / 詳細",
        "preview.no_selection": "ファイルを選択するとプレビューが表示されます",
        "preview.loading": "プレビューを読み込み中...",
        "preview.no_preview": "このファイル形式のプレビューは利用できません",
        "preview.lbl_name": "名前:",
        "preview.lbl_type": "種類:",
        "preview.lbl_size": "サイズ:",
        "preview.lbl_mtime": "更新日時:",
        "preview.mark_selected": "選択マーク（対象指定）",
        "preview.blur_box": "📷 ピンぼけ判定",
        "preview.blur_status": "判定: 未実行",
        "preview.blur_status_fmt": "判定: {status}",
        "preview.blur_score": "鮮鋭度スコア: -",
        "preview.blur_score_fmt": "鮮鋭度スコア: {score}",
        "preview.blur_faces": "顔検出: -",
        "preview.blur_faces_fmt": "顔検出: {count}個",
        "preview.btn_check_blur": "ピント詳細診断",

        # Status Bar
        "status.item_count": "{count} 個の項目",
        "status.selected_count": "（{count} 個選択中）",
        "status.loading": "フォルダを読み込み中...",
        "status.ready": "準備完了",

        # Context Menu
        "menu.open": "開く (Enter)",
        "menu.open_external": "関連付けられたアプリで開く",
        "menu.check_blur": "ピンぼけ詳細診断...",
        "menu.rename": "名前の変更 (F2)",
        "menu.trash": "ごみ箱に移動 (Delete)",
        "menu.delete_permanent": "完全に削除 (Shift+Delete)",
        "menu.new_folder": "新規フォルダ作成",
        "menu.new_file": "新規テキストファイル作成",
        "menu.refresh": "更新 (F5)",

        # Dialogs / Prompts
        "dialog.rename_title": "名前の変更",
        "dialog.rename_label": "新しい名前を入力してください:",
        "dialog.new_folder_title": "新規フォルダ作成",
        "dialog.new_folder_label": "新しいフォルダ名:",
        "dialog.new_file_title": "新規ファイル作成",
        "dialog.new_file_label": "新しいファイル名:",
        "dialog.trash_confirm_title": "ごみ箱への移動",
        "dialog.trash_confirm_msg": "選択した {count} 個の項目をごみ箱に移動しますか？",
        "dialog.delete_confirm_title": "完全削除の確認",
        "dialog.delete_confirm_msg": "選択した {count} 個の項目を完全に削除しますか？\n⚠️ この操作は元に戻せません！",
        "dialog.error": "エラー",
        "dialog.cannot_open": "ファイルを開けませんでした: {path}",
        "dialog.delete_failed": "一部またはすべての項目の削除に失敗しました。",
        "dialog.rename_failed": "名前の変更に失敗しました。",
        "dialog.create_failed": "作成に失敗しました。",

        # Blur Search Dialog
        "blur_dialog.title": "🔍 ピンぼけ画像検索 - Out of Focus Photo Finder",
        "blur_dialog.target_folder": "対象フォルダ:",
        "blur_dialog.browse": "参照...",
        "blur_dialog.recursive": "サブフォルダも含めて再帰検索する",
        "blur_dialog.threshold_label": "判定閾値 (Score < Threshold でピンぼけ):",
        "blur_dialog.btn_search": "🔍 検索開始",
        "blur_dialog.btn_cancel": "⏹️ キャンセル",
        "blur_dialog.initial_status": "対象フォルダを指定して「検索開始」を押してください。",
        "blur_dialog.col_file": "ファイル名",
        "blur_dialog.col_score": "鮮鋭度スコア",
        "blur_dialog.col_face": "顔検出",
        "blur_dialog.col_path": "相対パス",
        "blur_dialog.btn_open": "📂 開く",
        "blur_dialog.btn_show_in_main": "🎯 ファイラーで表示",
        "blur_dialog.btn_detail": "🔍 詳細診断",
        "blur_dialog.ready": "検索準備中...",
        "blur_dialog.cancelling": "検索をキャンセル中...",
        "blur_dialog.scanning": "スキャン中... ({current}/{total}) [発見: {found}件]: {file}",
        "blur_dialog.finished_cancelled": "検索がキャンセルされました。(発見: {count} 件)",
        "blur_dialog.finished_done": "検索完了: ピンぼけ画像が {count} 件見つかりました。",
        "blur_dialog.select_image": "画像を選択してください",
        "blur_dialog.preview_fail": "プレビュー読み込み失敗",
        "blur_dialog.lbl_file": "ファイル:",
        "blur_dialog.lbl_judgment": "判定:",
        "blur_dialog.lbl_reason": "判定理由:",
        "blur_dialog.lbl_score": "全体スコア:",
        "blur_dialog.lbl_max_grid": "最高領域スコア:",
        "blur_dialog.lbl_face": "顔検出:",
        "blur_dialog.face_yes": "{count} 個の顔領域をチェック済み",
        "blur_dialog.face_no": "なし (グリッド領域解析により自動評価)",
        "blur_dialog.face_present": "あり ({count}個)",
        "blur_dialog.face_none": "なし",

        # Burst Photo Dialog
        "burst_dialog.title": "📸 連続写真ピント判定・整理 - Burst Photo Focus Manager",
        "burst_dialog.target_folder": "対象フォルダ:",
        "burst_dialog.browse": "参照...",
        "burst_dialog.recursive": "サブフォルダも含めて再帰検索する",
        "burst_dialog.interval_label": "連続撮影とみなす最大間隔 (秒):",
        "burst_dialog.blur_label": "ピンぼけ判定閾値:",
        "burst_dialog.btn_search": "🔍 連続写真を検索・ピント判定",
        "burst_dialog.btn_cancel": "⏹️ キャンセル",
        "burst_dialog.initial_status": "対象フォルダを指定して「検索・ピント判定」を開始してください。",
        "burst_dialog.group_list_title": "検出された連続写真グループ",
        "burst_dialog.selected_group_title": "選択グループ内の写真比較・整理",
        "burst_dialog.keep_best_auto": "🟢 最良1枚を自動保持",
        "burst_dialog.trash_selected": "🗑️ 選択した不要写真をごみ箱へ移動",
        "burst_dialog.dismiss_group": "解散 (グループ解除)",
        "burst_dialog.card_keep": "🟢 残す (保持推奨)",
        "burst_dialog.card_trash": "🗑️ 削除候補",
        "burst_dialog.card_time": "撮影:",
        "burst_dialog.card_score": "スコア:",
        "burst_dialog.card_click_preview": "クリックで拡大プレビュー",
        "burst_dialog.preview_title": "📷 画像詳細プレビュー - {filename}",
        "burst_dialog.preview_filename": "ファイル名:",
        "burst_dialog.preview_datetime": "撮影日時:",
        "burst_dialog.preview_score": "ピントスコア:",
        "burst_dialog.preview_reason": "判定理由:",
        "burst_dialog.preview_faces": "顔詳細:",
        "burst_dialog.preview_close": "閉じる",
        "burst_dialog.group_item": "グループ {idx} ({count}枚, {time})",
        "burst_dialog.group_trash_confirm": "グループ {group_id} の不要な写真 {count} 枚をごみ箱へ移動しますか？",
        "burst_dialog.trash_success": "{count} 枚の不要写真をごみ箱に移動しました。",
        "burst_dialog.no_trash_target": "削除対象の写真が選択されていません。",
        "burst_dialog.all_cleared": "🎉 すべての連続写真グループの整理が完了しました！",
        "burst_dialog.select_group_prompt": "左の一覧からグループを選択してください。",

        # Similar Photo Dialog
        "similar_dialog.title": "🖼️ 類似写真ピント判定・整理 - Similar Photo Focus Manager",
        "similar_dialog.target_folder": "対象フォルダ:",
        "similar_dialog.browse": "参照...",
        "similar_dialog.recursive": "サブフォルダも含めて再帰検索する",
        "similar_dialog.dist_label": "類似許容度 (1-30ビット, 小さいほど厳密):",
        "similar_dialog.blur_label": "ピンぼけ参考閾値:",
        "similar_dialog.btn_search": "🔍 類似写真を検索・ピント判定",
        "similar_dialog.btn_cancel": "⏹️ キャンセル",
        "similar_dialog.initial_status": "対象フォルダを指定して「検索・ピント判定」を開始してください。",
        "similar_dialog.group_list_title": "検出された類似写真グループ",
        "similar_dialog.selected_group_title": "選択グループ内の写真比較・整理",
        "similar_dialog.keep_best_auto": "🟢 最良1枚を自動保持",
        "similar_dialog.trash_selected": "🗑️ 選択した不要写真をごみ箱へ移動",
        "similar_dialog.dismiss_group": "解散 (グループ解除)",
        "similar_dialog.group_item": "類似グループ {idx} ({count}枚)",
        "similar_dialog.group_trash_confirm": "類似グループ {group_id} の不要な写真 {count} 枚をごみ箱へ移動しますか？",
        "similar_dialog.trash_success": "{count} 枚の不要写真をごみ箱に移動しました。",
        "similar_dialog.all_cleared": "🎉 すべての類似写真グループの整理が完了しました！",
        "similar_dialog.select_group_prompt": "左の一覧からグループを選択してください。",

        # Node Types & Blur Status
        "node.folder": "フォルダ",
        "node.file": "ファイル",
        "node.archive": "{ext} アーカイブ",
        "node.audio": "{ext} 音声",
        "node.video": "{ext} 動画",
        "node.code": "{ext} スクリプト/コード",
        "node.text": "テキストドキュメント",
        "node.pdf": "PDF ドキュメント",
        "node.word": "Word ドキュメント",
        "node.sheet": "スプレッドシート",
        "node.image": "{ext} 画像",
        "status.sharp": "鮮明",
        "status.blurry": "ピンぼけ",
        "reason.sharp_subject": "画面内に十分鮮明な被写体・領域を検出 (背景ボケ考慮)",
        "reason.uniform_sharp": "画像全体が均一に鮮明",
        "reason.overall_blurry": "画面全体および各領域で鮮鋭度が低下（全体的にピンぼけ）",
        "reason.face_focused": "主要な顔領域にフォーカスが合っています",
        "reason.face_soft_fallback": "顔領域はややソフトですが画面内に鮮明な焦点領域を検出",
        "reason.face_blurry": "検出された顔領域のフォーカスが甘くボケています",
    },
    "en": {
        # App General
        "app.title": "Antigravity Filer - Photo & File Manager",
        "app.language": "Language",
        "app.lang_en": "English",
        "app.lang_ja": "日本語",

        # Toolbar & Navigation
        "nav.back": "Back",
        "nav.forward": "Forward",
        "nav.up": "Up",
        "nav.refresh": "Refresh",
        "nav.path_placeholder": "Enter path and press Enter...",
        "nav.filter_placeholder": "🔍 Filter by name...",

        # Tools
        "tool.blur_search": "🔍 Blurry Photos",
        "tool.blur_search_tip": "Find blurry photos in current folder and subfolders",
        "tool.burst_search": "📸 Burst Photos",
        "tool.burst_search_tip": "Detect burst shots, keep the sharpest one, and move duplicates to trash",
        "tool.similar_search": "🖼️ Similar Photos",
        "tool.similar_search_tip": "Group visually similar photos, keep the sharpest one, and clean up duplicates",

        # Sidebar Shortcuts
        "sidebar.home": "🏠 Home",
        "sidebar.pictures": "🖼️ Pictures",
        "sidebar.documents": "📁 Documents",
        "sidebar.downloads": "⬇️ Downloads",
        "sidebar.desktop": "💻 Desktop",
        "sidebar.root": "🗄️ Root",

        # File Table
        "table.col_name": "Name",
        "table.col_size": "Size",
        "table.col_type": "Type",
        "table.col_mtime": "Date Modified",

        # Preview Panel
        "preview.title": "Preview / Details",
        "preview.no_selection": "Select a file to display preview",
        "preview.loading": "Loading preview...",
        "preview.no_preview": "Preview is not available for this file type",
        "preview.lbl_name": "Name:",
        "preview.lbl_type": "Type:",
        "preview.lbl_size": "Size:",
        "preview.lbl_mtime": "Modified:",
        "preview.mark_selected": "Mark as Selected",
        "preview.blur_box": "📷 Focus & Blur Check",
        "preview.blur_status": "Status: Not evaluated",
        "preview.blur_status_fmt": "Status: {status}",
        "preview.blur_score": "Sharpness Score: -",
        "preview.blur_score_fmt": "Sharpness Score: {score}",
        "preview.blur_faces": "Face Detection: -",
        "preview.blur_faces_fmt": "Face Detection: {count} face(s)",
        "preview.btn_check_blur": "Detailed Focus Diagnostics",

        # Status Bar
        "status.item_count": "{count} items",
        "status.selected_count": "({count} selected)",
        "status.loading": "Loading directory...",
        "status.ready": "Ready",

        # Context Menu
        "menu.open": "Open (Enter)",
        "menu.open_external": "Open with Default App",
        "menu.check_blur": "Focus Diagnostics...",
        "menu.rename": "Rename (F2)",
        "menu.trash": "Move to Trash (Delete)",
        "menu.delete_permanent": "Delete Permanently (Shift+Delete)",
        "menu.new_folder": "New Folder",
        "menu.new_file": "New Text File",
        "menu.refresh": "Refresh (F5)",

        # Dialogs / Prompts
        "dialog.rename_title": "Rename",
        "dialog.rename_label": "Enter new name:",
        "dialog.new_folder_title": "New Folder",
        "dialog.new_folder_label": "New folder name:",
        "dialog.new_file_title": "New File",
        "dialog.new_file_label": "New file name:",
        "dialog.trash_confirm_title": "Move to Trash",
        "dialog.trash_confirm_msg": "Move {count} selected item(s) to trash?",
        "dialog.delete_confirm_title": "Permanent Deletion",
        "dialog.delete_confirm_msg": "Permanently delete {count} selected item(s)?\n⚠️ This action cannot be undone!",
        "dialog.error": "Error",
        "dialog.cannot_open": "Could not open file: {path}",
        "dialog.delete_failed": "Failed to delete one or more items.",
        "dialog.rename_failed": "Failed to rename item.",
        "dialog.create_failed": "Failed to create item.",

        # Blur Search Dialog
        "blur_dialog.title": "🔍 Blurry Photo Finder - Out of Focus Photo Finder",
        "blur_dialog.target_folder": "Target Folder:",
        "blur_dialog.browse": "Browse...",
        "blur_dialog.recursive": "Include subfolders recursively",
        "blur_dialog.threshold_label": "Threshold (Score < Threshold is Blurry):",
        "blur_dialog.btn_search": "🔍 Start Search",
        "blur_dialog.btn_cancel": "⏹️ Cancel",
        "blur_dialog.initial_status": "Select a target folder and click 'Start Search'.",
        "blur_dialog.col_file": "File Name",
        "blur_dialog.col_score": "Sharpness Score",
        "blur_dialog.col_face": "Face Detection",
        "blur_dialog.col_path": "Relative Path",
        "blur_dialog.btn_open": "📂 Open",
        "blur_dialog.btn_show_in_main": "🎯 Show in Filer",
        "blur_dialog.btn_detail": "🔍 Diagnostics",
        "blur_dialog.ready": "Preparing search...",
        "blur_dialog.cancelling": "Cancelling search...",
        "blur_dialog.scanning": "Scanning... ({current}/{total}) [Found: {found}]: {file}",
        "blur_dialog.finished_cancelled": "Search cancelled. ({count} photos found)",
        "blur_dialog.finished_done": "Search complete: {count} blurry photo(s) found.",
        "blur_dialog.select_image": "Please select an image",
        "blur_dialog.preview_fail": "Failed to load preview",
        "blur_dialog.lbl_file": "File:",
        "blur_dialog.lbl_judgment": "Status:",
        "blur_dialog.lbl_reason": "Reason:",
        "blur_dialog.lbl_score": "Overall Score:",
        "blur_dialog.lbl_max_grid": "Max Grid Score:",
        "blur_dialog.lbl_face": "Face Detection:",
        "blur_dialog.face_yes": "{count} face region(s) checked",
        "blur_dialog.face_no": "None (Evaluated via grid sharpness analysis)",
        "blur_dialog.face_present": "Yes ({count})",
        "blur_dialog.face_none": "No",

        # Burst Photo Dialog
        "burst_dialog.title": "📸 Burst Photo Focus Manager",
        "burst_dialog.target_folder": "Target Folder:",
        "burst_dialog.browse": "Browse...",
        "burst_dialog.recursive": "Include subfolders recursively",
        "burst_dialog.interval_label": "Max interval for burst (seconds):",
        "burst_dialog.blur_label": "Blur threshold:",
        "burst_dialog.btn_search": "🔍 Find Burst Photos & Assess Focus",
        "burst_dialog.btn_cancel": "⏹️ Cancel",
        "burst_dialog.initial_status": "Select a target folder and click 'Find Burst Photos & Assess Focus'.",
        "burst_dialog.group_list_title": "Detected Burst Groups",
        "burst_dialog.selected_group_title": "Photo Comparison & Cleanup in Group",
        "burst_dialog.keep_best_auto": "🟢 Auto-Keep Best Photo",
        "burst_dialog.trash_selected": "🗑️ Move Unwanted Photos to Trash",
        "burst_dialog.dismiss_group": "Dismiss Group",
        "burst_dialog.card_keep": "🟢 Keep (Recommended)",
        "burst_dialog.card_trash": "🗑️ Delete Candidate",
        "burst_dialog.card_time": "Time:",
        "burst_dialog.card_score": "Score:",
        "burst_dialog.card_click_preview": "Click to expand preview",
        "burst_dialog.preview_title": "📷 Photo Preview - {filename}",
        "burst_dialog.preview_filename": "File Name:",
        "burst_dialog.preview_datetime": "Captured At:",
        "burst_dialog.preview_score": "Sharpness Score:",
        "burst_dialog.preview_reason": "Reason:",
        "burst_dialog.preview_faces": "Face Details:",
        "burst_dialog.preview_close": "Close",
        "burst_dialog.group_item": "Group {idx} ({count} photos, {time})",
        "burst_dialog.group_trash_confirm": "Move {count} unwanted photo(s) in Group {group_id} to trash?",
        "burst_dialog.trash_success": "{count} photo(s) moved to trash.",
        "burst_dialog.no_trash_target": "No photos selected for deletion.",
        "burst_dialog.all_cleared": "🎉 All burst photo groups have been organized!",
        "burst_dialog.select_group_prompt": "Please select a group from the list on the left.",

        # Similar Photo Dialog
        "similar_dialog.title": "🖼️ Similar Photo Focus Manager",
        "similar_dialog.target_folder": "Target Folder:",
        "similar_dialog.browse": "Browse...",
        "similar_dialog.recursive": "Include subfolders recursively",
        "similar_dialog.dist_label": "Similarity tolerance (1-30 bits, lower is stricter):",
        "similar_dialog.blur_label": "Blur threshold reference:",
        "similar_dialog.btn_search": "🔍 Find Similar Photos & Assess Focus",
        "similar_dialog.btn_cancel": "⏹️ Cancel",
        "similar_dialog.initial_status": "Select a target folder and click 'Find Similar Photos & Assess Focus'.",
        "similar_dialog.group_list_title": "Detected Similar Groups",
        "similar_dialog.selected_group_title": "Photo Comparison & Cleanup in Group",
        "similar_dialog.keep_best_auto": "🟢 Auto-Keep Best Photo",
        "similar_dialog.trash_selected": "🗑️ Move Unwanted Photos to Trash",
        "similar_dialog.dismiss_group": "Dismiss Group",
        "similar_dialog.group_item": "Similar Group {idx} ({count} photos)",
        "similar_dialog.group_trash_confirm": "Move {count} unwanted photo(s) in Similar Group {group_id} to trash?",
        "similar_dialog.trash_success": "{count} photo(s) moved to trash.",
        "similar_dialog.all_cleared": "🎉 All similar photo groups have been organized!",
        "similar_dialog.select_group_prompt": "Please select a group from the list on the left.",

        # Node Types & Blur Status
        "node.folder": "Folder",
        "node.file": "File",
        "node.archive": "{ext} Archive",
        "node.audio": "{ext} Audio",
        "node.video": "{ext} Video",
        "node.code": "{ext} Script/Code",
        "node.text": "Text Document",
        "node.pdf": "PDF Document",
        "node.word": "Word Document",
        "node.sheet": "Spreadsheet",
        "node.image": "{ext} Image",
        "status.sharp": "Sharp",
        "status.blurry": "Blurry",
        "reason.sharp_subject": "Sufficiently sharp subject/region detected (depth-of-field accounted)",
        "reason.uniform_sharp": "Overall image is uniformly sharp",
        "reason.overall_blurry": "Low sharpness across entire image and regions (overall blurry)",
        "reason.face_focused": "Main face region is in crisp focus",
        "reason.face_soft_fallback": "Face is slightly soft, but sharp focal subject detected in frame",
        "reason.face_blurry": "Detected face region(s) lack crisp focus and appear blurry",
    }
}
