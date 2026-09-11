import os
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QColor, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QDoubleSpinBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSplitter, QWidget, QFileDialog, QFrame
)
from FilerRepository import FilerRepository
from BlurDetector import BlurResult, FaceBlurDetail
from BaseNodeObject import ImageNodeObject, format_size
from i18n import t, get_i18n_manager

class BlurSearchWorker(QThread):
    progress_signal = Signal(int, int, str)  # current, total, current_file
    result_signal = Signal(list)            # List[BlurResult]
    item_found_signal = Signal(object)      # BlurResult
    finished_signal = Signal()

    def __init__(self, dir_path: str, recursive: bool, threshold: float):
        super().__init__()
        self.dir_path = dir_path
        self.recursive = recursive
        self.threshold = threshold
        self._is_cancelled = False
        self.repository = FilerRepository()

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def report_progress(self, current: int, total: int, current_file: str):
        self.progress_signal.emit(current, total, current_file)

    def run(self):
        results = self.repository.search_blurry_images(
            dir_path=self.dir_path,
            recursive=self.recursive,
            threshold=self.threshold,
            is_cancelled_func=self.is_cancelled,
            progress_callback=self.report_progress,
            found_callback=self.item_found_signal.emit
        )
        if not self._is_cancelled:
            self.result_signal.emit(results)
        self.finished_signal.emit()

