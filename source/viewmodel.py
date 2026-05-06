import os
from typing import List
from datetime import datetime
import fitz

from PyQt6.QtCore import (
    QObject,
    QAbstractTableModel,
    Qt,
    QModelIndex,
    QThread,
    pyqtSignal,
    QSettings,
)
from PyQt6.QtGui import QImage

from model import PDFDocument
from engine import merge_pdfs_engine


class MergeWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, pdf_list: List[PDFDocument], output_path: str):
        super().__init__()
        self.pdf_list = pdf_list
        self.output_path = output_path

    def run(self):
        success, message = merge_pdfs_engine(self.pdf_list, self.output_path)
        self.finished.emit(success, message)


class ThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(str, int, QImage)
    
    def __init__(self, file_path: str, pages: List[int], max_width: int = 150, max_height: int = 200):
        super().__init__()
        self.file_path = file_path
        self.pages = pages
        self.max_width = max_width
        self.max_height = max_height
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            doc = fitz.open(self.file_path)
            for page_num in self.pages:
                if self._is_cancelled:
                    break
                page = doc.load_page(page_num)
                rect = page.rect
                if rect.width == 0 or rect.height == 0:
                    continue
                zoom_x = self.max_width / rect.width
                zoom_y = self.max_height / rect.height
                zoom = min(zoom_x, zoom_y)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                img = img.copy()
                self.thumbnail_ready.emit(self.file_path, page_num, img)
            doc.close()
        except Exception as e:
            print(f"Error generating thumbnails for {self.file_path}: {e}")


