import os
from typing import List, Optional
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QColor, QFont, QIcon, QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QDoubleSpinBox, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QWidget, QFileDialog, QFrame, QScrollArea,
    QRadioButton, QButtonGroup, QGridLayout, QSizePolicy
)
from FilerRepository import FilerRepository
from BurstPhotoManager import BurstGroup, BurstPhotoItem
from BaseNodeObject import format_size
from i18n import t, get_i18n_manager

class BurstSearchWorker(QThread):
    progress_signal = Signal(int, int, str)
    result_signal = Signal(list)
    finished_signal = Signal()

    def __init__(self, dir_path: str, recursive: bool, time_threshold: float, blur_threshold: float):
        super().__init__()
        self.dir_path = dir_path
        self.recursive = recursive
        self.time_threshold = time_threshold
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
        groups = self.repository.search_burst_photo_groups(
            dir_path=self.dir_path,
            recursive=self.recursive,
            time_threshold=self.time_threshold,
            blur_threshold=self.blur_threshold,
            is_cancelled_func=self.is_cancelled,
            progress_callback=self.report_progress
        )
        if not self._is_cancelled:
            self.result_signal.emit(groups)
        self.finished_signal.emit()


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, parent, item: BurstPhotoItem):
        super().__init__(parent)
        fname = os.path.basename(item.image_path)
        self.setWindowTitle(t("burst_dialog.preview_title", filename=fname))
        self.resize(1000, 780)
        
        layout = QVBoxLayout(self)
        
        info_str = (
            f"<b>{t('burst_dialog.preview_filename')}</b> {fname} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>{t('burst_dialog.preview_datetime')}</b> {item.timestamp_str} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>{t('burst_dialog.preview_score')}</b> <span style='font-size:15px; font-weight:bold; color:#2196F3;'>{item.composite_score}</span>"
        )
        if item.blur_result:
            info_str += f" &nbsp;&nbsp;|&nbsp;&nbsp; <b>{t('burst_dialog.preview_reason')}</b> {item.blur_result.reason_text}"

        info_label = QLabel(info_str)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #2b2b2b; border-radius: 4px; color: #ffffff; font-size: 13px;")
        layout.addWidget(info_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = QPixmap(item.image_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(950, 680, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(scaled_pixmap)
        else:
            img_label.setText(t("blur_dialog.preview_fail"))
            
        scroll.setWidget(img_label)
        layout.addWidget(scroll)
        
        btn_close = QPushButton(t("burst_dialog.preview_close"))
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


class BurstPhotoDialog(QDialog):
    def __init__(self, parent=None, initial_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("burst_dialog.title"))
        self.resize(1200, 800)
        
        self.initial_dir = initial_dir or os.getcwd()
        self.groups: List[BurstGroup] = []
        self.current_group_index: int = -1
        self.worker: Optional[BurstSearchWorker] = None
        self.repository = FilerRepository()
        
        self.init_ui()
        self.apply_styles()
        
        get_i18n_manager().language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        
        # 1. Config Panel
        config_frame = QFrame()
        config_frame.setObjectName("configFrame")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 10, 12, 10)
        config_layout.setSpacing(8)
        
        # Directory Selection Row
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(t("burst_dialog.target_folder"))
        self.dir_label.setStyleSheet("font-weight: bold;")
        self.dir_edit = QLineEdit(self.initial_dir)
        self.btn_browse = QPushButton(t("burst_dialog.browse"))
        self.btn_browse.setFixedWidth(80)
        self.btn_browse.clicked.connect(self.browse_directory)
        
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.btn_browse)
        config_layout.addLayout(dir_layout)
        
        # Options Row
        opts_layout = QHBoxLayout()
        
        self.chk_recursive = QCheckBox(t("burst_dialog.recursive"))
        self.chk_recursive.setChecked(True)
        
        self.time_label = QLabel(t("burst_dialog.interval_label"))
        self.spin_time_thresh = QDoubleSpinBox()
        self.spin_time_thresh.setRange(0.5, 30.0)
        self.spin_time_thresh.setValue(3.0)
        self.spin_time_thresh.setSingleStep(0.5)
        self.spin_time_thresh.setFixedWidth(80)
        
        self.blur_label = QLabel(t("burst_dialog.blur_label"))
        self.spin_blur_thresh = QDoubleSpinBox()
        self.spin_blur_thresh.setRange(1.0, 5000.0)
        self.spin_blur_thresh.setValue(100.0)
        self.spin_blur_thresh.setSingleStep(10.0)
        self.spin_blur_thresh.setFixedWidth(90)

        self.btn_start = QPushButton(t("burst_dialog.btn_search"))
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setFixedHeight(34)
        self.btn_start.clicked.connect(self.toggle_search)

        opts_layout.addWidget(self.chk_recursive)
        opts_layout.addWidget(self.time_label)
        opts_layout.addWidget(self.spin_time_thresh)
        opts_layout.addWidget(self.blur_label)
        opts_layout.addWidget(self.spin_blur_thresh)
        opts_layout.addStretch()
        opts_layout.addWidget(self.btn_start)
        
        config_layout.addLayout(opts_layout)
        main_layout.addWidget(config_frame, stretch=0)
        
        # 2. Progress & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar, stretch=0)
        
        self.status_label = QLabel(t("burst_dialog.initial_status"))
        self.status_label.setStyleSheet("color: #aaaaaa; font-style: italic; margin-left: 4px;")
        main_layout.addWidget(self.status_label, stretch=0)
        
        # 3. Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        
        self.left_title = QLabel(t("burst_dialog.group_list_title"))
        self.left_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #4CAF50;")
        left_layout.addWidget(self.left_title)
        
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
        
        self.group_detail_header = QLabel(t("burst_dialog.select_group_prompt"))
        self.group_detail_header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffffff;")
        
        self.btn_ungroup = QPushButton(t("burst_dialog.dismiss_group"))
        self.btn_ungroup.setObjectName("btnUngroup")
        self.btn_ungroup.setFixedHeight(34)
        self.btn_ungroup.setEnabled(False)
        self.btn_ungroup.clicked.connect(self.ungroup_current_group)

        self.btn_delete_group_items = QPushButton(t("burst_dialog.trash_selected"))
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
        
        # 4. Footer
        footer_frame = QFrame()
        footer_frame.setObjectName("footerFrame")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(12, 6, 12, 6)
        
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
        
        self.btn_close = QPushButton(t("burst_dialog.preview_close"))
        self.btn_close.setFixedHeight(34)
        self.btn_close.clicked.connect(self.close)
        
        footer_layout.addWidget(self.summary_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_close)
        
        main_layout.addWidget(footer_frame, stretch=0)
        self.update_summary_footer()

    def retranslate_ui(self):
        self.setWindowTitle(t("burst_dialog.title"))
        self.dir_label.setText(t("burst_dialog.target_folder"))
        self.btn_browse.setText(t("burst_dialog.browse"))
        self.chk_recursive.setText(t("burst_dialog.recursive"))
        self.time_label.setText(t("burst_dialog.interval_label"))
        self.blur_label.setText(t("burst_dialog.blur_label"))
        if not (self.worker and self.worker.isRunning()):
            self.btn_start.setText(t("burst_dialog.btn_search"))
        self.left_title.setText(t("burst_dialog.group_list_title"))
        self.btn_ungroup.setText(t("burst_dialog.dismiss_group"))
        self.btn_delete_group_items.setText(t("burst_dialog.trash_selected"))
        self.btn_close.setText(t("burst_dialog.preview_close"))
        self.update_group_list_ui()
        self.update_group_header_and_button()
        self.update_summary_footer()

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
            QLineEdit, QDoubleSpinBox {
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
                background-color: #2e7d32;
                font-weight: bold;
            }
            #btnStart:hover {
                background-color: #388e3c;
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
                background-color: #094771;
                color: #ffffff;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 4px;
            }
        """)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, t("burst_dialog.target_folder"), self.dir_edit.text())
        if dir_path:
            self.dir_edit.setText(dir_path)

    def toggle_search(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText(t("blur_dialog.cancelling"))
            return

        dir_path = self.dir_edit.text().strip()
        if not dir_path or not os.path.isdir(dir_path):
            QMessageBox.warning(self, t("dialog.error"), t("dialog.cannot_open", path=dir_path))
            return

        self.groups.clear()
        self.group_list.clear()
        self.clear_cards_grid()
        self.current_group_index = -1
        self.group_detail_header.setText(t("burst_dialog.select_group_prompt"))
        self.btn_delete_group_items.setEnabled(False)
        self.btn_ungroup.setEnabled(False)

        self.btn_start.setText(t("burst_dialog.btn_cancel"))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(t("blur_dialog.ready"))

        time_thresh = self.spin_time_thresh.value()
        blur_thresh = self.spin_blur_thresh.value()
        recursive = self.chk_recursive.isChecked()

        self.worker = BurstSearchWorker(dir_path, recursive, time_thresh, blur_thresh)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.result_signal.connect(self.on_worker_results)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
        self.status_label.setText(f"[{current}/{total}] {msg}")

    def on_worker_results(self, groups: list):
        self.groups = groups

    def on_worker_finished(self):
        self.btn_start.setText(t("burst_dialog.btn_search"))
        self.progress_bar.setVisible(False)

        if not self.groups:
            self.status_label.setText(t("burst_dialog.all_cleared"))
        else:
            total_items = sum(g.total_count for g in self.groups)
            self.status_label.setText(f"Found {len(self.groups)} group(s), {total_items} photo(s).")

        self.update_group_list_ui()
        if self.groups:
            self.group_list.setCurrentRow(0)

    def update_group_list_ui(self):
        self.group_list.clear()
        for idx, g in enumerate(self.groups):
            del_cnt = g.deletion_count
            item_text = f"Group {g.group_id} ({g.start_time_str}) - {g.total_count} photos [Keep 1 / Delete {del_cnt}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.group_list.addItem(item)

        self.update_summary_footer()

    def on_group_selected(self, row: int):
        if row < 0 or row >= len(self.groups):
            self.current_group_index = -1
            self.clear_cards_grid()
            self.group_detail_header.setText(t("burst_dialog.select_group_prompt"))
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)
            return

        self.current_group_index = row
        group = self.groups[row]
        self.display_group_cards(group)
        self.update_group_header_and_button()

    def clear_cards_grid(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def display_group_cards(self, group: BurstGroup):
        self.clear_cards_grid()
        cols = 2
        for i, item in enumerate(group.items):
            row = i // cols
            col = i % cols
            card = self.create_photo_card(item, group)
            self.cards_grid.addWidget(card, row, col)

    def create_photo_card(self, item: BurstPhotoItem, group: BurstGroup) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        
        if item.is_recommended_keep:
            card.setStyleSheet("""
                QFrame {
                    background-color: #1e3320;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame {
                    background-color: #2b2b2b;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        lbl_thumb = ClickableLabel()
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setFixedSize(380, 270)
        lbl_thumb.setStyleSheet("background-color: #151515; border-radius: 4px;")
        lbl_thumb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lbl_thumb.setToolTip(t("burst_dialog.card_click_preview"))
        lbl_thumb.clicked.connect(lambda it=item: self.open_preview(it))

        pixmap = QPixmap(item.image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(380, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_thumb.setPixmap(scaled)
        else:
            lbl_thumb.setText("No Image")

        layout.addWidget(lbl_thumb)

        fname = os.path.basename(item.image_path)
        lbl_name = QLabel(fname)
        lbl_name.setToolTip(item.image_path)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffffff;")
        layout.addWidget(lbl_name)

        score_layout = QHBoxLayout()
        lbl_score = QLabel(f"{t('burst_dialog.card_score')} {item.composite_score}")
        lbl_score.setStyleSheet("font-size: 12px; color: #2196F3; font-weight: bold;")
        
        if item.is_recommended_keep:
            lbl_badge = QLabel(t("burst_dialog.card_keep"))
            lbl_badge.setStyleSheet("background-color: #2e7d32; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        else:
            lbl_badge = QLabel(t("burst_dialog.card_trash"))
            lbl_badge.setStyleSheet("background-color: #e65100; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px;")

        score_layout.addWidget(lbl_score)
        score_layout.addStretch()
        score_layout.addWidget(lbl_badge)
        layout.addLayout(score_layout)

        btn_group = QButtonGroup(card)
        
        rb_keep = QRadioButton(t("burst_dialog.card_keep"))
        rb_trash = QRadioButton(t("burst_dialog.card_trash"))
        
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

        btn_preview = QPushButton(t("burst_dialog.card_click_preview"))
        btn_preview.setFixedHeight(28)
        btn_preview.setStyleSheet("font-size: 12px; padding: 4px;")
        btn_preview.clicked.connect(lambda checked=False, it=item: self.open_preview(it))
        layout.addWidget(btn_preview)

        return card

    def open_preview(self, item: BurstPhotoItem):
        dlg = ImagePreviewDialog(self, item)
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
            f"Group {group.group_id} ({group.start_time_str}) : Total {group.total_count} photos | Delete {del_cnt} ({format_size(del_size)})"
        )
        self.btn_delete_group_items.setEnabled(del_cnt > 0)
        self.btn_ungroup.setEnabled(True)

    def update_group_list_ui_quiet(self):
        curr = self.group_list.currentRow()
        for idx, g in enumerate(self.groups):
            del_cnt = g.deletion_count
            item_text = f"Group {g.group_id} ({g.start_time_str}) - {g.total_count} photos [Keep 1 / Delete {del_cnt}]"
            item = self.group_list.item(idx)
            if item:
                item.setText(item_text)
        if curr >= 0:
            self.group_list.setCurrentRow(curr)

    def update_summary_footer(self):
        total_groups = len(self.groups)
        total_items = sum(g.total_count for g in self.groups)
        self.summary_label.setText(
            f"Groups: {total_groups} (Total {total_items} photos)"
        )

    def ungroup_current_group(self):
        if self.current_group_index < 0 or self.current_group_index >= len(self.groups):
            return

        target_idx = self.current_group_index
        group = self.groups[target_idx]

        reply = QMessageBox.question(
            self, t("burst_dialog.dismiss_group"),
            f"Dismiss Group {group.group_id}?",
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
            self.group_detail_header.setText(t("burst_dialog.select_group_prompt"))
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
            QMessageBox.information(self, "Info", t("burst_dialog.no_trash_target"))
            return

        total_size = sum(os.path.getsize(it.image_path) for it in del_items if os.path.exists(it.image_path))

        msg = t("burst_dialog.group_trash_confirm", count=len(del_items), group_id=group.group_id) + f"\nSize: {format_size(total_size)}"
        reply = QMessageBox.question(
            self, t("burst_dialog.trash_selected"), msg,
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
            self.group_detail_header.setText(t("burst_dialog.select_group_prompt"))
            self.btn_delete_group_items.setEnabled(False)
            self.btn_ungroup.setEnabled(False)

        self.update_summary_footer()

        result_msg = t("burst_dialog.trash_success", count=success_count)
        if failed_count > 0:
            result_msg += f"\n({failed_count} items failed)"
        QMessageBox.information(self, "Done", result_msg)
