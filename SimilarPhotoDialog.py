import os
from typing import List, Optional
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon, QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QWidget, QFileDialog, QFrame, QScrollArea,
    QRadioButton, QButtonGroup, QGridLayout, QSizePolicy
)
from FilerRepository import FilerRepository
from SimilarPhotoManager import SimilarGroup, SimilarPhotoItem
from BurstPhotoDialog import ImagePreviewDialog, ClickableLabel
from BaseNodeObject import format_size

class SimilarSearchWorker(QThread):
    progress_signal = Signal(int, int, str)
    result_signal = Signal(list)
    finished_signal = Signal()

    def __init__(self, dir_path: str, recursive: bool, max_hash_dist: int, blur_threshold: float):
        super().__init__()
        self.dir_path = dir_path
        self.recursive = recursive
        self.max_hash_dist = max_hash_dist
        self.blur_threshold = blur_threshold
        self._is_cancelled = False
        self.repository = FilerRepository()

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def report_progress(self, current: int, total: int, msg: str):
        self.progress_signal.emit(current, total, msg)

    def run(self):
        groups = self.repository.search_similar_photo_groups(
            dir_path=self.dir_path,
            recursive=self.recursive,
            max_hash_distance=self.max_hash_dist,
            blur_threshold=self.blur_threshold,
            is_cancelled_func=self.is_cancelled,
            progress_callback=self.report_progress
        )
        if not self._is_cancelled:
            self.result_signal.emit(groups)
        self.finished_signal.emit()


