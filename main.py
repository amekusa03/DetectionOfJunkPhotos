import sys
import os
import datetime
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QSplitter, QStatusBar, QHeaderView,
    QCheckBox, QFrame, QMessageBox, QMenu, QInputDialog, QDoubleSpinBox,
    QComboBox
)
from BaseNodeObject import BaseNodeObject, FileNodeObject, DirectoryNodeObject, ImageNodeObject, format_size
from FilerRepository import FilerRepository
from BlurSearchDialog import BlurSearchDialog
from BurstPhotoDialog import BurstPhotoDialog
from SimilarPhotoDialog import SimilarPhotoDialog
from i18n import t, get_current_language, set_language, get_i18n_manager

def format_datetime(timestamp):
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)

class FilerMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app.title"))
        self.resize(1200, 750)
        
        self.repository = FilerRepository()
        self.current_directory_path = ""
        self.current_nodes = []
        self.selected_node = None
        
        # Navigation History
        self.history_back = []
        self.history_forward = []
        
        self.init_ui()
        self.apply_styles()
        
        get_i18n_manager().language_changed.connect(self.retranslate_ui)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(current_dir):
            self.navigate_to(current_dir)
        else:
            self.navigate_to("/")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # --- Top Navigation Bar ---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip(t("nav.back"))
        self.btn_back.setFixedWidth(40)
        self.btn_back.clicked.connect(self.navigate_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip(t("nav.forward"))
        self.btn_forward.setFixedWidth(40)
        self.btn_forward.clicked.connect(self.navigate_forward)

        self.btn_up = QPushButton("▲")
        self.btn_up.setToolTip(t("nav.up"))
        self.btn_up.setFixedWidth(40)
        self.btn_up.clicked.connect(self.navigate_up)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip(t("nav.refresh"))
        self.btn_refresh.setFixedWidth(40)
        self.btn_refresh.clicked.connect(self.refresh_directory)

        self.btn_new_folder = QPushButton("📁+")
        self.btn_new_folder.setToolTip(t("menu.new_folder"))
        self.btn_new_folder.setFixedWidth(40)
        self.btn_new_folder.clicked.connect(self.create_folder)

        self.btn_new_file = QPushButton("📄+")
        self.btn_new_file.setToolTip(t("menu.new_file"))
        self.btn_new_file.setFixedWidth(40)
        self.btn_new_file.clicked.connect(self.create_file_item)

        self.btn_blur_search = QPushButton(t("tool.blur_search"))
        self.btn_blur_search.setToolTip(t("tool.blur_search_tip"))
        self.btn_blur_search.clicked.connect(lambda: self.open_blur_search_dialog())

        self.btn_burst_search = QPushButton(t("tool.burst_search"))
        self.btn_burst_search.setToolTip(t("tool.burst_search_tip"))
        self.btn_burst_search.clicked.connect(lambda: self.open_burst_search_dialog())

        self.btn_similar_search = QPushButton(t("tool.similar_search"))
        self.btn_similar_search.setToolTip(t("tool.similar_search_tip"))
        self.btn_similar_search.clicked.connect(lambda: self.open_similar_search_dialog())

        self.path_bar = QLineEdit()
        self.path_bar.setPlaceholderText(t("nav.path_placeholder"))
        self.path_bar.returnPressed.connect(self.on_path_bar_entered)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(t("nav.filter_placeholder"))
        self.search_bar.setFixedWidth(180)
        self.search_bar.textChanged.connect(self.filter_table)

        # Language Switcher Combobox
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("日本語", "ja")
        self.lang_combo.addItem("English", "en")
        current_idx = 0 if get_current_language() == "ja" else 1
        self.lang_combo.setCurrentIndex(current_idx)
        self.lang_combo.setToolTip(t("app.language"))
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)

        top_bar.addWidget(self.btn_back)
        top_bar.addWidget(self.btn_forward)
        top_bar.addWidget(self.btn_up)
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_new_folder)
        top_bar.addWidget(self.btn_new_file)
        top_bar.addWidget(self.btn_blur_search)
        top_bar.addWidget(self.btn_burst_search)
        top_bar.addWidget(self.btn_similar_search)
        top_bar.addWidget(self.path_bar, stretch=1)
        top_bar.addWidget(self.search_bar)
        top_bar.addWidget(self.lang_combo)

        main_layout.addLayout(top_bar)

        # --- Splitter for Workspace Division ---
        self.splitter = QSplitter(Qt.Horizontal)

        # 1. Left Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.setup_sidebar_shortcuts()
        self.sidebar.itemClicked.connect(self.on_sidebar_clicked)
        self.splitter.addWidget(self.sidebar)

        # 2. Central Files Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.update_table_headers()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)

        self.splitter.addWidget(self.table)

        # 3. Right Details Panel
        self.details_panel = QFrame()
        self.details_panel.setObjectName("detailsPanel")
        self.setup_details_panel()
        self.splitter.addWidget(self.details_panel)

        self.splitter.setSizes([160, 620, 280])
        main_layout.addWidget(self.splitter)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("status.ready"))

    def update_table_headers(self):
        self.table.setHorizontalHeaderLabels([
            "",
            t("table.col_name"),
            t("table.col_type"),
            t("table.col_size"),
            t("table.col_mtime")
        ])

    def on_language_changed(self, index: int):
        lang = self.lang_combo.itemData(index)
        if lang:
            set_language(lang)

    def retranslate_ui(self):
        self.setWindowTitle(t("app.title"))
        self.btn_back.setToolTip(t("nav.back"))
        self.btn_forward.setToolTip(t("nav.forward"))
        self.btn_up.setToolTip(t("nav.up"))
        self.btn_refresh.setToolTip(t("nav.refresh"))
        self.btn_new_folder.setToolTip(t("menu.new_folder"))
        self.btn_new_file.setToolTip(t("menu.new_file"))
        self.btn_blur_search.setText(t("tool.blur_search"))
        self.btn_blur_search.setToolTip(t("tool.blur_search_tip"))
        self.btn_burst_search.setText(t("tool.burst_search"))
        self.btn_burst_search.setToolTip(t("tool.burst_search_tip"))
        self.btn_similar_search.setText(t("tool.similar_search"))
        self.btn_similar_search.setToolTip(t("tool.similar_search_tip"))
        self.path_bar.setPlaceholderText(t("nav.path_placeholder"))
        self.search_bar.setPlaceholderText(t("nav.filter_placeholder"))
        self.lang_combo.setToolTip(t("app.language"))

        # Retranslate sidebar
        self.setup_sidebar_shortcuts()
        self.highlight_sidebar_item(self.current_directory_path)

        # Retranslate table headers and reload type names
        self.update_table_headers()
        self.populate_table()

        # Retranslate details panel
        self.panel_title.setText(t("preview.title"))
        self.detail_select_checkbox.setText(t("preview.mark_selected"))
        self.blur_box_title.setText(t("preview.blur_box"))
        self.btn_recheck_blur.setText(t("preview.btn_check_blur"))
        self.btn_open_item.setText(t("menu.open"))
        self.btn_delete_item.setText(t("menu.trash"))
        if self.selected_node:
            self.show_details(self.selected_node)
        else:
            self.clear_details_panel()

        self.update_status_bar()

    def setup_sidebar_shortcuts(self):
        self.sidebar.clear()
        shortcuts = [
            (t("sidebar.home"), os.path.expanduser("~")),
            (t("sidebar.pictures"), os.path.expanduser("~/Pictures")),
            (t("sidebar.documents"), os.path.expanduser("~/Documents")),
            (t("sidebar.downloads"), os.path.expanduser("~/Downloads")),
            (t("sidebar.desktop"), os.path.expanduser("~/Desktop")),
            (t("sidebar.root"), "/"),
        ]

        for name, path in shortcuts:
            if os.path.exists(path):
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, path)
                self.sidebar.addItem(item)

    def setup_details_panel(self):
        layout = QVBoxLayout(self.details_panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.panel_title = QLabel(t("preview.title"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.panel_title.setFont(font)
        self.panel_title.setStyleSheet("color: #7aa2f7; margin-bottom: 4px;")
        self.panel_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.panel_title)

        self.detail_icon = QLabel("📁")
        icon_font = QFont()
        icon_font.setPointSize(48)
        self.detail_icon.setFont(icon_font)
        self.detail_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.detail_icon)

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px solid #24283b; border-radius: 8px; background-color: #101014;")
        self.image_preview.setFixedSize(200, 200)
        self.image_preview.setVisible(False)
        layout.addWidget(self.image_preview, alignment=Qt.AlignCenter)

        self.detail_name = QLabel(f"{t('preview.lbl_name')} -")
        self.detail_name.setWordWrap(True)
        self.detail_type = QLabel(f"{t('preview.lbl_type')} -")
        self.detail_size = QLabel(f"{t('preview.lbl_size')} -")
        self.detail_path = QLabel("Path: -")
        self.detail_path.setWordWrap(True)
        self.detail_created = QLabel("Created: -")
        self.detail_modified = QLabel(f"{t('preview.lbl_mtime')} -")

        layout.addWidget(self.detail_name)
        layout.addWidget(self.detail_type)
        layout.addWidget(self.detail_size)
        layout.addWidget(self.detail_path)
        layout.addWidget(self.detail_created)
        layout.addWidget(self.detail_modified)

        self.detail_select_checkbox = QCheckBox(t("preview.mark_selected"))
        self.detail_select_checkbox.setEnabled(False)
        self.detail_select_checkbox.toggled.connect(self.on_detail_select_toggled)
        layout.addWidget(self.detail_select_checkbox)

        # Blur Panel
        self.blur_panel = QFrame()
        self.blur_panel.setStyleSheet("""
            QFrame {
                background-color: #1a1b26;
                border: 1px solid #3b4261;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        blur_layout = QVBoxLayout(self.blur_panel)
        blur_layout.setSpacing(6)

        self.blur_box_title = QLabel(t("preview.blur_box"))
        self.blur_box_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.blur_box_title.setStyleSheet("color: #bb9af7;")
        blur_layout.addWidget(self.blur_box_title)

        self.detail_blur_status = QLabel(t("preview.blur_status"))
        self.detail_blur_score = QLabel(t("preview.blur_score"))
        self.detail_blur_faces = QLabel(t("preview.blur_faces"))

        blur_layout.addWidget(self.detail_blur_status)
        blur_layout.addWidget(self.detail_blur_score)
        blur_layout.addWidget(self.detail_blur_faces)

        th_layout = QHBoxLayout()
        self.th_label = QLabel("Threshold:")
        self.th_label.setStyleSheet("color: #a9b1d6; font-size: 11px;")
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(1.0, 5000.0)
        self.blur_threshold_spin.setValue(100.0)
        self.blur_threshold_spin.setSingleStep(10.0)
        self.blur_threshold_spin.setStyleSheet("background-color: #101014; color: #c0caf5; font-size: 11px;")

        self.btn_recheck_blur = QPushButton(t("preview.btn_check_blur"))
        self.btn_recheck_blur.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_recheck_blur.clicked.connect(self.on_recheck_blur_clicked)

        th_layout.addWidget(self.th_label)
        th_layout.addWidget(self.blur_threshold_spin)
        th_layout.addWidget(self.btn_recheck_blur)

        blur_layout.addLayout(th_layout)
        self.blur_panel.setVisible(False)
        layout.addWidget(self.blur_panel)

        layout.addStretch()

        self.btn_open_item = QPushButton(t("menu.open"))
        self.btn_open_item.setEnabled(False)
        self.btn_open_item.clicked.connect(self.on_open_clicked_from_details)
        layout.addWidget(self.btn_open_item)

        self.btn_delete_item = QPushButton(t("menu.trash"))
        self.btn_delete_item.setEnabled(False)
        self.btn_delete_item.setObjectName("deleteBtn")
        self.btn_delete_item.clicked.connect(self.on_delete_clicked_from_details)
        layout.addWidget(self.btn_delete_item)

    def apply_styles(self):
        qss = """
        QMainWindow {
            background-color: #1a1b26;
        }

        QWidget {
            color: #c0caf5;
            font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
            font-size: 13px;
        }

        QPushButton {
            background-color: #24283b;
            color: #c0caf5;
            border: 1px solid #3b4261;
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #2f354f;
            border-color: #7aa2f7;
        }
        QPushButton:pressed {
            background-color: #414868;
        }
        QPushButton:disabled {
            background-color: #16161e;
            color: #565f89;
            border-color: #24283b;
        }

        QPushButton#deleteBtn {
            background-color: #3d2432;
            color: #f7768e;
            border-color: #bb616a;
        }
        QPushButton#deleteBtn:hover {
            background-color: #582d43;
            border-color: #f7768e;
        }

        QLineEdit, QComboBox {
            background-color: #16161e;
            color: #c0caf5;
            border: 1px solid #3b4261;
            border-radius: 6px;
            padding: 6px 10px;
        }
        QLineEdit:focus, QComboBox:focus {
            border-color: #7aa2f7;
        }

        QFrame#detailsPanel {
            background-color: #16161e;
            border: 1px solid #24283b;
            border-radius: 8px;
        }
        QFrame#detailsPanel QLabel {
            color: #a9b1d6;
            font-size: 13px;
        }

        QCheckBox {
            spacing: 8px;
            color: #a9b1d6;
        }

        QListWidget#sidebar {
            background-color: #16161e;
            border: 1px solid #24283b;
            border-radius: 8px;
            outline: none;
            padding: 4px;
        }
        QListWidget#sidebar::item {
            height: 36px;
            padding-left: 8px;
            border-radius: 6px;
            margin-bottom: 2px;
        }
        QListWidget#sidebar::item:hover {
            background-color: #24283b;
            color: #7aa2f7;
        }
        QListWidget#sidebar::item:selected {
            background-color: #2e3c64;
            color: #7aa2f7;
            font-weight: bold;
        }

        QTableWidget {
            background-color: #16161e;
            border: 1px solid #24283b;
            border-radius: 8px;
            gridline-color: #1a1b26;
            outline: none;
        }
        QTableWidget::item {
            padding: 4px 8px;
        }
        QTableWidget::item:selected {
            background-color: #2e3c64;
            color: #c0caf5;
        }
        QHeaderView::section {
            background-color: #1f2335;
            color: #7aa2f7;
            padding: 6px;
            border: none;
            border-bottom: 2px solid #24283b;
            font-weight: bold;
        }

        QStatusBar {
            background-color: #16161e;
            color: #565f89;
            border-top: 1px solid #24283b;
        }
        """
        self.setStyleSheet(qss)

    def navigate_to(self, path: str, push_history: bool = True):
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            QMessageBox.warning(self, t("dialog.error"), t("dialog.cannot_open", path=abs_path))
            return

        if push_history and self.current_directory_path and self.current_directory_path != abs_path:
            self.history_back.append(self.current_directory_path)
            self.history_forward.clear()

        self.current_directory_path = abs_path
        self.path_bar.setText(self.current_directory_path)
        self.update_nav_buttons()

        dir_node = self.repository.get_directory_node(self.current_directory_path)
        self.current_nodes = dir_node.children

        def sort_key(node):
            is_dir = isinstance(node, DirectoryNodeObject)
            return (0 if is_dir else 1, node.name.lower())
        self.current_nodes.sort(key=sort_key)

        for node in self.current_nodes:
            node.updated.connect(self.on_node_updated)

        self.populate_table()
        self.clear_details_panel()
        self.highlight_sidebar_item(abs_path)
        self.update_status_bar()

    def populate_table(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)

        self.table.setRowCount(0)
        self.table.setRowCount(len(self.current_nodes))

        for row, node in enumerate(self.current_nodes):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked if node.is_selected else Qt.Unchecked)
            chk_item.setData(Qt.UserRole + 1, node)
            self.table.setItem(row, 0, chk_item)

            name_item = QTableWidgetItem(f"{node.icon} {node.name}")
            self.table.setItem(row, 1, name_item)

            type_item = QTableWidgetItem(node.type_name)
            self.table.setItem(row, 2, type_item)

            size_val = node.size if isinstance(node, FileNodeObject) else -1
            size_item = NumericTableWidgetItem(node.size_str, size_val)
            self.table.setItem(row, 3, size_item)

            mtime = node.modified_time
            date_str = format_datetime(mtime) if mtime > 0 else "-"
            date_item = NumericTableWidgetItem(date_str, mtime)
            self.table.setItem(row, 4, date_item)

        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def on_item_changed(self, item):
        if item.column() == 0:
            node = item.data(Qt.UserRole + 1)
            if node:
                node.is_selected = (item.checkState() == Qt.Checked)

    def on_node_updated(self, node):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole + 1) == node:
                item.setCheckState(Qt.Checked if node.is_selected else Qt.Unchecked)
                break
        self.table.blockSignals(False)

        if self.selected_node == node:
            self.detail_select_checkbox.blockSignals(True)
            self.detail_select_checkbox.setChecked(node.is_selected)
            self.detail_select_checkbox.blockSignals(False)

        self.update_status_bar()

    def on_table_selection_changed(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            self.clear_details_panel()
            return

        row = selected_ranges[0].topRow()
        item = self.table.item(row, 0)
        if item:
            node = item.data(Qt.UserRole + 1)
            if node:
                self.show_details(node)

    def on_cell_double_clicked(self, row, column):
        item = self.table.item(row, 0)
        if item:
            node = item.data(Qt.UserRole + 1)
            if isinstance(node, DirectoryNodeObject):
                self.navigate_to(node.path)
            elif isinstance(node, FileNodeObject):
                self.open_file(node.path)

    def show_details(self, node):
        self.selected_node = node
        has_preview = getattr(node, "has_preview", False)

        if has_preview:
            pixmap = QPixmap(node.path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(196, 196, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)
                self.image_preview.setVisible(True)
                self.detail_icon.setVisible(False)
            else:
                self.image_preview.clear()
                self.image_preview.setVisible(False)
                self.detail_icon.setText(node.icon)
                self.detail_icon.setVisible(True)
        else:
            self.image_preview.clear()
            self.image_preview.setVisible(False)
            self.detail_icon.setText(node.icon)
            self.detail_icon.setVisible(True)

        self.detail_name.setText(f"{t('preview.lbl_name')} {node.name}")
        self.detail_type.setText(f"{t('preview.lbl_type')} {node.type_name}")
        self.detail_size.setText(f"{t('preview.lbl_size')} {node.size_str}")
        self.detail_path.setText(f"Path: {node.path}")
        self.detail_created.setText(f"Created: {format_datetime(node.created_time)}")
        self.detail_modified.setText(f"{t('preview.lbl_mtime')} {format_datetime(node.modified_time)}")

        self.detail_select_checkbox.setEnabled(True)
        self.detail_select_checkbox.blockSignals(True)
        self.detail_select_checkbox.setChecked(node.is_selected)
        self.detail_select_checkbox.blockSignals(False)

        if isinstance(node, ImageNodeObject):
            self.blur_panel.setVisible(True)
            self.update_blur_panel_info(node, threshold=self.blur_threshold_spin.value())
        else:
            self.blur_panel.setVisible(False)

        self.btn_open_item.setEnabled(True)
        self.btn_delete_item.setEnabled(True)

    def update_blur_panel_info(self, node: ImageNodeObject, threshold: float = 100.0, force: bool = False):
        blur_res = node.detect_blur(threshold=threshold, force_recheck=force)
        if blur_res:
            if blur_res.is_blurry:
                self.detail_blur_status.setText(f"{t('preview.blur_status_fmt', status='<b style="color:#f7768e;">' + t('status.blurry') + ' 🔴</b>')}")
            else:
                self.detail_blur_status.setText(f"{t('preview.blur_status_fmt', status='<b style="color:#9ece6a;">' + t('status.sharp') + ' 🟢</b>')}")

            self.detail_blur_score.setText(f"{t('preview.blur_score_fmt', score=f'<b>{blur_res.overall_score:.2f}</b>')}")

            if blur_res.face_detected:
                self.detail_blur_faces.setText(f"{t('preview.blur_faces_fmt', count=blur_res.face_count)}")
            else:
                self.detail_blur_faces.setText(f"{t('preview.blur_faces_fmt', count=0)} ({t('blur_dialog.face_no')})")
        else:
            self.detail_blur_status.setText(f"{t('preview.blur_status_fmt', status=t('dialog.error'))}")
            self.detail_blur_score.setText(t("preview.blur_score"))
            self.detail_blur_faces.setText(t("preview.blur_faces"))

    def on_recheck_blur_clicked(self):
        if isinstance(self.selected_node, ImageNodeObject):
            th = self.blur_threshold_spin.value()
            self.update_blur_panel_info(self.selected_node, threshold=th, force=True)

    def clear_details_panel(self):
        self.selected_node = None
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.detail_icon.setText("📁")
        self.detail_icon.setVisible(True)

        self.detail_name.setText(f"{t('preview.lbl_name')} -")
        self.detail_type.setText(f"{t('preview.lbl_type')} -")
        self.detail_size.setText(f"{t('preview.lbl_size')} -")
        self.detail_path.setText("Path: -")
        self.detail_created.setText("Created: -")
        self.detail_modified.setText(f"{t('preview.lbl_mtime')} -")

        self.detail_select_checkbox.setChecked(False)
        self.detail_select_checkbox.setEnabled(False)

        self.blur_panel.setVisible(False)
        self.btn_open_item.setEnabled(False)
        self.btn_delete_item.setEnabled(False)

    def on_detail_select_toggled(self, checked: bool):
        if self.selected_node:
            self.selected_node.is_selected = checked

    def on_open_clicked_from_details(self):
        if self.selected_node:
            if isinstance(self.selected_node, DirectoryNodeObject):
                self.navigate_to(self.selected_node.path)
            elif isinstance(self.selected_node, FileNodeObject):
                self.open_file(self.selected_node.path)

    def on_delete_clicked_from_details(self):
        if self.selected_node:
            self.delete_node(self.selected_node)

    def open_file(self, path: str):
        url = QUrl.fromLocalFile(path)
        QDesktopServices.openUrl(url)

    def on_path_bar_entered(self):
        path = self.path_bar.text().strip()
        if os.path.exists(path) and os.path.isdir(path):
            self.navigate_to(path)
        else:
            QMessageBox.warning(self, t("dialog.error"), t("dialog.cannot_open", path=path))

    def filter_table(self, query: str):
        query = query.lower().strip()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            if name_item:
                visible = query in name_item.text().lower()
                self.table.setRowHidden(row, not visible)

    def navigate_back(self):
        if self.history_back:
            prev_dir = self.history_back.pop()
            if self.current_directory_path:
                self.history_forward.append(self.current_directory_path)
            self.navigate_to(prev_dir, push_history=False)

    def navigate_forward(self):
        if self.history_forward:
            next_dir = self.history_forward.pop()
            if self.current_directory_path:
                self.history_back.append(self.current_directory_path)
            self.navigate_to(next_dir, push_history=False)

    def navigate_up(self):
        if not self.current_directory_path:
            return
        parent_dir = os.path.dirname(self.current_directory_path)
        if os.path.exists(parent_dir) and parent_dir != self.current_directory_path:
            self.navigate_to(parent_dir)

    def refresh_directory(self):
        if self.current_directory_path and os.path.exists(self.current_directory_path):
            self.navigate_to(self.current_directory_path, push_history=False)

    def update_nav_buttons(self):
        self.btn_back.setEnabled(len(self.history_back) > 0)
        self.btn_forward.setEnabled(len(self.history_forward) > 0)
        parent_dir = os.path.dirname(self.current_directory_path)
        self.btn_up.setEnabled(bool(parent_dir and parent_dir != self.current_directory_path))

    def highlight_sidebar_item(self, path: str):
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            item_path = item.data(Qt.UserRole)
            if item_path == path:
                self.sidebar.setCurrentItem(item)
                return
        self.sidebar.clearSelection()

    def update_status_bar(self):
        total_items = len(self.current_nodes)
        selected_nodes = [n for n in self.current_nodes if n.is_selected]
        selected_count = len(selected_nodes)

        if selected_count > 0:
            total_size = sum(n.size for n in selected_nodes if isinstance(n, FileNodeObject))
            size_str = format_size(total_size)
            self.status_bar.showMessage(
                f"{t('status.item_count', count=total_items)} | {t('status.selected_count', count=selected_count)} ({size_str})"
            )
        else:
            self.status_bar.showMessage(t("status.item_count", count=total_items))

    def on_sidebar_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.navigate_to(path)

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)

        menu = QMenu(self)
        menu.setStyleSheet("""
        QMenu {
            background-color: #16161e;
            color: #c0caf5;
            border: 1px solid #24283b;
            border-radius: 6px;
            padding: 4px 0px;
        }
        QMenu::item {
            padding: 6px 22px;
        }
        QMenu::item:selected {
            background-color: #2e3c64;
            color: #7aa2f7;
        }
        QMenu::separator {
            height: 1px;
            background-color: #24283b;
            margin: 4px 0px;
        }
        """)

        node = None
        if item:
            row = item.row()
            chk_item = self.table.item(row, 0)
            if chk_item:
                node = chk_item.data(Qt.UserRole + 1)

        if node:
            action_open = menu.addAction(t("menu.open"))
            action_blur_check = None
            action_blur_search_dir = None
            if isinstance(node, ImageNodeObject):
                action_blur_check = menu.addAction(t("menu.check_blur"))
            elif isinstance(node, DirectoryNodeObject):
                action_blur_search_dir = menu.addAction(t("tool.blur_search"))

            action_rename = menu.addAction(t("menu.rename"))
            action_trash = menu.addAction(t("menu.trash"))
            action_delete_perm = menu.addAction(t("menu.delete_permanent"))
            menu.addSeparator()

            action_new_folder = menu.addAction(t("menu.new_folder"))
            action_new_file = menu.addAction(t("menu.new_file"))
            menu.addSeparator()
            action_refresh = menu.addAction(t("menu.refresh"))

            selected_action = menu.exec(self.table.mapToGlobal(pos))

            if selected_action == action_open:
                if isinstance(node, DirectoryNodeObject):
                    self.navigate_to(node.path)
                else:
                    self.open_file(node.path)
            elif action_blur_check and selected_action == action_blur_check:
                self.show_blur_dialog(node)
            elif action_blur_search_dir and selected_action == action_blur_search_dir:
                self.open_blur_search_dialog(node.path)
            elif selected_action == action_rename:
                self.rename_node(node)
            elif selected_action == action_trash:
                self.trash_node(node)
            elif selected_action == action_delete_perm:
                self.delete_node(node)
            elif selected_action == action_new_folder:
                self.create_folder()
            elif selected_action == action_new_file:
                self.create_file_item()
            elif selected_action == action_refresh:
                self.refresh_directory()
        else:
            action_blur_search_dir = menu.addAction(t("tool.blur_search"))
            action_new_folder = menu.addAction(t("menu.new_folder"))
            action_new_file = menu.addAction(t("menu.new_file"))
            menu.addSeparator()
            action_refresh = menu.addAction(t("menu.refresh"))

            selected_action = menu.exec(self.table.mapToGlobal(pos))

            if selected_action == action_blur_search_dir:
                self.open_blur_search_dialog(self.current_directory_path)
            elif selected_action == action_new_folder:
                self.create_folder()
            elif selected_action == action_new_file:
                self.create_file_item()
            elif selected_action == action_refresh:
                self.refresh_directory()

    def show_blur_dialog(self, node: ImageNodeObject):
        res = node.detect_blur(threshold=100.0, force_recheck=True)
        if not res:
            QMessageBox.warning(self, t("dialog.error"), t("dialog.cannot_open", path=node.name))
            return

        status = f"<font color='#f7768e'>{t('status.blurry')} 🔴</font>" if res.is_blurry else f"<font color='#9ece6a'>{t('status.sharp')} 🟢</font>"
        msg = f"<b>{t('blur_dialog.lbl_file')}</b> {node.name}<br>"
        msg += f"<b>{t('blur_dialog.lbl_judgment')}</b> {status}<br>"
        if hasattr(res, 'reason_text') and res.reason_text:
            msg += f"<b>{t('blur_dialog.lbl_reason')}</b> {res.reason_text}<br>"
        msg += f"<b>{t('blur_dialog.lbl_score')}</b> {res.overall_score:.2f} ({t('blur_dialog.threshold_label')} {res.threshold})<br>"
        if hasattr(res, 'max_grid_score'):
            msg += f"<b>{t('blur_dialog.lbl_max_grid')}</b> {res.max_grid_score:.2f}<br>"
        msg += f"<b>{t('blur_dialog.lbl_face')}</b> {t('blur_dialog.face_present', count=res.face_count) if res.face_detected else t('blur_dialog.face_none')}<br><br>"

        if res.faces:
            msg += "<b>--- Face Details ---</b><br>"
            for f in res.faces:
                st = f"<font color='#f7768e'>{t('status.blurry')}</font>" if f.is_blurry else f"<font color='#9ece6a'>{t('status.sharp')}</font>"
                msg += f"・Face {f.face_index}: Score {f.score:.2f} -> {st} (Box: {f.box})<br>"

        QMessageBox.information(self, f"{t('menu.check_blur')} - {node.name}", msg)

    def rename_node(self, node):
        new_name, ok = QInputDialog.getText(
            self, t("dialog.rename_title"), t("dialog.rename_label"), text=node.name
        )
        if ok and new_name.strip() and new_name.strip() != node.name:
            success = self.repository.rename_node(node.path, new_name.strip())
            if success:
                self.refresh_directory()
            else:
                QMessageBox.critical(self, t("dialog.error"), t("dialog.rename_failed"))

    def trash_node(self, node):
        reply = QMessageBox.question(
            self, t("dialog.trash_confirm_title"), t("dialog.trash_confirm_msg", count=1),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            success = self.repository.send_to_trash(node.path)
            if success:
                if self.selected_node == node:
                    self.clear_details_panel()
                self.refresh_directory()
            else:
                QMessageBox.critical(self, t("dialog.error"), t("dialog.delete_failed"))

    def delete_node(self, node):
        reply = QMessageBox.question(
            self, t("dialog.delete_confirm_title"), t("dialog.delete_confirm_msg", count=1),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.repository.delete_node(node.path)
            if success:
                if self.selected_node == node:
                    self.clear_details_panel()
                self.refresh_directory()
            else:
                QMessageBox.critical(self, t("dialog.error"), t("dialog.delete_failed"))

    def create_folder(self):
        folder_name, ok = QInputDialog.getText(
            self, t("dialog.new_folder_title"), t("dialog.new_folder_label")
        )
        if ok and folder_name.strip():
            success = self.repository.create_directory(self.current_directory_path, folder_name.strip())
            if success:
                self.refresh_directory()
            else:
                QMessageBox.critical(self, t("dialog.error"), t("dialog.create_failed"))

    def create_file_item(self):
        file_name, ok = QInputDialog.getText(
            self, t("dialog.new_file_title"), t("dialog.new_file_label")
        )
        if ok and file_name.strip():
            success = self.repository.create_file(self.current_directory_path, file_name.strip())
            if success:
                self.refresh_directory()
            else:
                QMessageBox.critical(self, t("dialog.error"), t("dialog.create_failed"))

    def open_blur_search_dialog(self, target_dir: str = None):
        if not target_dir:
            target_dir = self.current_directory_path or os.getcwd()
        dlg = BlurSearchDialog(self, initial_dir=target_dir)
        dlg.exec()

    def open_burst_search_dialog(self, target_dir: str = None):
        if not target_dir:
            target_dir = self.current_directory_path or os.getcwd()
        dlg = BurstPhotoDialog(self, initial_dir=target_dir)
        dlg.exec()
        self.refresh_directory()

    def open_similar_search_dialog(self, target_dir: str = None):
        if not target_dir:
            target_dir = self.current_directory_path or os.getcwd()
        dlg = SimilarPhotoDialog(self, initial_dir=target_dir)
        dlg.exec()
        self.refresh_directory()

    def select_file_by_path(self, file_path: str):
        file_path = os.path.abspath(file_path)
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item:
                node = chk_item.data(Qt.UserRole + 1)
                if node and os.path.abspath(node.path) == file_path:
                    self.table.selectRow(row)
                    self.table.scrollToItem(chk_item)
                    break

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FilerMainWindow()
    window.show()
    sys.exit(app.exec())
