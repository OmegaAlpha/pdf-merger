import os
from typing import List
from datetime import datetime
import fitz
import json

from PySide6.QtCore import (
    QObject,
    QAbstractTableModel,
    Qt,
    QModelIndex,
    QThread,
    Signal,
    QSettings,
)
from PySide6.QtGui import QImage

from model import PDFDocument
from engine import merge_pdfs_engine
from project_manager import save_project, load_project, refresh_pdf_metadata, verify_all_pdf_metadata

class AddPDFWorker(QThread):
    progress = Signal(PDFDocument)
    finished = Signal(int, int) # added, errors
    
    def __init__(self, file_paths: List[str], existing_paths: set):
        super().__init__()
        self.file_paths = file_paths
        self.existing_paths = existing_paths
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        
    def run(self):
        added_count = 0
        error_count = 0
        for file_path in self.file_paths:
            if self._is_cancelled:
                break
            if file_path in self.existing_paths:
                continue
            try:
                file_stats = os.stat(file_path)
                file_name = os.path.basename(file_path)
                file_size_kb = file_stats.st_size / 1024.0
                modified_dt = datetime.fromtimestamp(file_stats.st_mtime)
                
                # Opening PDF on network might be slow
                doc = fitz.open(file_path)
                pages = doc.page_count
                doc.close()

                pdf = PDFDocument(
                    file_path=file_path,
                    name=file_name,
                    size_kb=file_size_kb,
                    modified_dt=modified_dt,
                    pages=pages
                )
                self.progress.emit(pdf)
                added_count += 1
            except Exception as e:
                print(f"Error loading PDF metadata for {file_path}: {e}")
                error_count += 1
        self.finished.emit(added_count, error_count)


class MergeWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, pdf_list: List[PDFDocument], output_path: str):
        super().__init__()
        self.pdf_list = pdf_list
        self.output_path = output_path

    def run(self):
        success, message = merge_pdfs_engine(self.pdf_list, self.output_path)
        self.finished.emit(success, message)


class ThumbnailWorker(QThread):
    thumbnail_ready = Signal(str, int, object) # Using object for batch list support
    
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
            batch = []
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
                
                # Draw a thin border around the thumbnail
                from PySide6.QtGui import QPainter, QColor
                painter = QPainter(img)
                painter.setPen(QColor(200, 200, 200))
                painter.drawRect(0, 0, img.width() - 1, img.height() - 1)
                painter.end()
                
                batch.append((page_num, img))
                
                if len(batch) >= 100:
                    self.thumbnail_ready.emit(self.file_path, -1, batch)
                    batch = []
                
                # A microscopic sleep to force a GIL context switch
                import time
                time.sleep(0.001)
                    
            if batch:
                self.thumbnail_ready.emit(self.file_path, -1, batch)
            doc.close()
        except Exception as e:
            print(f"Error generating thumbnails for {self.file_path}: {e}")


class TOCWorker(QThread):
    finished = Signal(list, int, str)
    
    def __init__(self, row: int, file_path: str, pages: int, name: str):
        super().__init__()
        self.row = row
        self.file_path = file_path
        self.pages = pages
        self.name = name
        
    def run(self):
        toc = []
        try:
            doc = fitz.open(self.file_path)
            toc = doc.get_toc(simple=False)
            doc.close()
        except Exception as e:
            print(f"Error reading TOC for {self.name}: {e}")
            
        if not toc:
            toc = [[1, os.path.splitext(self.name)[0], 1]]
            
        self.finished.emit(toc, self.pages, self.name)