class SimilarPhotoDialog(QDialog):
    def __init__(self, parent=None, initial_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("🖼️ 類似写真ピント判定・整理 - Similar Photo Focus Manager")
        self.resize(1200, 800)
        
        self.initial_dir = initial_dir or os.getcwd()
        self.worker: Optional[SimilarSearchWorker] = None
        self.groups: List[SimilarGroup] = []
        self.current_group_index: int = -1
        self.repository = FilerRepository()
        
        self.init_ui()
        self.apply_styles()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        
        # 1. 検索設定パネル
        config_frame = QFrame()
        config_frame.setObjectName("configFrame")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 10, 12, 10)
        config_layout.setSpacing(8)
        
        dir_layout = QHBoxLayout()
        dir_label = QLabel("対象フォルダ:")
        dir_label.setStyleSheet("font-weight: bold;")
        self.dir_edit = QLineEdit(self.initial_dir)
        btn_browse = QPushButton("参照...")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self.browse_directory)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(btn_browse)
        config_layout.addLayout(dir_layout)
        
        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(16)
        
        self.chk_recursive = QCheckBox("サブフォルダも含めて再帰検索する")
        self.chk_recursive.setChecked(True)
        
        dist_label = QLabel("類似許容度(1-30ビット, 小さいほど厳密):")
        self.spin_hash_dist = QSpinBox()
        self.spin_hash_dist.setRange(1, 30)
        self.spin_hash_dist.setValue(10)
        self.spin_hash_dist.setFixedWidth(70)
        
        blur_label = QLabel("ピンぼけ参考閾値:")
        self.spin_blur_thresh = QDoubleSpinBox()
        self.spin_blur_thresh.setRange(1.0, 5000.0)
        self.spin_blur_thresh.setValue(100.0)
        self.spin_blur_thresh.setSingleStep(10.0)
        self.spin_blur_thresh.setFixedWidth(90)

        self.btn_start = QPushButton("🔍 類似写真を検索・ピント判定")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setFixedHeight(34)
        self.btn_start.clicked.connect(self.toggle_search)

        opts_layout.addWidget(self.chk_recursive)
        opts_layout.addWidget(dist_label)
        opts_layout.addWidget(self.spin_hash_dist)
        opts_layout.addWidget(blur_label)
        opts_layout.addWidget(self.spin_blur_thresh)
        opts_layout.addStretch()
        opts_layout.addWidget(self.btn_start)
        
        config_layout.addLayout(opts_layout)
        main_layout.addWidget(config_frame, stretch=0)
        
        # 2. プログレスバー & ステータス表示
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar, stretch=0)
        
        self.status_label = QLabel("対象フォルダを指定して「検索・ピント判定」を開始してください。")
        self.status_label.setStyleSheet("color: #aaaaaa; font-style: italic; margin-left: 4px;")
        main_layout.addWidget(self.status_label, stretch=0)
        
        # 3. メインエリア (Splitter: stretch=1 で縦方向最大に展開)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        
        left_title = QLabel("📁 検出された類似写真グループ")
        left_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #00bcd4;")
        left_layout.addWidget(left_title)
        
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self.on_group_selected)
        left_layout.addWidget(self.group_list)
        
        splitter.addWidget(left_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        
        group_action_frame = QFrame()
        group_action_frame.setObjectName("groupActionFrame")
        group_action_layout = QHBoxLayout(group_action_frame)
        group_action_layout.setContentsMargins(10, 8, 10, 8)
        
        self.group_detail_header = QLabel("左側のグループを選択してください")
        self.group_detail_header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        
        self.btn_ungroup = QPushButton("🔓 グループ化を解除")
        self.btn_ungroup.setObjectName("btnUngroup")
        self.btn_ungroup.setFixedHeight(34)
        self.btn_ungroup.setEnabled(False)
        self.btn_ungroup.clicked.connect(self.ungroup_current_group)

        self.btn_delete_group_items = QPushButton("🗑️ 選択中グループの不要ファイルを削除 (ごみ箱へ移動)")
        self.btn_delete_group_items.setObjectName("btnDeleteGroupItems")
        self.btn_delete_group_items.setFixedHeight(34)
        self.btn_delete_group_items.setEnabled(False)
        self.btn_delete_group_items.clicked.connect(self.delete_current_group_trash_candidates)
        
        group_action_layout.addWidget(self.group_detail_header, stretch=1)
        group_action_layout.addWidget(self.btn_ungroup)
        group_action_layout.addWidget(self.btn_delete_group_items)
        
        right_layout.addWidget(group_action_frame)
        
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(14)
        self.cards_scroll.setWidget(self.cards_container)
        
        right_layout.addWidget(self.cards_scroll)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([260, 940])
        main_layout.addWidget(splitter, stretch=1)
        
        # 4. フッターエリア (stretch=0 で下部にコンパクト配置)
        footer_frame = QFrame()
        footer_frame.setObjectName("footerFrame")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(12, 6, 12, 6)
        
        self.summary_label = QLabel("類似グループ数: 0")
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
        
        btn_close = QPushButton("閉じる")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.close)
        
        footer_layout.addWidget(self.summary_label)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_close)
        
        main_layout.addWidget(footer_frame, stretch=0)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            #configFrame, #footerFrame {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            #groupActionFrame {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 6px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton {
                background-color: #3a3d41;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4a4d51;
            }
            #btnStart {
                background-color: #00838f;
                font-weight: bold;
            }
            #btnStart:hover {
                background-color: #0097a7;
            }
            #btnUngroup {
                background-color: #4a4d51;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
            }
            #btnUngroup:hover {
                background-color: #5a5d61;
            }
            #btnUngroup:disabled {
                background-color: #333333;
                color: #777777;
            }
            #btnDeleteGroupItems {
                background-color: #c62828;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
            }
            #btnDeleteGroupItems:hover {
                background-color: #d32f2f;
            }
            #btnDeleteGroupItems:disabled {
                background-color: #555555;
                color: #888888;
            }
            QListWidget {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #005662;
                color: #ffffff;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "対象フォルダの選択", self.dir_edit.text())
        if dir_path:
            self.dir_edit.setText(dir_path)

    def toggle_search(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("検索を中断しています...")
            return

        target_dir = self.dir_edit.text().strip()
        if not os.path.isdir(target_dir):
            QMessageBox.warning(self, "エラー", "指定された対象フォルダが存在しません。")
            return

        self.groups.clear()
        self.group_list.clear()
        self.clear_cards_grid()
        self.group_detail_header.setText("左側のグループを選択してください")
        self.btn_delete_group_items.setEnabled(False)
        self.btn_ungroup.setEnabled(False)

        self.btn_start.setText("⏹️ 中止")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("類似画像を解析・比較中 (知覚ハッシュ dHash)...")

        self.worker = SimilarSearchWorker(
            dir_path=target_dir,
            recursive=self.chk_recursive.isChecked(),
            max_hash_dist=self.spin_hash_dist.value(),
            blur_threshold=self.spin_blur_thresh.value()
        )
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.result_signal.connect(self.on_worker_result)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, current: int, total: int, msg: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
        self.status_label.setText(f"[{current}/{total}] {msg}")

    def on_worker_result(self, groups: List[SimilarGroup]):
        self.groups = groups
        self.update_group_list_ui()

    def on_worker_finished(self):
        self.btn_start.setText("🔍 類似写真を検索・ピント判定")
        self.progress_bar.setVisible(False)
        
        if not self.groups:
            self.status_label.setText("構図や見た目の似ている類似画像グループは見つかりませんでした。")
        else:
            total_items = sum(g.total_count for g in self.groups)
            self.status_label.setText(
                f"検索完了: {len(self.groups)} 個の類似写真グループを検出 (合計 {total_items} 枚)"
            )
            self.group_list.setCurrentRow(0)

        self.update_summary_footer()

    def update_group_list_ui(self):
        self.group_list.clear()
        for g in self.groups:
            del_cnt = g.deletion_count
            item_text = (
                f"類似グループ {g.group_id}\n"
                f"  全 {g.total_count} 枚  [保持 1枚 / 削除 {del_cnt}枚]"
            )
            widget_item = QListWidgetItem(item_text)
            self.group_list.addItem(widget_item)

    def on_group_selected(self, row: int):
        if row < 0 or row >= len(self.groups):
            self.current_group_index = -1
            self.clear_cards_grid()
            self.group_detail_header.setText("左側のグループを選択してください")
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)
            return

        self.current_group_index = row
        group = self.groups[row]
        
        del_cnt = group.deletion_count
        del_size = sum(
            os.path.getsize(it.image_path) for it in group.items 
            if it.marked_for_deletion and os.path.exists(it.image_path)
        )
        
        self.group_detail_header.setText(
            f"類似グループ {group.group_id} : 全 {group.total_count} 枚 | 削除対象 {del_cnt} 枚 ({format_size(del_size)})"
        )
        self.btn_delete_group_items.setEnabled(del_cnt > 0)
        self.btn_ungroup.setEnabled(True)
        self.render_group_cards(group)

    def clear_cards_grid(self):
        while self.cards_grid.count():
            child = self.cards_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def render_group_cards(self, group: SimilarGroup):
        self.clear_cards_grid()
        
        cols = 2
        for idx, item in enumerate(group.items):
            card = self.create_photo_card(group, item)
            r = idx // cols
            c = idx % cols
            self.cards_grid.addWidget(card, r, c)

    def create_photo_card(self, group: SimilarGroup, item: SimilarPhotoItem) -> QWidget:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #2b2b2c;
                border: 1px solid #444444;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # サムネイル画像：固定高さ220px、横幅レスポンシブ拡大
        lbl_thumb = ClickableLabel()
        lbl_thumb.setFixedHeight(220)
        lbl_thumb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lbl_thumb.setToolTip("クリックすると拡大プレビュー表示します")
        lbl_thumb.setStyleSheet("background-color: #1a1a1a; border-radius: 6px;")
        
        pixmap = QPixmap(item.image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(420, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_thumb.setPixmap(scaled)
        else:
            lbl_thumb.setText("No Image")
            
        lbl_thumb.clicked.connect(lambda it=item: self.open_preview(it))
        layout.addWidget(lbl_thumb)

        fname = os.path.basename(item.image_path)
        lbl_name = QLabel(fname)
        lbl_name.setToolTip(item.image_path)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffffff;")
        lbl_name.setWordWrap(True)
        layout.addWidget(lbl_name)
        
        score_layout = QHBoxLayout()
        lbl_score = QLabel(f"スコア: {item.composite_score}")
        lbl_score.setStyleSheet("font-weight: bold; color: #4fc3f7; font-size: 13px;")
        
        if item.is_recommended_keep:
            lbl_badge = QLabel("🎯 ピント最良")
            lbl_badge.setStyleSheet("background-color: #2e7d32; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        else:
            lbl_badge = QLabel("⚠️ 類似/補足")
            lbl_badge.setStyleSheet("background-color: #e65100; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px;")

        score_layout.addWidget(lbl_score)
        score_layout.addStretch()
        score_layout.addWidget(lbl_badge)
        layout.addLayout(score_layout)

        btn_group = QButtonGroup(card)
        
        rb_keep = QRadioButton("🟢 残す (保持)")
        rb_trash = QRadioButton("🗑️ 削除候補 (ごみ箱)")
        
        rb_keep.setStyleSheet("color: #a5d6a7; font-weight: bold; font-size: 12px;")
        rb_trash.setStyleSheet("color: #ef9a9a; font-weight: bold; font-size: 12px;")
        
        if item.marked_for_deletion:
            rb_trash.setChecked(True)
        else:
            rb_keep.setChecked(True)
            
        btn_group.addButton(rb_keep, 0)
        btn_group.addButton(rb_trash, 1)

        def on_radio_changed(id_val: int):
            if id_val == 0:
                item.marked_for_deletion = False
            else:
                item.marked_for_deletion = True
            self.update_group_header_and_button()
            self.update_group_list_ui_quiet()
            self.update_summary_footer()

        btn_group.idClicked.connect(on_radio_changed)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(rb_keep)
        radio_layout.addWidget(rb_trash)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        btn_preview = QPushButton("🔍 拡大プレビュー表示")
        btn_preview.setFixedHeight(28)
        btn_preview.setStyleSheet("font-size: 12px; padding: 4px;")
        btn_preview.clicked.connect(lambda checked=False, it=item: self.open_preview(it))
        layout.addWidget(btn_preview)

        return card

    def open_preview(self, item: SimilarPhotoItem):
        from BurstPhotoManager import BurstPhotoItem
        dummy_item = BurstPhotoItem(
            image_path=item.image_path,
            timestamp=0.0,
            timestamp_str="-",
            blur_result=item.blur_result,
            composite_score=item.composite_score
        )
        dlg = ImagePreviewDialog(self, dummy_item)
        dlg.exec()

    def update_group_header_and_button(self):
        if self.current_group_index < 0 or self.current_group_index >= len(self.groups):
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)
            return

        group = self.groups[self.current_group_index]
        del_cnt = group.deletion_count
        del_size = sum(
            os.path.getsize(it.image_path) for it in group.items 
            if it.marked_for_deletion and os.path.exists(it.image_path)
        )
        self.group_detail_header.setText(
            f"類似グループ {group.group_id} : 全 {group.total_count} 枚 | 削除対象 {del_cnt} 枚 ({format_size(del_size)})"
        )
        self.btn_delete_group_items.setEnabled(del_cnt > 0)
        self.btn_ungroup.setEnabled(True)

    def update_group_list_ui_quiet(self):
        curr = self.group_list.currentRow()
        for idx, g in enumerate(self.groups):
            del_cnt = g.deletion_count
            item_text = (
                f"類似グループ {g.group_id}\n"
                f"  全 {g.total_count} 枚  [保持 1枚 / 削除 {del_cnt}枚]"
            )
            item = self.group_list.item(idx)
            if item:
                item.setText(item_text)
        if curr >= 0:
            self.group_list.setCurrentRow(curr)

    def update_summary_footer(self):
        total_groups = len(self.groups)
        total_items = sum(g.total_count for g in self.groups)
        self.summary_label.setText(
            f"検出類似グループ: {total_groups}グループ (計 {total_items}枚)"
        )

    def ungroup_current_group(self):
        if self.current_group_index < 0 or self.current_group_index >= len(self.groups):
            return

        target_idx = self.current_group_index
        group = self.groups[target_idx]

        reply = QMessageBox.question(
            self, "グループ化を解除",
            f"類似グループ {group.group_id} のグループ化を解除しますか？\n（ファイルは削除されず、グループ一覧から除外されます）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.groups.pop(target_idx)
        for idx, g in enumerate(self.groups):
            g.group_id = idx + 1

        self.update_group_list_ui()

        if self.groups:
            next_row = min(target_idx, len(self.groups) - 1)
            self.group_list.setCurrentRow(next_row)
        else:
            self.current_group_index = -1
            self.clear_cards_grid()
            self.group_detail_header.setText("左側のグループを選択してください")
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)

        self.update_summary_footer()

    def delete_current_group_trash_candidates(self):
        if self.current_group_index < 0 or self.current_group_index >= len(self.groups):
            return

        target_idx = self.current_group_index
        group = self.groups[target_idx]
        del_items = [it for it in group.items if it.marked_for_deletion and os.path.exists(it.image_path)]

        if not del_items:
            QMessageBox.information(self, "通知", "このグループで削除対象に設定されたファイルはありません。")
            return

        total_size = sum(os.path.getsize(it.image_path) for it in del_items if os.path.exists(it.image_path))

        msg = (
            f"類似グループ {group.group_id} の削除対象 {len(del_items)} 個のファイルをOSのごみ箱へ移動します。\n"
            f"容量: {format_size(total_size)}\n\n"
            f"※ 削除されたファイルはごみ箱から復元可能です。\n"
            f"移動しますか？"
        )
        reply = QMessageBox.question(
            self, "選択中類似グループのごみ箱移動", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        success_count = 0
        failed_count = 0

        for item in del_items:
            ok = self.repository.send_to_trash(item.image_path)
            if ok:
                success_count += 1
                group.items.remove(item)
            else:
                failed_count += 1

        group_removed = False
        if len(group.items) <= 1:
            self.groups.remove(group)
            group_removed = True
            for idx, g in enumerate(self.groups):
                g.group_id = idx + 1

        self.update_group_list_ui()

        if self.groups:
            if group_removed:
                next_row = min(target_idx, len(self.groups) - 1)
            else:
                next_row = (target_idx + 1) if (target_idx + 1) < len(self.groups) else min(target_idx, len(self.groups) - 1)
            self.group_list.setCurrentRow(next_row)
        else:
            self.current_group_index = -1
            self.clear_cards_grid()
            self.group_detail_header.setText("左側のグループを選択してください")
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)

        self.update_summary_footer()

        result_msg = f"類似グループから {success_count} 個の不要ファイルを正常にごみ箱へ移動しました。"
        if failed_count > 0:
            result_msg += f"\n({failed_count} 個のファイル移動に失敗しました)"
        QMessageBox.information(self, "完了", result_msg)
