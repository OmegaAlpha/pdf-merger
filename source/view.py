import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QFileDialog,
    QLineEdit,
    QLabel,
    QHeaderView,
    QAbstractItemView,
    QStatusBar,
    QMessageBox,
    QProgressBar,
    QStyle,
    QGridLayout,
    QSplitter,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QIcon, QPixmap, QImage

from viewmodel import MainViewModel

class MainWindow(QMainWindow):
    def __init__(self, viewmodel: MainViewModel):
        super().__init__()
        self.vm = viewmodel
        self.setWindowTitle("PDF Merger (MVVM)")
        self.setMinimumSize(QSize(900, 500))
        self.resize(1000, 600)
        self.setAcceptDrops(True)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self._setup_ui()
        self._bind_viewmodel()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files = [url.toLocalFile() for url in urls if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf')]
            if files:
                self.vm.set_last_open_dir(os.path.dirname(files[0]))
                self.vm.add_pdfs(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _setup_ui(self):
        # Table view setup
        self.pdf_table = QTableView()
        self.pdf_table.setModel(self.vm.pdf_list_model)
        header = self.pdf_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        
        self.pdf_table.setColumnWidth(2, 150)
        
        self._is_resizing_header = False
        header.sectionResized.connect(self._on_section_resized)
        
        self.pdf_table._original_resizeEvent = self.pdf_table.resizeEvent
        self.pdf_table.resizeEvent = self._on_table_resize

        self.pdf_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Drag and Drop internally handled by model
        self.pdf_table.setDragEnabled(True)
        self.pdf_table.setAcceptDrops(True)
        self.pdf_table.setDropIndicatorShown(True)
        self.pdf_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.pdf_table.setDragDropOverwriteMode(False)
        self.pdf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pdf_table.setSortingEnabled(True)
        self._clear_sort_indicator()
        
        # Table Container for Overlay
        table_container = QWidget()
        table_layout = QGridLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.pdf_table, 0, 0)
        
        self.empty_label = QLabel("Drag and drop PDF files here\nor click 'Add PDFs' to begin")
        self.empty_label.setObjectName("emptyStateLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        table_layout.addWidget(self.empty_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        self.splitter.addWidget(table_container)
        
        self.preview_pane = QWidget()
        preview_layout = QVBoxLayout(self.preview_pane)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_label = QLabel("Page Previews")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(preview_label)
        
        self.preview_list = QListWidget()
        self.preview_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.preview_list.setIconSize(QSize(150, 200))
        self.preview_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.preview_list.setUniformItemSizes(True)
        self.preview_list.setSpacing(10)
        preview_layout.addWidget(self.preview_list)
        
        self.splitter.addWidget(self.preview_pane)
        
        # Restore splitter state
        settings = QSettings("PDFMerger", "PDFMergerApp")
        splitter_state = settings.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)
        else:
            self.splitter.setSizes([500, 350])
            
        preview_visible = settings.value("preview_visible", True, type=bool)
        self.preview_pane.setVisible(preview_visible)

        # Restore window geometry
        geometry = settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restore table header state
        header_state = settings.value("header_state")
        if header_state:
            self.pdf_table.horizontalHeader().restoreState(header_state)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(" Add PDFs")
        self.add_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        
        self.remove_btn = QPushButton(" Remove Selected")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        
        self.toggle_preview_btn = QPushButton(" Hide Preview" if preview_visible else " Show Preview")
        self.toggle_preview_btn.setCheckable(True)
        self.toggle_preview_btn.setChecked(preview_visible)
        
        self.merge_btn = QPushButton(" Merge PDFs")
        self.merge_btn.setObjectName("mergeButton")
        self.merge_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.toggle_preview_btn)
        btn_layout.addWidget(self.merge_btn)
        self.layout.addLayout(btn_layout)

        # Output Layout
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output File:"))
        self.output_name = QLineEdit("")
        
        output_layout.addWidget(self.output_name)
        self.output_dir_btn = QPushButton(" Set Output Directory")
        self.output_dir_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        output_layout.addWidget(self.output_dir_btn)
        self.layout.addLayout(output_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        self.setStatusBar(QStatusBar(self))
        self.vm.set_output_dir(self.vm.output_dir)

    def _on_table_resize(self, event):
        self.pdf_table._original_resizeEvent(event)
        
        header = self.pdf_table.horizontalHeader()
        if header.count() == 0:
            return
            
        viewport_width = self.pdf_table.viewport().width()
        
        other_widths = 0
        for i in range(header.count()):
            if i != 0:
                other_widths += header.sectionSize(i)
                
        new_width = viewport_width - other_widths
        if new_width < header.minimumSectionSize():
            new_width = header.minimumSectionSize()
            
        self._is_resizing_header = True
        header.resizeSection(0, new_width)
        self._is_resizing_header = False

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        if self._is_resizing_header:
            return
            
        header = self.pdf_table.horizontalHeader()
        visual_index = header.visualIndex(logicalIndex)
        
        if visual_index >= header.count() - 1:
            return
            
        next_logical = header.logicalIndex(visual_index + 1)
        
        if header.sectionResizeMode(next_logical) == QHeaderView.ResizeMode.Stretch:
            return
            
        delta = newSize - oldSize
        next_old_size = header.sectionSize(next_logical)
        next_new_size = next_old_size - delta
        
        min_size = header.minimumSectionSize()
        if next_new_size < min_size:
            next_new_size = min_size
            allowed_delta = next_old_size - min_size
            newSize = oldSize + allowed_delta
            
            self._is_resizing_header = True
            header.resizeSection(logicalIndex, newSize)
            header.resizeSection(next_logical, next_new_size)
            self._is_resizing_header = False
        else:
            self._is_resizing_header = True
            header.resizeSection(next_logical, next_new_size)
            self._is_resizing_header = False

    def _bind_viewmodel(self):
        # View bindings (UI events to ViewModel methods)
        self.add_btn.clicked.connect(self.on_add_pdfs)
        self.remove_btn.clicked.connect(self.on_remove_pdfs)
        self.merge_btn.clicked.connect(self.on_merge)
        self.output_dir_btn.clicked.connect(self.on_set_output_dir)
        self.toggle_preview_btn.toggled.connect(self.on_toggle_preview)
        
        self.pdf_table.selectionModel().selectionChanged.connect(self.on_table_selection_changed)

        # ViewModel bindings (Signals to UI updates)
        self.vm.status_message.connect(self.on_status_message)
        self.vm.merge_started.connect(self.on_merge_started)
        self.vm.merge_completed.connect(self.on_merge_completed)
        self.vm.output_dir_changed.connect(self.on_output_dir_changed)
        self.vm.thumbnail_started.connect(self.on_thumbnail_started)
        self.vm.thumbnail_ready.connect(self.on_thumbnail_ready)

        # Empty state bindings
        self.vm.pdf_list_model.rowsInserted.connect(self._on_rows_inserted)
        self.vm.pdf_list_model.rowsRemoved.connect(self._update_empty_state)
        self.vm.pdf_list_model.modelReset.connect(self._update_empty_state)
        self._update_empty_state()
        
        self.vm.pdf_list_model.order_broken.connect(self._clear_sort_indicator)

    def _clear_sort_indicator(self):
        self.pdf_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    def _on_rows_inserted(self, parent, first, last):
        self._update_empty_state()
        if first == 0 and self.vm.pdf_list_model.rowCount() > 0:
            first_pdf = self.vm.pdf_list_model.pdfs[0]
            name, ext = os.path.splitext(first_pdf.name)
            self.output_name.setText(f"{name}_merged{ext}")

    def _update_empty_state(self):
        if self.vm.pdf_list_model.rowCount() > 0:
            self.empty_label.hide()
        else:
            self.empty_label.show()

    def on_add_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", self.vm.last_open_dir, "PDF Files (*.pdf)"
        )
        if files:
            self.vm.set_last_open_dir(os.path.dirname(files[0]))
            self.vm.add_pdfs(files)

    def on_remove_pdfs(self):
        # We need to map the selected indices
        indexes = self.pdf_table.selectionModel().selectedRows()
        row_indices = [idx.row() for idx in indexes]
        if not row_indices:
            self.statusBar().showMessage("No rows selected.", 3000)
            return
        
        self.vm.remove_pdfs_by_indices(row_indices)

    def on_merge(self):
        dest_filename = self.output_name.text().strip() or "merged_output.pdf"
        output_path = os.path.join(self.vm.output_dir, dest_filename)

        if os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                f"File exists:\n{output_path}\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self.statusBar().showMessage("Merge cancelled.", 3000)
                return

        self.vm.start_merge(dest_filename)

    def on_table_selection_changed(self, selected, deselected):
        indexes = self.pdf_table.selectionModel().selectedRows()
        if not indexes:
            self.preview_list.clear()
            return
            
        if self.preview_pane.isVisible():
            row = indexes[0].row()
            pdf = self.vm.pdf_list_model.pdfs[row]
            self.vm.request_thumbnails(pdf.file_path)

    def on_thumbnail_started(self):
        self.preview_list.clear()

    def on_thumbnail_ready(self, page_num: int, image: QImage):
        pixmap = QPixmap.fromImage(image)
        icon = QIcon(pixmap)
        item = QListWidgetItem(icon, f"Page {page_num + 1}")
        self.preview_list.addItem(item)
        
    def on_toggle_preview(self, checked):
        self.preview_pane.setVisible(checked)
        self.toggle_preview_btn.setText(" Hide Preview" if checked else " Show Preview")
        
        if checked:
            indexes = self.pdf_table.selectionModel().selectedRows()
            if indexes:
                row = indexes[0].row()
                pdf = self.vm.pdf_list_model.pdfs[row]
                self.vm.request_thumbnails(pdf.file_path)

    def on_set_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.vm.output_dir
        )
        if directory:
            self.vm.set_output_dir(directory)

    # Signal handlers
    def on_output_dir_changed(self, directory: str):
        self.output_dir_btn.setToolTip(f"Current Output Dir:\n{directory}")

    def on_status_message(self, message: str, timeout: int):
        self.statusBar().showMessage(message, timeout)

    def on_merge_started(self):
        self.add_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.merge_btn.setEnabled(False)
        self.pdf_table.setEnabled(False)
        
        self.progress_bar.show()

    def on_merge_completed(self, success: bool, message: str):
        self.add_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)
        self.pdf_table.setEnabled(True)
        
        self.progress_bar.hide()
        
        if success:
            QMessageBox.information(self, "Merge Successful", message)
        else:
            QMessageBox.critical(self, "Merge Error", message)

    def closeEvent(self, event):
        settings = QSettings("PDFMerger", "PDFMergerApp")
        settings.setValue("splitter_state", self.splitter.saveState())
        settings.setValue("preview_visible", self.preview_pane.isVisible())
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("header_state", self.pdf_table.horizontalHeader().saveState())
        super().closeEvent(event)