class PDFListViewModel(QAbstractTableModel):
    order_broken = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdfs: List[PDFDocument] = []
        self.headers = ["Name", "Size (KB)", "Modified Date", "Pages"]
        self.dragged_rows = []

    def mimeTypes(self):
        return ["application/x-qabstractitemmodeldatalist"]

    def mimeData(self, indexes):
        self.dragged_rows = sorted(list(set(index.row() for index in indexes)))
        return super().mimeData(indexes)

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.DropAction.IgnoreAction:
            return True
            
        if not data.hasFormat("application/x-qabstractitemmodeldatalist"):
            return False

        if row != -1:
            begin_row = row
        elif parent.isValid():
            begin_row = parent.row()
        else:
            begin_row = self.rowCount(QModelIndex())
            
        if not hasattr(self, 'dragged_rows') or not self.dragged_rows:
            return False
            
        self.order_broken.emit()
        self.layoutAboutToBeChanged.emit()
        
        moved_items = [self.pdfs[r] for r in self.dragged_rows]
        
        insert_row = begin_row
        for r in self.dragged_rows:
            if r < begin_row:
                insert_row -= 1
                
        for r in sorted(self.dragged_rows, reverse=True):
            self.pdfs.pop(r)
            
        for i, item in enumerate(moved_items):
            self.pdfs.insert(insert_row + i, item)
            
        self.dragged_rows = []
        self.layoutChanged.emit()
        
        return False

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.pdfs)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        pdf = self.pdfs[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return pdf.name
            elif col == 1:
                return f"{pdf.size_kb:.1f}"
            elif col == 2:
                return pdf.modified_dt.strftime("%Y-%m-%d %H:%M")
            elif col == 3:
                return str(pdf.pages)

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                return f"Path: {pdf.file_path}\nName: {pdf.name}"
            elif col == 1:
                return f"{pdf.size_kb:.3f} KB"
            elif col == 2:
                return f"{pdf.modified_dt:%Y-%m-%d %H:%M:%S}"
            elif col == 3:
                return f"{pdf.pages} pages"

        elif role == Qt.ItemDataRole.UserRole:
            # Allow custom sorting based on UserRole
            if col == 0:
                return pdf.name.lower()
            elif col == 1:
                return pdf.size_kb
            elif col == 2:
                return pdf.modified_dt
            elif col == 3:
                return pdf.pages

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        reverse = (order == Qt.SortOrder.DescendingOrder)
        
        if column == 0:
            self.pdfs.sort(key=lambda x: x.name.lower(), reverse=reverse)
        elif column == 1:
            self.pdfs.sort(key=lambda x: x.size_kb, reverse=reverse)
        elif column == 2:
            self.pdfs.sort(key=lambda x: x.modified_dt, reverse=reverse)
        elif column == 3:
            self.pdfs.sort(key=lambda x: x.pages, reverse=reverse)
            
        self.layoutChanged.emit()

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def flags(self, index):
        default_flags = super().flags(index)
        if index.isValid():
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled
        else:
            return Qt.ItemFlag.ItemIsDropEnabled | default_flags


class MainViewModel(QObject):
    # Signals to update the View
    status_message = pyqtSignal(str, int)
    merge_started = pyqtSignal()
    merge_completed = pyqtSignal(bool, str)
    output_dir_changed = pyqtSignal(str)
    
    thumbnail_ready = pyqtSignal(int, QImage)
    thumbnail_started = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.pdf_list_model = PDFListViewModel()
        self.settings = QSettings("PDFMerger", "PDFMergerApp")
        self.output_dir = self.settings.value("output_dir", os.path.expanduser("~"), type=str)
        self.last_open_dir = self.settings.value("last_open_dir", os.path.expanduser("~"), type=str)
        self.worker = None
        self.thumbnail_worker = None
        self.thumbnail_cache = {}
        self._current_preview_file = None

    def request_thumbnails(self, file_path: str):
        self._current_preview_file = file_path
        
        pdf = next((p for p in self.pdf_list_model.pdfs if p.file_path == file_path), None)
        if not pdf: return

        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.cancel()
            try:
                self.thumbnail_worker.thumbnail_ready.disconnect()
            except TypeError:
                pass
            self.thumbnail_worker.wait()
            self.thumbnail_worker = None
            
        self.thumbnail_started.emit()
        
        if file_path not in self.thumbnail_cache:
            self.thumbnail_cache[file_path] = {}
            
        for page_num in sorted(self.thumbnail_cache[file_path].keys()):
            self.thumbnail_ready.emit(page_num, self.thumbnail_cache[file_path][page_num])
            
        if len(self.thumbnail_cache[file_path]) == pdf.pages:
            return
            
        missing_pages = [p for p in range(pdf.pages) if p not in self.thumbnail_cache[file_path]]
        
        self.thumbnail_worker = ThumbnailWorker(file_path, missing_pages)
        self.thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_worker_ready)
        self.thumbnail_worker.start()

    def _on_thumbnail_worker_ready(self, file_path: str, page_num: int, image: QImage):
        if file_path not in self.thumbnail_cache:
            self.thumbnail_cache[file_path] = {}
        self.thumbnail_cache[file_path][page_num] = image
        
        if file_path == self._current_preview_file:
            self.thumbnail_ready.emit(page_num, image)

    def set_last_open_dir(self, directory: str):
        if directory:
            self.last_open_dir = directory
            self.settings.setValue("last_open_dir", self.last_open_dir)

    def add_pdfs(self, file_paths: List[str]):
        if not file_paths:
            return

        existing_paths = {pdf.file_path for pdf in self.pdf_list_model.pdfs}
        new_pdfs = []
        errors = []

        for file_path in file_paths:
            if file_path in existing_paths:
                continue

            try:
                file_stats = os.stat(file_path)
                file_name = os.path.basename(file_path)
                file_size_kb = file_stats.st_size / 1024.0
                modified_dt = datetime.fromtimestamp(file_stats.st_mtime)
                pages = 0
                
                doc = None
                try:
                    doc = fitz.open(file_path)
                    pages = doc.page_count
                except Exception as e:
                    errors.append(f"PagesError: {file_name} ({e})")
                finally:
                    if doc: doc.close()

                new_pdfs.append(PDFDocument(
                    file_path=file_path,
                    name=file_name,
                    size_kb=file_size_kb,
                    modified_dt=modified_dt,
                    pages=pages
                ))
            except Exception as e:
                errors.append(f"AddError: {os.path.basename(file_path)} ({e})")

        if new_pdfs:
            # Need to inform model we are inserting rows
            self.pdf_list_model.beginInsertRows(
                QModelIndex(), 
                len(self.pdf_list_model.pdfs), 
                len(self.pdf_list_model.pdfs) + len(new_pdfs) - 1
            )
            self.pdf_list_model.pdfs.extend(new_pdfs)
            self.pdf_list_model.endInsertRows()

            # Set the output directory to the folder of the newly added files
            first_new_dir = os.path.dirname(new_pdfs[0].file_path)
            self.set_output_dir(first_new_dir)

            msg = f"Added {len(new_pdfs)} PDF(s)." + (f" {len(errors)} error(s)." if errors else "")
            self.status_message.emit(msg, 5000)
        elif errors:
            self.status_message.emit(f"Failed to add files. {len(errors)} error(s).", 5000)
        else:
            self.status_message.emit("Selected PDF(s) already in list.", 3000)

    def remove_pdfs_by_indices(self, indices: List[int]):
        # Sort indices in descending order so removal doesn't shift remaining targets
        sorted_indices = sorted(indices, reverse=True)
        for r in sorted_indices:
            if 0 <= r < len(self.pdf_list_model.pdfs):
                pdf = self.pdf_list_model.pdfs[r]
                if pdf.file_path in self.thumbnail_cache:
                    del self.thumbnail_cache[pdf.file_path]
                self.pdf_list_model.beginRemoveRows(QModelIndex(), r, r)
                del self.pdf_list_model.pdfs[r]
                self.pdf_list_model.endRemoveRows()
        
        self.status_message.emit(f"Removed {len(sorted_indices)} PDF(s)", 3000)

    def move_rows(self, source_row: int, count: int, destination_child_row: int):
        # Allow programmatic or drag/drop reordering.
        if destination_child_row >= source_row and destination_child_row <= source_row + count:
            return  # No-op move

        self.pdf_list_model.beginMoveRows(QModelIndex(), source_row, source_row + count - 1, QModelIndex(), destination_child_row)
        
        moved_items = self.pdf_list_model.pdfs[source_row : source_row + count]
        temp_list = self.pdf_list_model.pdfs[:source_row] + self.pdf_list_model.pdfs[source_row + count:]
        
        insert_index = destination_child_row
        if source_row < destination_child_row:
            insert_index -= count
            
        self.pdf_list_model.pdfs = temp_list[:insert_index] + moved_items + temp_list[insert_index:]
        
        self.pdf_list_model.endMoveRows()

    def set_output_dir(self, directory: str):
        if directory:
            self.output_dir = directory
            self.settings.setValue("output_dir", self.output_dir)
            self.output_dir_changed.emit(self.output_dir)
            self.status_message.emit(f"Output directory: {self.output_dir}", 3000)

    def start_merge(self, dest_filename: str):
        if not self.pdf_list_model.pdfs:
            self.status_message.emit("No PDFs loaded.", 3000)
            return

        if not dest_filename.lower().endswith(".pdf"):
            dest_filename += ".pdf"

        output_path = os.path.join(self.output_dir, dest_filename)

        # Basic check for file overwrite logic should ideally be requested by View
        # But we'll let the View check and then call start_merge. Let's assume
        # View already checked for overwrite if exists.

        self.merge_started.emit()
        self.status_message.emit("Merging started in background...", 0)

        # Keep reference to avoid garbage collection
        self.worker = MergeWorker(list(self.pdf_list_model.pdfs), output_path)
        self.worker.finished.connect(self._on_merge_finished)
        self.worker.start()

    def _on_merge_finished(self, success: bool, message: str):
        self.merge_completed.emit(success, message)
        self.status_message.emit(message, 7000)
        self.worker.deleteLater()
        self.worker = None

