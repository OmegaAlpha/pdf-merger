#!/usr/bin/env python3
import sys
import os
import collections
import fitz  # PyMuPDF
import traceback  # For detailed error printing
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QFileDialog,
    QLineEdit,
    QLabel,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QStatusBar,
    QMessageBox,
    QStyle,
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QItemSelection,
    QModelIndex,
    QItemSelectionModel,
)

# Use PyPDF2 only for initial page count if needed, prefer fitz
from PyPDF2 import PdfReader as PyPDF2Reader  # Keep for add_pdfs page count


# --- Helper Classes and Data Structures ---
class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            val1 = float(self.data(Qt.ItemDataRole.UserRole))
            val2 = float(other.data(Qt.ItemDataRole.UserRole))
            return val1 < val2
        except (ValueError, TypeError):
            return super().__lt__(other)


class DateTimeTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            dt1 = self.data(Qt.ItemDataRole.UserRole)
            dt2 = other.data(Qt.ItemDataRole.UserRole)
            if isinstance(dt1, datetime) and isinstance(dt2, datetime):
                return dt1 < dt2
            else:
                return super().__lt__(other)
        except TypeError:
            return super().__lt__(other)


# --- Main Application Class ---
class PDFMergerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Merger")
        self.setMinimumSize(QSize(600, 400))
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.pdf_table = QTableWidget()
        self.pdf_table.setColumnCount(4)
        self.pdf_table.setHorizontalHeaderLabels(
            ["Name", "Size (KB)", "Modified Date", "Pages"]
        )
        self.pdf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.pdf_table.horizontalHeader().setSectionsMovable(True)
        self.pdf_table.horizontalHeader().setSectionsClickable(True)
        self.pdf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pdf_table.setDragEnabled(True)
        self.pdf_table.setAcceptDrops(True)
        self.pdf_table.setDropIndicatorShown(True)
        self.pdf_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.pdf_table.setDragDropOverwriteMode(False)
        self.pdf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pdf_table.setSortingEnabled(False)
        self.pdf_table.horizontalHeader().sectionClicked.connect(
            self.handle_header_click
        )
        self.pdf_table.model().rowsMoved.connect(self.on_rows_moved)
        self.layout.addWidget(self.pdf_table)
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add PDFs")
        self.add_btn.clicked.connect(self.add_pdfs)
        btn_layout.addWidget(self.add_btn)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_pdfs)
        btn_layout.addWidget(self.remove_btn)
        self.merge_btn = QPushButton("Merge PDFs")
        self.merge_btn.clicked.connect(self.merge_pdfs)
        btn_layout.addWidget(self.merge_btn)
        self.layout.addLayout(btn_layout)
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output File:"))
        self.output_name = QLineEdit("merged_output.pdf")
        output_layout.addWidget(self.output_name)
        self.output_dir_btn = QPushButton("Set Output Directory")
        self.output_dir_btn.clicked.connect(self.set_output_directory)
        output_layout.addWidget(self.output_dir_btn)
        self.layout.addLayout(output_layout)
        self.setStatusBar(QStatusBar(self))
        self.output_dir = os.path.expanduser("~")
        self.pdf_files_data = []

    def add_pdfs(self):  # Using fitz page count
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", self.output_dir, "PDF Files (*.pdf)"
        )
        if not files:
            return
        added_count = 0
        errors = []
        new_files_data = []
        existing_paths = {data[0] for data in self.pdf_files_data}
        for file_path in files:
            if file_path in existing_paths:
                continue
            doc = None
            try:
                file_stats = os.stat(file_path)
                file_name = os.path.basename(file_path)
                file_size_kb = file_stats.st_size / 1024.0
                modified_dt = datetime.fromtimestamp(file_stats.st_mtime)
                pages = 0
                try:
                    doc = fitz.open(file_path)
                    pages = doc.page_count
                except Exception as page_error:
                    errors.append(f"PagesError: {file_name} ({page_error})")
                finally:
                    if doc:
                        doc.close()
                new_files_data.append(
                    (file_path, file_name, file_size_kb, modified_dt, pages)
                )
                added_count += 1
                existing_paths.add(file_path)
            except Exception as e:
                errors.append(f"AddError: {os.path.basename(file_path)} ({e})")
        if added_count > 0:
            self.pdf_files_data.extend(new_files_data)
            if self._sort_column != -1:
                self.sort_data(self._sort_column, self._sort_order)
            self.populate_table()
            msg = f"Added {added_count} PDF(s)." + (
                f" {len(errors)} error(s)." if errors else ""
            )
            self.statusBar().showMessage(msg, 5000)
        elif files and not errors:
            self.statusBar().showMessage("Selected PDF(s) already in list.", 3000)
        elif errors:
            self.statusBar().showMessage(
                f"Failed to add files. {len(errors)} error(s).", 5000
            )

    def populate_table(self):
        self.pdf_table.setUpdatesEnabled(False)
        self.pdf_table.setRowCount(0)
        new_row_count = len(self.pdf_files_data)
        self.pdf_table.setRowCount(new_row_count)
        if self.pdf_table.rowCount() != new_row_count:
            print("!!! WARNING: Row count mismatch!")
        for row, pdf_data in enumerate(self.pdf_files_data):
            path, name, size_kb, modified_dt, pages = pdf_data
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, path)
            size_item = NumericTableWidgetItem(f"{size_kb:.1f}")
            size_item.setData(Qt.ItemDataRole.UserRole, size_kb)
            modified_item = DateTimeTableWidgetItem(
                modified_dt.strftime("%Y-%m-%d %H:%M")
            )
            modified_item.setData(Qt.ItemDataRole.UserRole, modified_dt)
            pages_item = NumericTableWidgetItem(str(pages))
            pages_item.setData(Qt.ItemDataRole.UserRole, pages)
            name_item.setToolTip(f"Path: {path}\nName: {name}")
            size_item.setToolTip(f"{size_kb:.3f} KB")
            modified_item.setToolTip(f"{modified_dt:%Y-%m-%d %H:%M:%S}")
            pages_item.setToolTip(f"{pages} pages")
            flags = (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            [
                item.setFlags(flags)
                for item in [name_item, size_item, modified_item, pages_item]
            ]
            self.pdf_table.setItem(row, 0, name_item)
            self.pdf_table.setItem(row, 1, size_item)
            self.pdf_table.setItem(row, 2, modified_item)
            self.pdf_table.setItem(row, 3, pages_item)
        self.pdf_table.setUpdatesEnabled(True)
        if self._sort_column != -1:
            self.pdf_table.horizontalHeader().setSortIndicator(
                self._sort_column, self._sort_order
            )
            self.pdf_table.horizontalHeader().setSortIndicatorShown(True)
        else:
            self.pdf_table.horizontalHeader().setSortIndicatorShown(False)

    def remove_selected_pdfs(self):
        selected_indices = self.pdf_table.selectionModel().selectedRows()
        if not selected_indices:
            return self.statusBar().showMessage("No rows selected.", 3000)
        rows_to_remove = sorted(
            [index.row() for index in selected_indices], reverse=True
        )
        removed_count = 0
        for row in rows_to_remove:
            if 0 <= row < len(self.pdf_files_data):
                del self.pdf_files_data[row]
                removed_count += 1
        if removed_count > 0:
            self.populate_table()
            self.statusBar().showMessage(f"Removed {removed_count} PDF(s)", 3000)

    def on_rows_moved(self, parent, start, end, destination, row):
        if parent.isValid() or destination.isValid():
            return
        source_model_row_count = self.pdf_table.rowCount()
        if not (0 <= start <= end < source_model_row_count and row >= -1):
            return print("Warning: Invalid on_rows_moved signal.")
        count = end - start + 1
        current_data_len = len(self.pdf_files_data)
        if end >= current_data_len:
            return (
                print("ERROR: Move signal index out of data bounds."),
                self.populate_table(),
            )
        target_row_in_data = (
            current_data_len if (row == -1 or row >= current_data_len) else row
        )
        try:
            moved_items = self.pdf_files_data[start : end + 1]
            temp_list = self.pdf_files_data[:start] + self.pdf_files_data[end + 1 :]
            insert_index_in_temp = (
                target_row_in_data - count
                if start < target_row_in_data
                else target_row_in_data
            )
            insert_index_in_temp = max(0, min(insert_index_in_temp, len(temp_list)))
            self.pdf_files_data = (
                temp_list[:insert_index_in_temp]
                + moved_items
                + temp_list[insert_index_in_temp:]
            )
            self._sort_column = -1
            self._sort_order = Qt.SortOrder.AscendingOrder
            self.populate_table()
            self.select_rows(insert_index_in_temp, insert_index_in_temp + count - 1)
        except Exception as e:
            print(
                f"ERROR in on_rows_moved: {e}"
            ), traceback.print_exc(), self.populate_table()

    def select_rows(self, start_row, end_row):
        current_row_count = self.pdf_table.rowCount()
        if not (
            0 <= start_row < current_row_count
            and 0 <= end_row < current_row_count
            and start_row <= end_row
        ):
            return
        selection_model = self.pdf_table.selectionModel()
        selection_model.clearSelection()
        item_selection = QItemSelection()
        for r in range(start_row, end_row + 1):
            tl = self.pdf_table.model().index(r, 0)
            br = self.pdf_table.model().index(r, self.pdf_table.columnCount() - 1)
            if tl.isValid() and br.isValid():
                item_selection.select(tl, br)
        if not item_selection.isEmpty():
            selection_model.select(
                item_selection,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def handle_header_click(self, logical_index):
        if not (0 <= logical_index < self.pdf_table.columnCount()):
            return print("Warning: Invalid header index.")
        new_order = (
            Qt.SortOrder.DescendingOrder
            if self._sort_column == logical_index
            and self._sort_order == Qt.SortOrder.AscendingOrder
            else Qt.SortOrder.AscendingOrder
        )
        self._sort_column = logical_index
        self._sort_order = new_order
        self.sort_data(self._sort_column, self._sort_order)
        self.populate_table()

    def sort_data(self, column, order):
        reverse_sort = order == Qt.SortOrder.DescendingOrder
        sort_key = None
        keys = {
            0: (lambda item: item[1].lower()),
            1: (lambda item: item[2]),
            2: (lambda item: item[3]),
            3: (lambda item: item[4]),
        }
        sort_key = keys.get(column)
        if sort_key:
            try:
                self.pdf_files_data.sort(key=sort_key, reverse=reverse_sort)
            except Exception as e:
                print(f"ERROR: Sorting exception: {e}"), self.statusBar().showMessage(
                    f"Sorting error: {e}", 5000
                )
        else:
            print(f"ERROR: Invalid sort column {column}")

    def set_output_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_dir
        )
        if directory:
            self.output_dir = directory
            self.statusBar().showMessage(f"Output directory: {self.output_dir}", 3000)

    # --- Bookmark Helper Functions (PyMuPDF specific) ---
    def _check_fitz_toc_for_first_page(self, toc):
        """Checks a PyMuPDF ToC list for an item pointing to page 1 (1-based index)."""
        if not toc:
            return False
        for item in toc:
            if len(item) >= 3 and isinstance(item[2], int) and item[2] == 1:
                return True
        return False

    def _adjust_toc_pages_and_levels(
        self, toc, page_offset_0based, source_doc, level_increase=0
    ):
        """
        Adjusts page numbers and destination dictionary page indices in a PyMuPDF TOC list.
        Resolves named destinations to explicit destinations and ensures valid entries.

        Args:
            toc: List of TOC entries from PyMuPDF (each entry: [level, title, page, dest_dict])
            page_offset_0based: 0-based page offset to adjust page numbers
            source_doc: The source PDF document (fitz.Document) to resolve named destinations
            level_increase: Amount to increase bookmark levels

        Returns:
            List of adjusted, valid TOC entries
        """

        if not toc:
            print("      No TOC to adjust.")
            return []

        # Resolve all named destinations in the source document
        named_dest_dict = source_doc.resolve_names()
        new_toc = []
        print(
            f"      Adjusting {len(toc)} TOC entries (offset={page_offset_0based}, level_inc={level_increase})"
        )

        for i, item in enumerate(toc):
            if not (isinstance(item, list) and len(item) >= 3):
                print(f"        Skipping malformed TOC entry {i}: {item}")
                continue

            new_item = list(item)  # Create a mutable copy
            valid_entry = True

            # Validate and adjust level (item[0])
            if isinstance(new_item[0], int):
                new_item[0] = max(1, new_item[0] + level_increase)
            else:
                print(f"        Skipping entry {i}: Invalid level {new_item[0]}")
                valid_entry = False

            # Validate and adjust title (item[1])
            if not isinstance(new_item[1], str) or not new_item[1].strip():
                print(f"        Skipping entry {i}: Invalid title {new_item[1]}")
                valid_entry = False

            # Validate and adjust page number (item[2], 1-based for set_toc)
            if isinstance(new_item[2], int):
                new_page_1based = new_item[2] + page_offset_0based
                if new_page_1based < 1:
                    print(
                        f"        Skipping entry {i}: Invalid adjusted page {new_page_1based}"
                    )
                    valid_entry = False
                new_item[2] = new_page_1based
            else:
                print(f"        Skipping entry {i}: Invalid page number {new_item[2]}")
                valid_entry = False

            # Handle destination dictionary (item[3] if present)
            dest_dict = (
                new_item[3]
                if len(new_item) > 3 and isinstance(new_item[3], dict)
                else {}
            )

            if dest_dict.get("kind") == fitz.LINK_NAMED:  # kind == 4
                named = dest_dict.get("nameddest") or dest_dict.get("named")
                if named and named in named_dest_dict:
                    resolved_dest = named_dest_dict[named]
                    if resolved_dest and "page" in resolved_dest:
                        original_page_0based = resolved_dest["page"]
                        new_dest_page_0based = original_page_0based + page_offset_0based
                        if new_dest_page_0based < 0:
                            print(
                                f"        Skipping entry {i}: Invalid dest page {new_dest_page_0based}"
                            )
                            valid_entry = False
                        else:
                            new_dest_dict = {
                                "kind": fitz.LINK_GOTO,  # 1
                                "page": new_dest_page_0based,
                                "to": resolved_dest.get("to", fitz.Point(0, 0)),
                                "zoom": resolved_dest.get("zoom", 0.0),
                            }
                            for key in resolved_dest:
                                if key not in ["kind", "page", "to", "zoom"]:
                                    new_dest_dict[key] = resolved_dest[key]
                            new_item[3] = new_dest_dict
                            print(
                                f"        Resolved named destination '{named}' to page {new_dest_page_0based} (original: {original_page_0based}) for entry {i}"
                            )
                    else:
                        print(
                            f"        Skipping entry {i}: Resolved destination '{named}' lacks page info"
                        )
                        valid_entry = False
                elif "page" in dest_dict and isinstance(dest_dict["page"], str):
                    # Handle non-standard named destinations with string page numbers
                    try:
                        original_page_0based = (
                            int(dest_dict["page"]) - 1
                        )  # Convert to 0-based
                        new_dest_page_0based = original_page_0based + page_offset_0based
                        if new_dest_page_0based < 0:
                            print(
                                f"        Skipping entry {i}: Invalid dest page {new_dest_page_0based}"
                            )
                            valid_entry = False
                        else:
                            new_dest_dict = {
                                "kind": fitz.LINK_GOTO,
                                "page": new_dest_page_0based,
                                "to": fitz.Point(0, 0),  # Default position
                                "zoom": dest_dict.get("zoom", 0.0),
                            }
                            # Preserve additional attributes like 'view' or 'xref'
                            for key in dest_dict:
                                if key not in ["kind", "page", "to", "zoom"]:
                                    new_dest_dict[key] = dest_dict[key]
                            new_item[3] = new_dest_dict
                            print(
                                f"        Converted string page '{dest_dict['page']}' to page {new_dest_page_0based} for entry {i}"
                            )
                    except ValueError:
                        print(
                            f"        Skipping entry {i}: Invalid string page number '{dest_dict['page']}'"
                        )
                        valid_entry = False
                else:
                    print(
                        f"        Skipping entry {i}: Missing or invalid named destination '{named}'"
                    )
                    valid_entry = False

            elif dest_dict.get("kind") == fitz.LINK_GOTO:  # kind == 1
                original_page_0based = dest_dict.get("page", new_item[2] - 1)
                if isinstance(original_page_0based, int):
                    new_dest_page_0based = original_page_0based + page_offset_0based
                    if new_dest_page_0based < 0:
                        print(
                            f"        Skipping entry {i}: Invalid dest page {new_dest_page_0based}"
                        )
                        valid_entry = False
                    else:
                        new_dest_dict = {
                            "kind": fitz.LINK_GOTO,
                            "page": new_dest_page_0based,
                            "to": dest_dict.get("to", fitz.Point(0, 0)),
                            "zoom": dest_dict.get("zoom", 0.0),
                        }
                        for key in dest_dict:
                            if key not in ["kind", "page", "to", "zoom"]:
                                new_dest_dict[key] = dest_dict[key]
                        new_item[3] = new_dest_dict
                        print(
                            f"        Adjusted explicit destination to page {new_dest_page_0based} (original: {original_page_0based}) for entry {i}"
                        )
                else:
                    print(
                        f"        Skipping entry {i}: Invalid original dest page {original_page_0based}"
                    )
                    valid_entry = False

            else:
                # No destination or unsupported kind, create a default
                original_page_0based = new_item[2] - 1  # Convert to 0-based
                new_dest_page_0based = original_page_0based + page_offset_0based
                if new_dest_page_0based < 0:
                    print(
                        f"        Skipping entry {i}: Invalid default dest page {new_dest_page_0based}"
                    )
                    valid_entry = False
                else:
                    new_dest_dict = {
                        "kind": fitz.LINK_GOTO,
                        "page": new_dest_page_0based,
                        "to": fitz.Point(0, 0),
                        "zoom": 0.0,
                    }
                    new_item[3] = new_dest_dict
                    print(
                        f"        No valid destination for entry {i}, using default page {new_dest_page_0based} (original: {original_page_0based})"
                    )

            # Special check for first-page bookmarks
            if valid_entry and new_item[3]["page"] == page_offset_0based:
                print(
                    f"        First-page bookmark detected for entry {i}: DestPg={new_item[3]['page']}, Pg={new_item[2]}, Title='{new_item[1]}'"
                )

            if valid_entry:
                print(
                    f"        Adjusted entry {i}: Lvl={new_item[0]}, Pg={new_item[2]}, DestPg={new_item[3]['page']}, Title='{new_item[1]}'"
                )
                new_toc.append(new_item)
            else:
                print(f"        Excluded invalid entry {i}: {new_item}")

        print(f"      Adjusted TOC: {len(new_toc)} valid entries")
        return new_toc

    # --- PDF Merging Method ---
    def merge_pdfs(self):
        if not self.pdf_files_data:
            return self.statusBar().showMessage("No PDFs loaded.", 3000)
        output_filename = (
            self.output_name.text().strip()
            or f"merged_output_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        )
        if not output_filename.lower().endswith(".pdf"):
            output_filename += ".pdf"
        self.output_name.setText(output_filename)
        output_path = os.path.join(self.output_dir, output_filename)
        if os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                f"File exists:\n{output_path}\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return self.statusBar().showMessage("Merge cancelled.", 3000)

        merged_doc = fitz.open()
        final_toc = []
        current_page_offset = 0
        success_count = 0
        error_files = []
        toc_error_files = []

        self.statusBar().showMessage("Merging started (PyMuPDF)...", 0)
        QApplication.processEvents()

        try:
            print(f"--- Starting PyMuPDF merge. Output: {output_path} ---")
            for pdf_path, name, _, _, _ in self.pdf_files_data:
                print(f"\n--- Processing file: {name} ---")
                self.statusBar().showMessage(f"Processing: {name}...", 0)
                QApplication.processEvents()
                doc_to_add = None
                try:
                    doc_to_add = fitz.open(pdf_path)
                    num_pages_in_source = doc_to_add.page_count
                    if num_pages_in_source == 0:
                        print(f"  Skipping '{name}': No pages.")
                        error_files.append(f"{name} (no pages)")
                        doc_to_add.close()
                        continue

                    # --- Bookmark Logic ---
                    source_toc = None
                    has_first_page_bookmark = False
                    try:
                        source_toc = doc_to_add.get_toc(simple=False)
                        if source_toc:
                            has_first_page_bookmark = (
                                self._check_fitz_toc_for_first_page(source_toc)
                            )
                            print(
                                f"  Source ToC: {len(source_toc)} items, has page 1 bookmark: {has_first_page_bookmark}"
                            )
                    except Exception as toc_error:
                        print(
                            f"  WARNING: Could not read ToC for '{name}': {toc_error}"
                        )
                        source_toc = None

                    # Build TOC entries
                    try:
                        if has_first_page_bookmark and source_toc:
                            print(
                                f"  Case 3: Using source ToC with adjusted pages (offset={current_page_offset})"
                            )
                            adjusted_toc = self._adjust_toc_pages_and_levels(
                                source_toc,
                                current_page_offset,
                                doc_to_add,
                                level_increase=0,
                            )
                            if adjusted_toc:
                                final_toc.extend(adjusted_toc)
                            else:
                                print(
                                    f"  WARNING: No valid TOC entries for '{name}' after adjustment."
                                )
                                toc_error_files.append(name)
                        else:
                            # Add top-level bookmark for the file
                            bookmark_title = os.path.splitext(name)[0]
                            file_page_1based = current_page_offset + 1
                            file_dest = {
                                "kind": 1,  # XYZ destination
                                "to": fitz.Point(0, 0),  # Top-left
                                "page": current_page_offset,  # 0-based
                                "zoom": 0.0,
                            }
                            file_entry = [
                                1,
                                bookmark_title,
                                file_page_1based,
                                file_dest,
                            ]
                            print(
                                f"  Case 1/2: Adding file bookmark: Lvl=1, Pg={file_page_1based}, Title='{bookmark_title}'"
                            )
                            final_toc.append(file_entry)

                            if source_toc:
                                print(
                                    f"    Nesting source ToC (offset={current_page_offset}, level_inc=1)"
                                )
                                adjusted_nested_toc = self._adjust_toc_pages_and_levels(
                                    source_toc,
                                    current_page_offset,
                                    doc_to_add,
                                    level_increase=1,
                                )
                                if adjusted_nested_toc:
                                    final_toc.extend(adjusted_nested_toc)
                                else:
                                    print(
                                        f"    WARNING: No valid nested TOC entries for '{name}' after adjustment."
                                    )
                                    toc_error_files.append(name)
                    except Exception as toc_error:
                        print(
                            f"  ERROR: Failed to process TOC for '{name}': {toc_error}"
                        )
                        traceback.print_exc()
                        toc_error_files.append(name)

                    # Insert pages
                    merged_doc.insert_pdf(
                        doc_to_add,
                        from_page=0,
                        to_page=num_pages_in_source - 1,
                        start_at=current_page_offset,
                    )
                    doc_to_add.close()

                    success_count += 1
                    current_page_offset += num_pages_in_source

                except Exception as process_error:
                    print(f"  ERROR processing file '{name}': {process_error}")
                    traceback.print_exc()
                    error_files.append(f"{name} ({type(process_error).__name__})")
                    self.statusBar().showMessage(f"Skipping error in: {name}...", 0)
                    QApplication.processEvents()
                    if doc_to_add and not getattr(doc_to_add, "is_closed", True):
                        try:
                            doc_to_add.close()
                        except:
                            pass

            # --- Finalize Merged Document ---
            if success_count > 0:
                self.statusBar().showMessage("Setting bookmarks & writing file...", 0)
                QApplication.processEvents()
                if final_toc:
                    print(f"\n--- Setting final ToC ({len(final_toc)} entries) ---")
                    # Validate final_toc before setting
                    valid_toc = []
                    for i, entry in enumerate(final_toc):
                        if (
                            isinstance(entry, list)
                            and len(entry) >= 3
                            and isinstance(entry[0], int)
                            and entry[0] >= 1
                            and isinstance(entry[1], str)
                            and entry[1].strip()
                            and isinstance(entry[2], int)
                            and entry[2] >= 1
                            and (len(entry) == 3 or isinstance(entry[3], dict))
                        ):
                            valid_toc.append(entry)
                        else:
                            print(
                                f"  WARNING: Excluding invalid final TOC entry {i}: {entry}"
                            )
                    if not valid_toc:
                        print(
                            "  ERROR: No valid TOC entries after validation. Skipping set_toc."
                        )
                        self.statusBar().showMessage(
                            "Warning: No valid bookmarks could be set.", 5000
                        )
                    else:
                        try:
                            merged_doc.set_toc(valid_toc)
                            print(
                                f"  Successfully set TOC with {len(valid_toc)} entries."
                            )
                        except Exception as set_toc_error:
                            print(f"  ERROR during set_toc: {set_toc_error}")
                            traceback.print_exc()
                            self.statusBar().showMessage(
                                "Warning: Failed to set some bookmarks.", 5000
                            )
                else:
                    print("\n--- No bookmarks to set. ---")
                    self.statusBar().showMessage(
                        "Warning: No bookmarks were set.", 5000
                    )

                if toc_error_files:
                    self.statusBar().showMessage(
                        f"Warning: Bookmark errors in {', '.join(toc_error_files)}.",
                        5000,
                    )

                print(f"--- Writing merged PDF ({merged_doc.page_count} pages) ---")
                try:
                    merged_doc.save(output_path, garbage=4, deflate=True)
                    final_msg = f"Merged {success_count} PDF(s) to {output_path}" + (
                        f" ({len(error_files)} skipped/errors)." if error_files else "."
                    )
                    if toc_error_files:
                        final_msg += (
                            f" Bookmark errors in {len(toc_error_files)} file(s)."
                        )
                    self.statusBar().showMessage(final_msg, 7000)
                    print("--- Merge write successful ---")
                except Exception as save_error:
                    print(f"--- ERROR during final save: {save_error} ---")
                    traceback.print_exc()
                    self.statusBar().showMessage(
                        f"ERROR saving merged file: {save_error}", 6000
                    )

            elif error_files:
                self.statusBar().showMessage(
                    f"Merge failed. {len(error_files)} file(s) had errors/skipped.",
                    5000,
                )
                print("--- Merge failed ---")
            else:
                self.statusBar().showMessage(
                    "No valid PDFs were available to merge.", 5000
                )
                print("--- Merge attempted but no files added ---")

        except Exception as merge_error:
            self.statusBar().showMessage(f"CRITICAL Merge Error: {merge_error}", 6000)
            print(f"--- FATAL Merge Error: {merge_error} ---")
            traceback.print_exc()
        finally:
            if "merged_doc" in locals() and merged_doc is not None:
                try:
                    if not getattr(merged_doc, "is_closed", True):
                        merged_doc.close()
                        print("--- Merged PyMuPDF document closed ---")
                except Exception as e_close:
                    print(f"Warning: Error closing merged document: {e_close}")


# --- Entry Point ---
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = PDFMergerApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred.")
            msg_box.setInformativeText(
                f"Details:\n{e}\n\nSee console for full traceback."
            )
            msg_box.setWindowTitle("Application Error")
            msg_box.exec()
        except Exception:
            pass
        sys.exit(1)
