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
)
from PyQt6.QtCore import Qt, QSize

from viewmodel import MainViewModel

class MainWindow(QMainWindow):
    def __init__(self, viewmodel: MainViewModel):
        super().__init__()
        self.vm = viewmodel
        self.setWindowTitle("PDF Merger (MVVM)")
        self.setMinimumSize(QSize(700, 450))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self._setup_ui()
        self._bind_viewmodel()

    def _setup_ui(self):
        # Table view setup
        self.pdf_table = QTableView()
        self.pdf_table.setModel(self.vm.pdf_list_model)
        self.pdf_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pdf_table.horizontalHeader().setSectionsMovable(True)
        self.pdf_table.horizontalHeader().setSectionsClickable(True)
        self.pdf_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Drag and Drop internally handled by model
        self.pdf_table.setDragEnabled(True)
        self.pdf_table.setAcceptDrops(True)
        self.pdf_table.setDropIndicatorShown(True)
        self.pdf_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.pdf_table.setDragDropOverwriteMode(False)
        self.pdf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pdf_table.setSortingEnabled(True)
        
        self.layout.addWidget(self.pdf_table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add PDFs")
        self.remove_btn = QPushButton("Remove Selected")
        self.merge_btn = QPushButton("Merge PDFs")
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.merge_btn)
        self.layout.addLayout(btn_layout)

        # Output Layout
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output File:"))
        self.output_name = QLineEdit(f"merged_output_{datetime.now():%Y%m%d_%H%M%S}.pdf")
        
        output_layout.addWidget(self.output_name)
        self.output_dir_btn = QPushButton("Set Output Directory")
        output_layout.addWidget(self.output_dir_btn)
        self.layout.addLayout(output_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        self.setStatusBar(QStatusBar(self))
        self.vm.set_output_dir(self.vm.output_dir)

    def _bind_viewmodel(self):
        # View bindings (UI events to ViewModel methods)
        self.add_btn.clicked.connect(self.on_add_pdfs)
        self.remove_btn.clicked.connect(self.on_remove_pdfs)
        self.merge_btn.clicked.connect(self.on_merge)
        self.output_dir_btn.clicked.connect(self.on_set_output_dir)

        # ViewModel bindings (Signals to UI updates)
        self.vm.status_message.connect(self.on_status_message)
        self.vm.merge_started.connect(self.on_merge_started)
        self.vm.merge_completed.connect(self.on_merge_completed)

    def on_add_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", self.vm.output_dir, "PDF Files (*.pdf)"
        )
        if files:
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

    def on_set_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.vm.output_dir
        )
        if directory:
            self.vm.set_output_dir(directory)

    # Signal handlers
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