class PDFListViewModel(QAbstractTableModel):
    order_broken = Signal()
    
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

        elif role == Qt.ItemDataRole.ForegroundRole:
            if pdf.missing:
                from PySide6.QtGui import QColor
                return QColor(180, 60, 60)

        elif role == Qt.ItemDataRole.ToolTipRole:
            if pdf.missing:
                return f"FILE NOT FOUND\nPath: {pdf.file_path}"
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

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if not self.pdfs:
            return
            
        self.layoutAboutToBeChanged.emit()
        
        def sort_key(pdf):
            if column == 0: return pdf.name.lower()
            if column == 1: return pdf.size_kb
            if column == 2: return pdf.modified_dt
            if column == 3: return pdf.pages
            return ""

        reverse = (order == Qt.SortOrder.DescendingOrder)
        self.pdfs.sort(key=sort_key, reverse=reverse)
        
        self.layoutChanged.emit()

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
    status_message = Signal(str, int)
    merge_started = Signal()
    merge_completed = Signal(bool, str)
    output_dir_changed = Signal(str)
    
    thumbnail_ready = Signal(int, QImage)
    thumbnail_cache_ready = Signal(object) # Using 'object' avoids Shiboken conversion issues for dicts
    thumbnail_batch_ready = Signal(object)
    thumbnail_started = Signal(int) # Now includes total pages
    pdfs_added = Signal(int, int) # added, errors
    toc_ready = Signal(int, list, int, str) # row, toc, pages, name

    # Project signals
    project_loaded = Signal(str, str)   # project file path, output_name
    project_saved = Signal(str)        # project file path
    project_load_warning = Signal(str) # warning message (missing files etc.)
    pdf_refreshed = Signal(int, list)  # row, list of change descriptions
    
    def __init__(self):
        super().__init__()
        self.pdf_list_model = PDFListViewModel()
        self.settings = QSettings("PDFMerger", "PDFMergerApp")
        self.output_dir = self.settings.value("output_dir", os.path.expanduser("~"), type=str)
        self.last_open_dir = self.settings.value("last_open_dir", os.path.expanduser("~"), type=str)
        self.worker = None
        self.add_worker = None
        self.thumbnail_worker = None
        self.thumbnail_cache = {}
        self._current_preview_file = None

    def request_thumbnails(self, file_path: str):
        self._current_preview_file = file_path
        
        pdf = next((p for p in self.pdf_list_model.pdfs if p.file_path == file_path), None)
        if not pdf or pdf.missing: 
            return

        # Stop previous worker if running
        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.cancel()
            try:
                self.thumbnail_worker.thumbnail_ready.disconnect()
            except:
                pass
            self.thumbnail_worker.deleteLater()
        self.thumbnail_worker = None
            
        total_pages_to_show = pdf.pages
        self.thumbnail_started.emit(total_pages_to_show)
        
        if file_path not in self.thumbnail_cache:
            self.thumbnail_cache[file_path] = {}
        else:
            # Emit all cached thumbnails at once for instant UI update
            if self.thumbnail_cache[file_path]:
                self.thumbnail_cache_ready.emit(self.thumbnail_cache[file_path])
            
        missing_pages = [p for p in range(total_pages_to_show) if p not in self.thumbnail_cache[file_path]]
        
        if not missing_pages:
            return

        self.thumbnail_worker = ThumbnailWorker(file_path, missing_pages)
        self.thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_worker_ready)
        self.thumbnail_worker.start(QThread.Priority.LowPriority)

    def _on_thumbnail_worker_ready(self, file_path: str, page_num: int, data: object):
        if file_path not in self.thumbnail_cache:
            self.thumbnail_cache[file_path] = {}
        
        if page_num == -1:
            # Batch mode
            batch = data
            batch_to_emit = []
            for p_num, img in batch:
                self.thumbnail_cache[file_path][p_num] = img
                if file_path == self._current_preview_file:
                    batch_to_emit.append((p_num, img))
            
            if batch_to_emit:
                self.thumbnail_batch_ready.emit(batch_to_emit)
        else:
            # Single mode (if ever used)
            self.thumbnail_cache[file_path][page_num] = data
            if file_path == self._current_preview_file:
                self.thumbnail_ready.emit(page_num, data)

    def set_last_open_dir(self, directory: str):
        if directory:
            self.last_open_dir = directory
            self.settings.setValue("last_open_dir", self.last_open_dir)

    def request_toc(self, row: int):
        if not (0 <= row < len(self.pdf_list_model.pdfs)):
            return
            
        pdf = self.pdf_list_model.pdfs[row]
        if pdf.missing:
            return
        if pdf.custom_toc is not None:
            self.toc_ready.emit(row, pdf.custom_toc, pdf.pages, pdf.name)
            return
            
        self.status_message.emit(f"Reading bookmarks for {pdf.name}...", 0)
        self.toc_worker = TOCWorker(row, pdf.file_path, pdf.pages, pdf.name)
        self.toc_worker.finished.connect(lambda toc, pages, name: self._on_toc_ready(row, toc, pages, name))
        self.toc_worker.start()

    def _on_toc_ready(self, row: int, toc: list, pages: int, name: str):
        self.status_message.emit("Bookmarks loaded.", 3000)
        self.toc_ready.emit(row, toc, pages, name)
        self.toc_worker = None

    def set_custom_toc_for_pdf(self, row: int, toc: list):
        if 0 <= row < len(self.pdf_list_model.pdfs):
            self.pdf_list_model.pdfs[row].custom_toc = toc

    def add_pdfs(self, file_paths: List[str]):
        if not file_paths: return

        existing_paths = {pdf.file_path for pdf in self.pdf_list_model.pdfs}
        
        # Move long-running file operations to a background thread
        self.add_worker = AddPDFWorker(file_paths, existing_paths)
        self.add_worker.progress.connect(self._on_pdf_load_progress)
        self.add_worker.finished.connect(self._on_pdf_load_finished)
        
        self.status_message.emit(f"Analyzing {len(file_paths)} file(s)...", 0)
        self.add_worker.start()

    def _on_pdf_load_progress(self, pdf: PDFDocument):
        # Update model row by row as they are loaded
        self.pdf_list_model.beginInsertRows(
            QModelIndex(), 
            len(self.pdf_list_model.pdfs), 
            len(self.pdf_list_model.pdfs)
        )
        self.pdf_list_model.pdfs.append(pdf)
        self.pdf_list_model.endInsertRows()
        
        # If it's the first one, update output dir
        if len(self.pdf_list_model.pdfs) == 1:
            self.set_output_dir(os.path.dirname(pdf.file_path))

    def _on_pdf_load_finished(self, added: int, errors: int):
        if added > 0:
            msg = f"Added {added} PDF(s)." + (f" {errors} error(s)." if errors else "")
            self.status_message.emit(msg, 5000)
        elif errors:
            self.status_message.emit(f"Failed to add files. {errors} error(s).", 5000)
        else:
            self.status_message.emit("Selected PDF(s) already in list.", 3000)
            
        self.pdfs_added.emit(added, errors)
        self.add_worker = None

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

    # --- PDF Refresh ---

    def refresh_pdf(self, row: int):
        """Re-read a PDF's metadata from disk, preserving custom_toc."""
        if not (0 <= row < len(self.pdf_list_model.pdfs)):
            return

        pdf = self.pdf_list_model.pdfs[row]
        changes = refresh_pdf_metadata(pdf)

        # Invalidate thumbnail cache for this file
        if pdf.file_path in self.thumbnail_cache:
            del self.thumbnail_cache[pdf.file_path]

        # Notify the table model that this row changed
        top_left = self.pdf_list_model.index(row, 0)
        bottom_right = self.pdf_list_model.index(row, self.pdf_list_model.columnCount() - 1)
        self.pdf_list_model.dataChanged.emit(top_left, bottom_right)

        self.pdf_refreshed.emit(row, changes)

        if changes:
            self.status_message.emit(f"Updated: {'; '.join(changes)}", 7000)
        else:
            self.status_message.emit(f"{pdf.name}: no changes detected.", 3000)

    def change_pdf_path(self, row: int, new_path: str):
        """Change the file path of an existing PDF entry, preserving custom_toc."""
        if not (0 <= row < len(self.pdf_list_model.pdfs)):
            return

        pdf = self.pdf_list_model.pdfs[row]
        old_path = pdf.file_path
        
        # Invalidate thumbnail cache for old path
        if old_path in self.thumbnail_cache:
            del self.thumbnail_cache[old_path]
            
        # Update path and name
        pdf.file_path = new_path
        pdf.name = os.path.basename(new_path)
        
        # Refresh metadata (size, pages, modified_dt, missing flag)
        changes = refresh_pdf_metadata(pdf)
        
        # Invalidate thumbnail cache for new path (just in case)
        if new_path in self.thumbnail_cache:
            del self.thumbnail_cache[new_path]

        # Notify the table model that this row changed
        top_left = self.pdf_list_model.index(row, 0)
        bottom_right = self.pdf_list_model.index(row, self.pdf_list_model.columnCount() - 1)
        self.pdf_list_model.dataChanged.emit(top_left, bottom_right)

        self.pdf_refreshed.emit(row, changes)
        self.status_message.emit(f"Relocated: {pdf.name}", 5000)

    # --- Project Save / Load ---

    def has_missing_files(self) -> bool:
        """Return True if any PDF in the list is flagged as missing."""
        return any(pdf.missing for pdf in self.pdf_list_model.pdfs)

    def do_save_project(self, project_path: str, output_name: str):
        """Save the current session to a .pdfm file."""
        try:
            save_project(
                project_path,
                self.pdf_list_model.pdfs,
                self.output_dir,
                output_name,
            )
            self.project_saved.emit(project_path)
            self.status_message.emit(f"Project saved: {os.path.basename(project_path)}", 5000)
        except Exception as e:
            self.status_message.emit(f"Error saving project: {e}", 7000)

    def do_load_project(self, project_path: str):
        """Load a .pdfm project file, replacing the current session."""
        try:
            result = load_project(project_path)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self.status_message.emit(f"Error loading project: {e}", 7000)
            return

        # Clear current state
        if self.pdf_list_model.pdfs:
            self.pdf_list_model.beginResetModel()
            self.pdf_list_model.pdfs.clear()
            self.pdf_list_model.endResetModel()
        self.thumbnail_cache.clear()

        # Stop any running thumbnail worker
        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.cancel()
            self.thumbnail_worker.deleteLater()
            self.thumbnail_worker = None

        # Populate the PDF list
        pdfs = result["pdfs"]
        if pdfs:
            self.pdf_list_model.beginInsertRows(
                QModelIndex(), 0, len(pdfs) - 1
            )
            self.pdf_list_model.pdfs.extend(pdfs)
            self.pdf_list_model.endInsertRows()

        # Verify metadata of found files against live disk state
        metadata_changes = verify_all_pdf_metadata(pdfs)
        # Refresh the table display after verification updates
        if metadata_changes:
            self.pdf_list_model.beginResetModel()
            self.pdf_list_model.endResetModel()

        # Set output dir and name
        self.set_output_dir(result["output_dir"])

        # Emit signals
        self.project_loaded.emit(project_path, result["output_name"])

        # Build combined warning message
        warnings = []
        missing = result.get("missing_files", [])
        if missing:
            warnings.append(
                f"The following files could not be found:\n"
                + "\n".join(f"  \u2022 {n}" for n in missing)
                + "\n\nThey are shown in the list but cannot be merged until relocated or removed."
            )
        if metadata_changes:
            warnings.append(
                f"The following files have changed since the project was saved:\n"
                + "\n".join(f"  \u2022 {c}" for c in metadata_changes)
            )

        if warnings:
            self.project_load_warning.emit("\n\n".join(warnings))
            self.status_message.emit(
                f"Project loaded with {len(missing)} missing, {len(metadata_changes)} changed file(s).", 7000
            )
        else:
            self.status_message.emit(
                f"Project loaded: {os.path.basename(project_path)}", 5000
            )
