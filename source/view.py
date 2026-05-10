import os
from datetime import datetime
from PySide6.QtWidgets import (
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
    QMenu,
)
from PySide6.QtCore import Qt, QSize, QSettings, QTimer
from PySide6.QtGui import QIcon, QPixmap, QImage, QAction

from viewmodel import MainViewModel
from bookmark_editor import BookmarkEditorDialog
from settings_dialog import SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self, viewmodel: MainViewModel, theme_manager=None):
        super().__init__()
        self.vm = viewmodel
        self.theme_manager = theme_manager
        self._current_project_path = None
        self._app_title = "PDF Merger"
        self.setWindowTitle(self._app_title)
        self.setMinimumSize(QSize(900, 500))
        self.setAcceptDrops(True)

        # Debouncing for selection changes
        self.selection_timer = QTimer(self)
        self.selection_timer.setSingleShot(True)
        self.selection_timer.setInterval(200) # 200ms debounce
        self.selection_timer.timeout.connect(self._on_selection_timer_timeout)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self._setup_menubar()
        self._setup_ui()
        self._bind_viewmodel()
        
        if self.theme_manager:
            self.theme_manager.apply_window_theme(self)

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
                self.add_btn.setEnabled(False)
                self.vm.add_pdfs(files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _setup_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_project_action = QAction("Open Project...", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.on_open_project)
        file_menu.addAction(open_project_action)

        save_project_action = QAction("Save Project", self)
        save_project_action.setShortcut("Ctrl+S")
        save_project_action.triggered.connect(self.on_save_project)
        file_menu.addAction(save_project_action)

        save_as_action = QAction("Save Project As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.on_save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()
        
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.on_settings_open)
        file_menu.addAction(settings_action)

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

        # Context menu
        self.pdf_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pdf_table.customContextMenuRequested.connect(self._on_table_context_menu)
        
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
        self.preview_list.setIconSize(QSize(150, 220)) # Added 20px height for spacing
        self.preview_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.preview_list.setUniformItemSizes(True)
        self.preview_list.setSpacing(10)
        self.preview_list.setGridSize(QSize(170, 255)) # Accommodate larger icon area + text
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
        
        self.edit_bookmarks_btn = QPushButton(" Edit Bookmarks")
        self.edit_bookmarks_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.edit_bookmarks_btn.setEnabled(False)
        
        self.merge_btn = QPushButton(" Merge PDFs")
        self.merge_btn.setObjectName("mergeButton")
        self.merge_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.edit_bookmarks_btn)
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
        self.edit_bookmarks_btn.clicked.connect(self.on_edit_bookmarks)
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
        self.vm.thumbnail_batch_ready.connect(self.on_thumbnail_batch_ready)
        self.vm.thumbnail_cache_ready.connect(self.on_thumbnail_cache_ready)
        self.vm.pdfs_added.connect(self.on_pdfs_added_finished)
        self.vm.toc_ready.connect(self.on_toc_ready)

        # Empty state bindings
        self.vm.pdf_list_model.rowsInserted.connect(self._on_rows_inserted)
        self.vm.pdf_list_model.rowsRemoved.connect(self._update_empty_state)
        self.vm.pdf_list_model.modelReset.connect(self._update_empty_state)
        self._update_empty_state()
        
        self.vm.pdf_list_model.order_broken.connect(self._clear_sort_indicator)

        # Project signals
        self.vm.project_loaded.connect(self._on_project_loaded)
        self.vm.project_saved.connect(self._on_project_saved)
        self.vm.project_load_warning.connect(self._on_project_load_warning)

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
            self.add_btn.setEnabled(False) # Prevent multiple simultaneous loads
            self.vm.add_pdfs(files)

    def on_pdfs_added_finished(self, added: int, errors: int):
        self.add_btn.setEnabled(True)
        self._update_empty_state()

    def on_remove_pdfs(self):
        # We need to map the selected indices
        indexes = self.pdf_table.selectionModel().selectedRows()
        row_indices = [idx.row() for idx in indexes]
        if not row_indices:
            self.statusBar().showMessage("No rows selected.", 3000)
            return
        
        self.vm.remove_pdfs_by_indices(row_indices)

    # --- Context Menu ---

    def _on_table_context_menu(self, position):
        """Show a context menu for the PDF table."""
        indexes = self.pdf_table.selectionModel().selectedRows()
        if not indexes:
            return

        menu = QMenu(self)

        # Refresh / Update PDF(s)
        if len(indexes) == 1:
            refresh_action = menu.addAction("Update PDF from Disk")
            refresh_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
            
            relocate_action = menu.addAction("Relocate/Change PDF...")
            relocate_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        else:
            refresh_action = menu.addAction(f"Update {len(indexes)} PDFs from Disk")
            refresh_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
            relocate_action = None

        menu.addSeparator()

        # Edit Bookmarks (single selection only)
        edit_bm_action = None
        if len(indexes) == 1:
            row = indexes[0].row()
            pdf = self.vm.pdf_list_model.pdfs[row]
            edit_bm_action = menu.addAction("Edit Bookmarks...")
            edit_bm_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            if pdf.missing:
                edit_bm_action.setEnabled(False)
            menu.addSeparator()

        # Remove
        if len(indexes) == 1:
            remove_action = menu.addAction("Remove")
        else:
            remove_action = menu.addAction(f"Remove {len(indexes)} PDFs")
        remove_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        # Execute
        action = menu.exec(self.pdf_table.viewport().mapToGlobal(position))
        if action is None:
            return

        if action == refresh_action:
            self._on_refresh_selected_pdfs(indexes)
        elif action == relocate_action:
            self._on_change_pdf_path(indexes[0].row())
        elif action == edit_bm_action:
            self.on_edit_bookmarks()
        elif action == remove_action:
            self.on_remove_pdfs()

    def _on_change_pdf_path(self, row: int):
        """Prompt user to select a new path for a PDF entry."""
        if not (0 <= row < self.vm.pdf_list_model.rowCount()):
            return
            
        pdf = self.vm.pdf_list_model.pdfs[row]
        start_dir = os.path.dirname(pdf.file_path) if os.path.exists(os.path.dirname(pdf.file_path)) else self.vm.last_open_dir
        
        new_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Replacement for {pdf.name}",
            start_dir,
            "PDF Files (*.pdf)"
        )
        
        if new_path:
            self.vm.change_pdf_path(row, new_path)
            # If preview is visible, request thumbnails for the new path
            if self.preview_pane.isVisible():
                self.vm.request_thumbnails(new_path)

    def _on_refresh_selected_pdfs(self, indexes):
        """Refresh metadata for the selected PDF(s) and report changes."""
        all_changes = []
        for idx in indexes:
            row = idx.row()
            pdf = self.vm.pdf_list_model.pdfs[row]
            from project_manager import refresh_pdf_metadata
            changes = refresh_pdf_metadata(pdf)

            # Invalidate thumbnail cache
            if pdf.file_path in self.vm.thumbnail_cache:
                del self.vm.thumbnail_cache[pdf.file_path]

            # Notify model
            top_left = self.vm.pdf_list_model.index(row, 0)
            bottom_right = self.vm.pdf_list_model.index(row, self.vm.pdf_list_model.columnCount() - 1)
            self.vm.pdf_list_model.dataChanged.emit(top_left, bottom_right)

            all_changes.extend(changes)

        if all_changes:
            QMessageBox.information(
                self,
                "PDF Updated",
                "The following changes were detected:\n\n"
                + "\n".join(f"\u2022 {c}" for c in all_changes)
                + "\n\nCustom bookmarks have been preserved.",
            )
        else:
            count = len(indexes)
            self.statusBar().showMessage(
                f"{count} PDF(s) checked — no changes detected.", 3000
            )

        # Refresh preview if visible
        if self.preview_pane.isVisible() and len(indexes) == 1:
            row = indexes[0].row()
            pdf = self.vm.pdf_list_model.pdfs[row]
            if not pdf.missing:
                self.vm.request_thumbnails(pdf.file_path)

    def on_merge(self):
        # Guard: warn if there are missing files
        if self.vm.has_missing_files():
            reply = QMessageBox.warning(
                self,
                "Missing Files",
                "Some PDF files in the list could not be found.\n\n"
                "Remove or relocate the missing files (shown in red) before merging.",
                QMessageBox.StandardButton.Ok,
            )
            return

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
        # Trigger debounce timer
        self.selection_timer.start()

    def _on_selection_timer_timeout(self):
        indexes = self.pdf_table.selectionModel().selectedRows()
        
        self.edit_bookmarks_btn.setEnabled(len(indexes) == 1)
        
        if not indexes:
            self.preview_list.clear()
            return
            
        if self.preview_pane.isVisible():
            row = indexes[0].row()
            pdf = self.vm.pdf_list_model.pdfs[row]
            if pdf.missing:
                self.preview_list.clear()
            else:
                self.vm.request_thumbnails(pdf.file_path)

    def on_thumbnail_started(self, total_pages: int):
        self.preview_list.setUpdatesEnabled(False)
        self.preview_list.clear()
        self.preview_list.setGridSize(QSize(160, 245))
        # Pre-fill with placeholders to maintain order during parallel loading
        for i in range(total_pages):
            item = QListWidgetItem(f"Page {i + 1}")
            item.setSizeHint(QSize(150, 235)) # Match icon area + text height
            self.preview_list.addItem(item)
        self.preview_list.setUpdatesEnabled(True)

    def on_thumbnail_ready(self, page_num: int, image: QImage):
        # Update existing placeholder item
        if 0 <= page_num < self.preview_list.count():
            item = self.preview_list.item(page_num)
            pixmap = QPixmap.fromImage(image)
            item.setIcon(QIcon(pixmap))

    def on_thumbnail_batch_ready(self, batch: list):
        # Chunky update every 100 pages, inserting into pre-filled placeholders
        self.preview_list.setUpdatesEnabled(False)
        try:
            for page_num, image in batch:
                if 0 <= page_num < self.preview_list.count():
                    item = self.preview_list.item(page_num)
                    pixmap = QPixmap.fromImage(image)
                    item.setIcon(QIcon(pixmap))
        finally:
            self.preview_list.setUpdatesEnabled(True)

    def on_thumbnail_cache_ready(self, cache: dict):
        # Update placeholders for all cached items at once
        self.preview_list.setUpdatesEnabled(False)
        try:
            for page_num in sorted(cache.keys()):
                if 0 <= page_num < self.preview_list.count():
                    image = cache[page_num]
                    item = self.preview_list.item(page_num)
                    pixmap = QPixmap.fromImage(image)
                    item.setIcon(QIcon(pixmap))
        finally:
            self.preview_list.setUpdatesEnabled(True)


        
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

    def on_edit_bookmarks(self):
        indexes = self.pdf_table.selectionModel().selectedRows()
        if not indexes: return
        row = indexes[0].row()
        
        self.edit_bookmarks_btn.setEnabled(False)
        self.vm.request_toc(row)

    def on_toc_ready(self, row: int, toc: list, max_pages: int, name: str):
        self.edit_bookmarks_btn.setEnabled(True)
        
        from PySide6.QtWidgets import QDialog
        dialog = BookmarkEditorDialog(toc, max_pages, name, self)
        if self.theme_manager:
            self.theme_manager.apply_window_theme(dialog)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_toc = dialog.get_updated_toc()
            self.vm.set_custom_toc_for_pdf(row, new_toc)

    def on_settings_open(self):
        if self.theme_manager:
            dialog = SettingsDialog(self.theme_manager, self)
            self.theme_manager.apply_window_theme(dialog)
            dialog.exec()

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

    # --- Project Save / Load handlers ---

    def on_save_project(self):
        """Save to current project path, or prompt Save As if none."""
        if self._current_project_path:
            self.vm.do_save_project(
                self._current_project_path,
                self.output_name.text().strip(),
            )
        else:
            self.on_save_project_as()

    def on_save_project_as(self):
        """Prompt the user for a save location."""
        start_dir = os.path.dirname(self._current_project_path) if self._current_project_path else self.vm.output_dir
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            start_dir,
            "PDF Merger Project (*.pdfm)",
        )
        if path:
            if not path.lower().endswith(".pdfm"):
                path += ".pdfm"
            self.vm.do_save_project(path, self.output_name.text().strip())

    def on_open_project(self):
        """Prompt the user for a project file to load."""
        # Warn if there are PDFs in the current list
        if self.vm.pdf_list_model.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Open Project",
                "Opening a project will replace the current PDF list.\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        start_dir = os.path.dirname(self._current_project_path) if self._current_project_path else self.vm.last_open_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            start_dir,
            "PDF Merger Project (*.pdfm)",
        )
        if path:
            self.vm.do_load_project(path)

    def _on_project_saved(self, project_path: str):
        self._current_project_path = project_path
        name = os.path.splitext(os.path.basename(project_path))[0]
        self.setWindowTitle(f"{self._app_title} — {name}")

    def _on_project_loaded(self, project_path: str, output_name: str):
        self._current_project_path = project_path
        name = os.path.splitext(os.path.basename(project_path))[0]
        self.setWindowTitle(f"{self._app_title} — {name}")
        if output_name:
            self.output_name.setText(output_name)
        self._update_empty_state()

    def _on_project_load_warning(self, message: str):
        QMessageBox.warning(self, "Missing Files", message)