class BlurSearchDialog(QDialog):
    def __init__(self, parent=None, initial_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("blur_dialog.title"))
        self.resize(950, 650)
        
        self.initial_dir = initial_dir or os.getcwd()
        self.worker = None
        self.results = []
        
        self.init_ui()
        self.apply_styles()
        
        get_i18n_manager().language_changed.connect(self.retranslate_ui)
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # 1. Config Panel
        config_frame = QFrame()
        config_frame.setObjectName("configFrame")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 12, 12, 12)
        config_layout.setSpacing(10)
        
        # Directory Selection Row
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(t("blur_dialog.target_folder"))
        self.dir_label.setStyleSheet("font-weight: bold;")
        self.dir_edit = QLineEdit(self.initial_dir)
        self.btn_browse = QPushButton(t("blur_dialog.browse"))
        self.btn_browse.setFixedWidth(90)
        self.btn_browse.clicked.connect(self.browse_directory)
        
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.btn_browse)
        config_layout.addLayout(dir_layout)
        
        # Options Row
        opts_layout = QHBoxLayout()
        
        self.chk_recursive = QCheckBox(t("blur_dialog.recursive"))
        self.chk_recursive.setChecked(True)
        
        self.thresh_label = QLabel(t("blur_dialog.threshold_label"))
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(1.0, 5000.0)
        self.spin_threshold.setValue(100.0)
        self.spin_threshold.setSingleStep(10.0)
        self.spin_threshold.setFixedWidth(100)
        
        self.btn_search = QPushButton(t("blur_dialog.btn_search"))
        self.btn_search.setObjectName("btnSearch")
        self.btn_search.setFixedHeight(32)
        self.btn_search.clicked.connect(self.start_search)
        
        self.btn_cancel = QPushButton(t("blur_dialog.btn_cancel"))
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_search)
        
        opts_layout.addWidget(self.chk_recursive)
        opts_layout.addSpacing(20)
        opts_layout.addWidget(self.thresh_label)
        opts_layout.addWidget(self.spin_threshold)
        opts_layout.addStretch()
        opts_layout.addWidget(self.btn_search)
        opts_layout.addWidget(self.btn_cancel)
        
        config_layout.addLayout(opts_layout)
        main_layout.addWidget(config_frame)
        
        # 2. Progress
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        
        self.lbl_status = QLabel(t("blur_dialog.initial_status"))
        self.lbl_status.setStyleSheet("color: #a9b1d6;")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.lbl_status)
        main_layout.addLayout(progress_layout)
        
        # 3. Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.update_table_headers()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        splitter.addWidget(self.table)
        
        # Preview / Details
        preview_panel = QFrame()
        preview_panel.setObjectName("previewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        
        self.lbl_preview_title = QLabel(t("preview.title"))
        self.lbl_preview_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #7aa2f7;")
        
        self.lbl_image_preview = QLabel(t("blur_dialog.select_image"))
        self.lbl_image_preview.setAlignment(Qt.AlignCenter)
        self.lbl_image_preview.setStyleSheet("border: 1px dashed #414868; background-color: #16161e; border-radius: 6px;")
        self.lbl_image_preview.setMinimumSize(220, 200)
        
        self.lbl_detail_info = QLabel("")
        self.lbl_detail_info.setWordWrap(True)
        self.lbl_detail_info.setAlignment(Qt.AlignTop)
        
        btn_action_layout = QVBoxLayout()
        self.btn_open_file = QPushButton(t("blur_dialog.btn_open"))
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.clicked.connect(self.open_selected_file)
        
        self.btn_show_in_main = QPushButton(t("blur_dialog.btn_show_in_main"))
        self.btn_show_in_main.setEnabled(False)
        self.btn_show_in_main.clicked.connect(self.navigate_main_window)
        
        self.btn_detail_dialog = QPushButton(t("blur_dialog.btn_detail"))
        self.btn_detail_dialog.setEnabled(False)
        self.btn_detail_dialog.clicked.connect(self.show_detail_dialog)
        
        btn_action_layout.addWidget(self.btn_open_file)
        btn_action_layout.addWidget(self.btn_show_in_main)
        btn_action_layout.addWidget(self.btn_detail_dialog)
        
        preview_layout.addWidget(self.lbl_preview_title)
        preview_layout.addWidget(self.lbl_image_preview, 1)
        preview_layout.addWidget(self.lbl_detail_info)
        preview_layout.addLayout(btn_action_layout)
        
        splitter.addWidget(preview_panel)
        splitter.setSizes([600, 320])
        
        main_layout.addWidget(splitter, 1)

    def update_table_headers(self):
        self.table.setHorizontalHeaderLabels([
            t("blur_dialog.col_file"),
            t("blur_dialog.col_score"),
            t("blur_dialog.col_face"),
            t("blur_dialog.col_path")
        ])

    def retranslate_ui(self):
        self.setWindowTitle(t("blur_dialog.title"))
        self.dir_label.setText(t("blur_dialog.target_folder"))
        self.btn_browse.setText(t("blur_dialog.browse"))
        self.chk_recursive.setText(t("blur_dialog.recursive"))
        self.thresh_label.setText(t("blur_dialog.threshold_label"))
        self.btn_search.setText(t("blur_dialog.btn_search"))
        self.btn_cancel.setText(t("blur_dialog.btn_cancel"))
        self.lbl_preview_title.setText(t("preview.title"))
        self.btn_open_file.setText(t("blur_dialog.btn_open"))
        self.btn_show_in_main.setText(t("blur_dialog.btn_show_in_main"))
        self.btn_detail_dialog.setText(t("blur_dialog.btn_detail"))
        self.update_table_headers()
        self.on_selection_changed()

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1b26;
                color: #c0caf5;
            }
            QFrame#configFrame, QFrame#previewPanel {
                background-color: #24283b;
                border-radius: 8px;
            }
            QLabel {
                color: #c0caf5;
            }
            QLineEdit, QDoubleSpinBox {
                background-color: #16161e;
                border: 1px solid #414868;
                border-radius: 4px;
                padding: 4px 8px;
                color: #c0caf5;
            }
            QCheckBox {
                color: #c0caf5;
            }
            QPushButton {
                background-color: #2e3c64;
                color: #7aa2f7;
                border: 1px solid #3d59a1;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d59a1;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1a1b26;
                color: #565f89;
                border: 1px solid #24283b;
            }
            QPushButton#btnSearch {
                background-color: #7aa2f7;
                color: #15161e;
            }
            QPushButton#btnSearch:hover {
                background-color: #bb9af7;
            }
            QPushButton#btnCancel {
                background-color: #f7768e;
                color: #15161e;
            }
            QPushButton#btnCancel:hover {
                background-color: #ff9e3b;
            }
            QProgressBar {
                border: 1px solid #414868;
                border-radius: 4px;
                text-align: center;
                background-color: #16161e;
                color: #c0caf5;
            }
            QProgressBar::chunk {
                background-color: #7aa2f7;
                border-radius: 3px;
            }
            QTableWidget {
                background-color: #1a1b26;
                color: #c0caf5;
                gridline-color: #24283b;
                border: 1px solid #24283b;
                border-radius: 6px;
            }
            QTableWidget::item:selected {
                background-color: #2e3c64;
                color: #7aa2f7;
            }
            QHeaderView::section {
                background-color: #1f2335;
                color: #7aa2f7;
                padding: 6px;
                border: 1px solid #24283b;
                font-weight: bold;
            }
        """)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, t("blur_dialog.target_folder"), self.dir_edit.text())
        if dir_path:
            self.dir_edit.setText(dir_path)

    def start_search(self):
        dir_path = self.dir_edit.text().strip()
        if not dir_path or not os.path.isdir(dir_path):
            QMessageBox.warning(self, t("dialog.error"), t("dialog.cannot_open", path=dir_path))
            return
            
        self.btn_search.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.table.setRowCount(0)
        self.results = []
        self.clear_preview()
        
        self.progress_bar.setValue(0)
        self.lbl_status.setText(t("blur_dialog.ready"))
        
        recursive = self.chk_recursive.isChecked()
        threshold = self.spin_threshold.value()
        
        self.worker = BlurSearchWorker(dir_path, recursive, threshold)
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.item_found_signal.connect(self.on_item_found)
        self.worker.result_signal.connect(self.on_results_received)
        self.worker.finished_signal.connect(self.on_search_finished)
        self.worker.start()

    def cancel_search(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText(t("blur_dialog.cancelling"))
            self.btn_cancel.setEnabled(False)

    def on_progress(self, current: int, total: int, current_file: str):
        if total > 0:
            val = int((current / total) * 100)
            self.progress_bar.setValue(val)
            rel_path = os.path.basename(current_file)
            found_count = len(self.results)
            self.lbl_status.setText(t("blur_dialog.scanning", current=current, total=total, found=found_count, file=rel_path))

    def _add_result_row(self, res: BlurResult):
        base_dir = self.dir_edit.text().strip()
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        filename = os.path.basename(res.image_path)
        item_name = QTableWidgetItem(f"🔴 {filename}")
        item_name.setData(Qt.UserRole, res)
        
        item_score = QTableWidgetItem(f"{res.overall_score:.2f}")
        item_score.setTextAlignment(Qt.AlignCenter)
        
        face_str = t("blur_dialog.face_present", count=res.face_count) if res.face_detected else t("blur_dialog.face_none")
        item_face = QTableWidgetItem(face_str)
        item_face.setTextAlignment(Qt.AlignCenter)
        
        try:
            rel_path = os.path.relpath(res.image_path, base_dir)
        except Exception:
            rel_path = res.image_path
        item_path = QTableWidgetItem(rel_path)
        
        self.table.setItem(row, 0, item_name)
        self.table.setItem(row, 1, item_score)
        self.table.setItem(row, 2, item_face)
        self.table.setItem(row, 3, item_path)

    def on_item_found(self, res: BlurResult):
        self.results.append(res)
        self._add_result_row(res)

    def on_results_received(self, results: list):
        self.results = results
        if self.table.rowCount() == 0 and len(results) > 0:
            for res in results:
                self._add_result_row(res)

    def on_search_finished(self):
        self.btn_search.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        count = len(self.results)
        
        if self.worker and self.worker.is_cancelled():
            self.lbl_status.setText(t("blur_dialog.finished_cancelled", count=count))
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setValue(100)
            self.lbl_status.setText(t("blur_dialog.finished_done", count=count))

    def get_selected_result(self) -> BlurResult:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def on_selection_changed(self):
        res = self.get_selected_result()
        if not res:
            self.clear_preview()
            return
            
        self.btn_open_file.setEnabled(True)
        self.btn_show_in_main.setEnabled(True)
        self.btn_detail_dialog.setEnabled(True)
        
        pixmap = QPixmap(res.image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.lbl_image_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.lbl_image_preview.setPixmap(scaled)
        else:
            self.lbl_image_preview.setText(t("blur_dialog.preview_fail"))
            
        info = f"<b>{t('blur_dialog.lbl_file')}</b> {os.path.basename(res.image_path)}<br>"
        status_color = "#f7768e" if res.is_blurry else "#9ece6a"
        info += f"<b>{t('blur_dialog.lbl_judgment')}</b> <font color='{status_color}'><b>{res.status_text} {'🔴' if res.is_blurry else '🟢'}</b></font><br>"
        if getattr(res, "reason_text", ""):
            info += f"<b>{t('blur_dialog.lbl_reason')}</b> {res.reason_text}<br>"
        info += f"<b>{t('blur_dialog.lbl_score')}</b> {res.overall_score:.2f} (Threshold: {res.threshold})<br>"
        if hasattr(res, "max_grid_score"):
            info += f"<b>{t('blur_dialog.lbl_max_grid')}</b> {res.max_grid_score:.2f}<br>"
        if res.face_detected:
            info += f"<b>{t('blur_dialog.lbl_face')}</b> {t('blur_dialog.face_yes', count=res.face_count)}<br>"
        else:
            info += f"<b>{t('blur_dialog.lbl_face')}</b> {t('blur_dialog.face_no')}<br>"
            
        self.lbl_detail_info.setText(info)

    def clear_preview(self):
        self.lbl_image_preview.clear()
        self.lbl_image_preview.setText(t("blur_dialog.select_image"))
        self.lbl_detail_info.setText("")
        self.btn_open_file.setEnabled(False)
        self.btn_show_in_main.setEnabled(False)
        self.btn_detail_dialog.setEnabled(False)

    def on_item_double_clicked(self, item):
        res = self.get_selected_result()
        if res:
            self.navigate_main_window()

    def open_selected_file(self):
        res = self.get_selected_result()
        if res and os.path.exists(res.image_path):
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(res.image_path))

    def navigate_main_window(self):
        res = self.get_selected_result()
        if res and self.parent():
            parent_dir = os.path.dirname(res.image_path)
            if hasattr(self.parent(), 'navigate_to'):
                self.parent().navigate_to(parent_dir)
                if hasattr(self.parent(), 'select_file_by_path'):
                    self.parent().select_file_by_path(res.image_path)
            self.accept()

    def show_detail_dialog(self):
        res = self.get_selected_result()
        if res and self.parent() and hasattr(self.parent(), 'show_blur_dialog'):
            node = ImageNodeObject(res.image_path)
            self.parent().show_blur_dialog(node)
