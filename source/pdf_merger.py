#!/usr/bin/env python3
import sys
import os
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
    QStyle,  # Added for standard icons
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QItemSelection,
    QModelIndex,
    QItemSelectionModel,  # Added for clarity in select_rows
)

# Use 'from PyPDF2 import PdfReader, PdfWriter, PdfMerger' if using PyPDF2 3.0.0+
# Use 'from PyPDF2 import PdfFileReader, PdfFileWriter, PdfFileMerger' for older versions
# Sticking with PdfReader, PdfMerger as per original request for now
from PyPDF2 import PdfReader, PdfMerger


# Custom QTableWidgetItem subclass using data role for better sorting logic
class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            # Extract numeric value from UserRole for comparison
            val1 = float(self.data(Qt.ItemDataRole.UserRole))
            val2 = float(other.data(Qt.ItemDataRole.UserRole))
            return val1 < val2
        except (ValueError, TypeError):
            # Fallback to text comparison if data is not numeric or missing
            print(
                f"Warning: Numeric comparison failed between '{self.text()}' and '{other.text()}'. Falling back to text."
            )
            # It's often better to ensure data IS numeric before creating the item
            return super().__lt__(other)


# Custom QTableWidgetItem subclass using data role for better sorting logic
class DateTimeTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            # Extract datetime object from UserRole for comparison
            dt1 = self.data(Qt.ItemDataRole.UserRole)
            dt2 = other.data(Qt.ItemDataRole.UserRole)
            if isinstance(dt1, datetime) and isinstance(dt2, datetime):
                return dt1 < dt2
            else:
                # Fallback if data is not datetime or missing
                print(
                    f"Warning: DateTime comparison failed between '{self.text()}' and '{other.text()}'. Falling back to text."
                )
                return super().__lt__(other)
        except TypeError:
            # Fallback if comparison fails
            print(
                f"Warning: TypeError during DateTime comparison between '{self.text()}' and '{other.text()}'. Falling back to text."
            )
            return super().__lt__(other)


class PDFMergerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Merger")
        self.setMinimumSize(QSize(600, 400))

        # Internal state for sorting
        self._sort_column = -1  # Column index (-1 for none)
        self._sort_order = Qt.SortOrder.AscendingOrder

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # PDF Table setup
        self.pdf_table = QTableWidget()
        self.pdf_table.setColumnCount(4)
        self.pdf_table.setHorizontalHeaderLabels(
            ["Name", "Size (KB)", "Modified Date", "Pages"]
        )
        self.pdf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.pdf_table.horizontalHeader().setSectionsMovable(True)
        self.pdf_table.horizontalHeader().setSectionsClickable(
            True
        )  # Essential for sorting clicks

        self.pdf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Enable drag and drop for rows
        self.pdf_table.setDragEnabled(True)
        self.pdf_table.setAcceptDrops(True)
        self.pdf_table.setDropIndicatorShown(True)
        self.pdf_table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove  # Reorder rows within the table
        )
        self.pdf_table.setDragDropOverwriteMode(False)  # Must be False for InternalMove
        self.pdf_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )  # Read-only table
        self.pdf_table.setSortingEnabled(
            False
        )  # Disable Qt's built-in sorting; we handle it manually

        # Connect signals
        self.pdf_table.horizontalHeader().sectionClicked.connect(
            self.handle_header_click
        )
        self.pdf_table.model().rowsMoved.connect(self.on_rows_moved)

        self.layout.addWidget(self.pdf_table)

        # Buttons layout
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

        # Output settings
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output File:"))
        self.output_name = QLineEdit("merged_output.pdf")
        output_layout.addWidget(self.output_name)

        self.output_dir_btn = QPushButton("Set Output Directory")
        self.output_dir_btn.clicked.connect(self.set_output_directory)
        output_layout.addWidget(self.output_dir_btn)

        self.layout.addLayout(output_layout)

        # Status Bar
        self.setStatusBar(QStatusBar(self))

        # Initialize data
        self.output_dir = os.path.expanduser("~")  # Default to user's home directory
        # Store full path and metadata for each file
        # List of tuples: (full_path, name, size_kb_float, modified_datetime, pages_int)
        self.pdf_files_data = []

    def add_pdfs(self):
        """Add PDF files, storing data and updating the table."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", self.output_dir, "PDF Files (*.pdf)"
        )
        if not files:
            return  # User cancelled

        added_count = 0
        errors = []
        new_files_data = []  # Collect new data before adding to main list
        existing_paths = {
            data[0] for data in self.pdf_files_data
        }  # Check existing full paths

        for file_path in files:
            if file_path in existing_paths:
                print(f"Skipping duplicate: {os.path.basename(file_path)}")
                continue

            try:
                file_stats = os.stat(file_path)
                file_name = os.path.basename(file_path)
                file_size_kb = file_stats.st_size / 1024.0
                modified_dt = datetime.fromtimestamp(file_stats.st_mtime)
                pages = 0

                try:
                    # Use 'with' for automatic file closing (important!)
                    with open(file_path, "rb") as f:
                        reader = PdfReader(
                            f, strict=False
                        )  # Be lenient with PDF structure
                        pages = len(reader.pages)
                except Exception as page_error:
                    error_msg = f"Could not read pages from '{file_name}': {page_error}"
                    print(error_msg)
                    errors.append(error_msg)
                    # Add file even if pages couldn't be read (shows 0 pages)

                # Append tuple with correct data types
                new_files_data.append(
                    (file_path, file_name, file_size_kb, modified_dt, pages)
                )
                added_count += 1
                existing_paths.add(
                    file_path
                )  # Add to set to catch duplicates within the same selection run
                print(
                    f"Prepared: {file_name}, Size: {file_size_kb:.1f} KB, Mod: {modified_dt}, Pages: {pages}"
                )

            except OSError as stat_error:
                error_msg = f"Error accessing file '{os.path.basename(file_path)}': {stat_error}"
                print(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = (
                    f"Unexpected error adding '{os.path.basename(file_path)}': {e}"
                )
                print(error_msg)
                errors.append(error_msg)

        if added_count > 0:
            self.pdf_files_data.extend(new_files_data)  # Add all new files at once
            print(f"Data list length after adding: {len(self.pdf_files_data)}")

            # Apply current sort *before* populating if a sort is active
            if self._sort_column != -1:
                print(
                    f"Applying existing sort: col={self._sort_column}, order={self._sort_order}"
                )
                self.sort_data(
                    self._sort_column, self._sort_order
                )  # Sort the combined data list

            print("Calling populate_table after adding files...")
            self.populate_table()  # Refresh the table display

            msg = f"Added {added_count} PDF(s)."
            if errors:
                msg += f" Encountered {len(errors)} error(s)."
            self.statusBar().showMessage(msg, 5000)  # Show message for 5 seconds
        elif files and not errors:  # Files were selected, but all were duplicates
            self.statusBar().showMessage("Selected PDF(s) already in list.", 3000)
        elif errors:  # No files added, but errors occurred
            self.statusBar().showMessage(
                f"Failed to add files. Encountered {len(errors)} error(s).", 5000
            )

    def populate_table(self):
        """Populate the table widget from the self.pdf_files_data list."""
        print(f"--- populate_table called ---")
        print(f"--- Source data list length: {len(self.pdf_files_data)} ---")

        # Use setUpdatesEnabled for efficiency during bulk changes
        self.pdf_table.setUpdatesEnabled(False)

        # Clear existing rows and set new count
        self.pdf_table.setRowCount(0)
        new_row_count = len(self.pdf_files_data)
        self.pdf_table.setRowCount(new_row_count)
        print(
            f"--- Set table row count to: {new_row_count} (Actual: {self.pdf_table.rowCount()}) ---"
        )

        # Check if row count was set correctly
        if self.pdf_table.rowCount() != new_row_count:
            print(
                "!!! WARNING: Row count mismatch after setRowCount! Table update might fail."
            )
            self.pdf_table.setUpdatesEnabled(
                True
            )  # Ensure updates are re-enabled on early exit
            return

        print(f"--- Starting item population loop ---")
        for row, pdf_data in enumerate(self.pdf_files_data):
            path, name, size_kb, modified_dt, pages = pdf_data

            # Create items with text for display AND store raw data in UserRole
            name_item = QTableWidgetItem(name)
            size_item = NumericTableWidgetItem(
                f"{size_kb:.1f}"
            )  # Display formatted size
            modified_item = DateTimeTableWidgetItem(
                modified_dt.strftime("%Y-%m-%d %H:%M")
            )  # Display formatted date
            pages_item = NumericTableWidgetItem(str(pages))  # Display page count

            # Store raw data for sorting/tooltips
            name_item.setData(
                Qt.ItemDataRole.UserRole, path
            )  # Store path for tooltip/reference
            size_item.setData(
                Qt.ItemDataRole.UserRole, size_kb
            )  # Store float for sorting
            modified_item.setData(
                Qt.ItemDataRole.UserRole, modified_dt
            )  # Store datetime for sorting
            pages_item.setData(Qt.ItemDataRole.UserRole, pages)  # Store int for sorting

            # Add Tooltips
            name_item.setToolTip(f"Path: {path}\nName: {name}")
            size_item.setToolTip(f"{size_kb:.3f} KB")  # More precision in tooltip
            modified_item.setToolTip(
                f"Modified: {modified_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            )  # Full timestamp
            pages_item.setToolTip(f"{pages} pages")

            # Set common flags (Selectable, Enabled, Draggable)
            flags = (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            name_item.setFlags(flags)
            size_item.setFlags(flags)
            modified_item.setFlags(flags)
            pages_item.setFlags(flags)

            # Set items in the table row
            self.pdf_table.setItem(row, 0, name_item)
            self.pdf_table.setItem(row, 1, size_item)
            self.pdf_table.setItem(row, 2, modified_item)
            self.pdf_table.setItem(row, 3, pages_item)

        # Re-enable updates *after* the loop
        self.pdf_table.setUpdatesEnabled(True)

        # Update Sort Indicator in Header
        print("--- Updating sort indicator ---")
        if self._sort_column != -1:
            print(
                f"--- Setting indicator: col={self._sort_column}, order={self._sort_order} ---"
            )
            self.pdf_table.horizontalHeader().setSortIndicator(
                self._sort_column, self._sort_order
            )
            self.pdf_table.horizontalHeader().setSortIndicatorShown(True)
        else:
            print("--- Hiding sort indicator ---")
            self.pdf_table.horizontalHeader().setSortIndicatorShown(
                False
            )  # Hide indicator if no sort active

        # Optional: Force repaint if needed (usually setUpdatesEnabled handles this)
        # self.pdf_table.viewport().update()
        print("--- populate_table finished ---")

    def remove_selected_pdfs(self):
        """Remove selected rows from the table and the underlying data."""
        # Get selected row indices (QModelIndex list)
        selected_indices = self.pdf_table.selectionModel().selectedRows()
        if not selected_indices:
            self.statusBar().showMessage("No rows selected to remove.", 3000)
            return

        # Get row numbers and sort descending to avoid index shifting issues during removal
        rows_to_remove = sorted(
            [index.row() for index in selected_indices], reverse=True
        )

        removed_count = 0
        print(f"Removing rows (indices): {rows_to_remove}")
        # Remove from the data list first
        for row in rows_to_remove:
            if 0 <= row < len(self.pdf_files_data):
                removed_name = self.pdf_files_data[row][1]  # Get name for logging
                del self.pdf_files_data[row]
                print(f"  Removed data for: {removed_name} at index {row}")
                removed_count += 1
            else:
                print(f"  Skipping invalid row index for removal: {row}")

        if removed_count > 0:
            print(f"Data list length after removal: {len(self.pdf_files_data)}")
            print("Calling populate_table after removal...")
            self.populate_table()  # Refresh the table view completely
            self.statusBar().showMessage(f"Removed {removed_count} PDF(s)", 3000)
        else:
            print("No valid rows found in data list corresponding to selection.")

    def on_rows_moved(self, parent, start, end, destination, row):
        """Update self.pdf_files_data list after rows have been moved via drag/drop."""
        # Ignore moves involving different models or parents
        if parent.isValid() or destination.isValid():
            return

        # --- Basic validation of signal indices ---
        source_model_row_count = (
            self.pdf_table.rowCount()
        )  # Rows currently VISIBLE before move finishes
        if start < 0 or end < start or end >= source_model_row_count or row < -1:
            print(
                f"Warning: Invalid indices received in on_rows_moved signal: start={start}, end={end}, row={row}, view_rows={source_model_row_count}. Ignoring move."
            )
            # It might be safer to repopulate from data if signals are unreliable
            # self.populate_table()
            return

        print(
            f"on_rows_moved signal: Moving view rows {start}-{end} to before view row {row}"
        )
        count = end - start + 1
        current_data_len = len(self.pdf_files_data)

        # --- More robust index check against the *data* list length BEFORE modification ---
        # The 'start' and 'end' indices should correspond to the data list *before* the move.
        if end >= current_data_len:
            print(
                f"ERROR: Move signal 'end' index ({end}) is out of bounds for data list (len={current_data_len}). View/data mismatch? Repopulating."
            )
            self.populate_table()  # Data and view seem out of sync, refresh from data
            return

        # --- Determine the target insertion index in the *data* list ---
        # 'row' is the view index *before which* the items are inserted.
        # If row == -1 or row >= current_data_len (or view row count), it means move to the very end of the data list.
        target_row_in_data = (
            current_data_len if (row == -1 or row >= current_data_len) else row
        )

        try:
            # --- Perform the move in the data list ---
            print(
                f"  Data before move ({current_data_len} items): {[item[1] for item in self.pdf_files_data]}"
            )  # Show names
            moved_items = self.pdf_files_data[
                start : end + 1
            ]  # Slice the items being moved
            print(f"  Items being moved: {[item[1] for item in moved_items]}")

            # Create a temporary list *without* the moved items
            temp_list = self.pdf_files_data[:start] + self.pdf_files_data[end + 1 :]

            # Calculate the correct insertion index in the *temp_list*
            # If the items were moved *downwards* (start < target_row_in_data),
            # the target index needs adjustment because items *before* it were removed.
            insert_index_in_temp = target_row_in_data
            if start < target_row_in_data:
                insert_index_in_temp -= count  # Adjust downwards

            # Clamp index to valid range [0, len(temp_list)] for insertion
            insert_index_in_temp = max(0, min(insert_index_in_temp, len(temp_list)))
            print(f"  Calculated insertion index in temp list: {insert_index_in_temp}")

            # Reconstruct the data list in the new order
            self.pdf_files_data = (
                temp_list[:insert_index_in_temp]
                + moved_items
                + temp_list[insert_index_in_temp:]
            )
            print(
                f"  Data after move ({len(self.pdf_files_data)} items): {[item[1] for item in self.pdf_files_data]}"
            )

            # --- Drag/drop resets any active sorting ---
            print("--- Rows moved via drag/drop, resetting sort state ---")
            self._sort_column = -1
            self._sort_order = Qt.SortOrder.AscendingOrder
            # The sort indicator will be hidden by the subsequent populate_table call

            # --- CRITICAL: Re-populate the table to ensure view matches data ---
            # Don't just rely on the visual move performed by Qt's view mechanism.
            print("--- Calling populate_table after internal data reorder ---")
            self.populate_table()

            # --- Reselect the moved rows visually in their new positions ---
            # The new visual position corresponds to insert_index_in_temp
            new_visual_start_row = insert_index_in_temp
            new_visual_end_row = new_visual_start_row + count - 1
            print(
                f"--- Reselecting rows {new_visual_start_row} to {new_visual_end_row} ---"
            )
            self.select_rows(new_visual_start_row, new_visual_end_row)

        except IndexError as e:
            print(f"ERROR: IndexError during list manipulation in on_rows_moved: {e}")
            print(
                f"State: start={start}, end={end}, row={row}, target_idx={target_row_in_data}, data_len={current_data_len}"
            )
            print("--- Repopulating table due to IndexError ---")
            self.populate_table()  # Attempt to recover view state
        except Exception as e:
            print(f"ERROR: Unexpected error in on_rows_moved: {e}")
            import traceback

            traceback.print_exc()
            print("--- Repopulating table due to unexpected error ---")
            self.populate_table()  # Attempt to recover view state

    def select_rows(self, start_row, end_row):
        """Selects a range of rows in the table visually."""
        # Check against the current table row count AFTER any repopulation
        current_row_count = self.pdf_table.rowCount()
        if not (
            0 <= start_row < current_row_count
            and 0 <= end_row < current_row_count
            and start_row <= end_row
        ):
            print(
                f"Warning: Invalid row range for selection ({start_row}-{end_row}), table has {current_row_count} rows. Skipping."
            )
            return

        selection_model = self.pdf_table.selectionModel()
        selection_model.clearSelection()  # Clear previous selections
        item_selection = QItemSelection()

        # Create a selection range covering the desired rows
        for r in range(start_row, end_row + 1):
            # Get QModelIndex for the first and last column of the row 'r'
            top_left_index = self.pdf_table.model().index(r, 0)
            bottom_right_index = self.pdf_table.model().index(
                r, self.pdf_table.columnCount() - 1
            )

            # Ensure indices are valid before adding to selection range
            if top_left_index.isValid() and bottom_right_index.isValid():
                item_selection.select(
                    top_left_index, bottom_right_index
                )  # Add this row range
            else:
                # This shouldn't happen if row range check passed, but is a safeguard
                print(
                    f"Warning: Could not get valid QModelIndex for row {r} during selection."
                )

        if not item_selection.isEmpty():
            # Apply the selection to the model, selecting full rows
            selection_model.select(
                item_selection,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            print(f"Selected rows {start_row}-{end_row}")
        else:
            print("Item selection was empty, no rows selected.")

    def handle_header_click(self, logical_index):
        """Handles clicking on a header section to sort the data and update the view."""
        print(f"Header clicked: column {logical_index}")
        # Basic validation
        if logical_index < 0 or logical_index >= self.pdf_table.columnCount():
            print("Warning: Invalid column index received from header click.")
            return

        # Determine the new sort order
        if self._sort_column == logical_index:
            # Toggle order if the same column is clicked again
            new_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            # Default to ascending order for a newly clicked column
            new_order = Qt.SortOrder.AscendingOrder

        # Update internal sort state
        self._sort_column = logical_index
        self._sort_order = new_order

        # Sort the underlying data list
        print(f"Sorting data by column {self._sort_column}, order {self._sort_order}")
        self.sort_data(self._sort_column, self._sort_order)

        # Repopulate the table to show sorted data and update the sort indicator
        print("Calling populate_table after sorting...")
        self.populate_table()

    def sort_data(self, column, order):
        """Sorts the self.pdf_files_data list IN PLACE based on column index and order."""
        reverse_sort = order == Qt.SortOrder.DescendingOrder
        sort_key = None

        # Define the sort key based on the column index, accessing the correct tuple element
        if column == 0:  # Name (string, case-insensitive)
            sort_key = lambda item: item[1].lower()
        elif column == 1:  # Size (float)
            sort_key = lambda item: item[2]
        elif column == 2:  # Modified Date (datetime object)
            sort_key = lambda item: item[3]
        elif column == 3:  # Pages (integer)
            sort_key = lambda item: item[4]
        else:
            print(f"ERROR: Invalid sort column index {column}")
            return  # Should not happen if header click index is validated

        # Perform the sort on the data list
        try:
            self.pdf_files_data.sort(key=sort_key, reverse=reverse_sort)
            print("--- Data sorting complete ---")
        except Exception as e:
            print(f"ERROR: Exception during data sorting: {e}")
            self.statusBar().showMessage(f"Sorting error: {e}", 5000)
            # Optionally reset sort state if sorting fails critically
            # self._sort_column = -1
            # self.populate_table() # Refresh view even if sort failed?

    def set_output_directory(self):
        """Opens a dialog to select the output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir,  # Start in current output dir
        )
        if directory:  # Only update if a directory was selected (user didn't cancel)
            self.output_dir = directory
            self.statusBar().showMessage(
                f"Output directory set to: {self.output_dir}", 3000
            )

    def _add_bookmarks_recursively(
        self, reader, merger, parent_bookmark, outline_items, page_offset
    ):
        """
        Recursive helper function to add bookmarks from a reader's outline
        to the merger, nested under a parent bookmark.

        Args:
            reader: The PdfReader instance for the source PDF.
            merger: The PdfMerger instance being built.
            parent_bookmark: The outline item in the merger to attach children to (can be None for top level).
            outline_items: A list of outline items from the reader's outline (can be nested lists or OutlineItem objects).
            page_offset: The page number offset for this PDF in the merged document.
        """
        if not outline_items:  # Base case for recursion
            return

        for item in outline_items:
            # PyPDF2's outline can be a list of OutlineItem objects or nested lists
            if isinstance(item, list):
                # This level doesn't have its own title, just contains children. Recurse deeper.
                # The parent remains the same for the items within this list.
                self._add_bookmarks_recursively(
                    reader, merger, parent_bookmark, item, page_offset
                )
            else:
                # Assume 'item' is an OutlineItem object (or similar dict-like structure in older PyPDF2)
                try:
                    # Safely get title and destination page number
                    title = item.title  # Direct access assumed for OutlineItem
                    # Use get_destination_page_number for robustness across destination types
                    original_page_num = reader.get_destination_page_number(item)

                    if title is not None and original_page_num is not None:
                        # Calculate the page number in the final merged document
                        merged_page_num = original_page_num + page_offset

                        # Add the bookmark to the merger, nested under the parent
                        print(
                            f"      Adding nested bookmark: '{title}' -> page {merged_page_num} (original {original_page_num}) under parent: {parent_bookmark}"
                        )
                        current_new_bookmark = merger.add_outline_item(
                            title, merged_page_num, parent=parent_bookmark
                        )

                        # --- Process children of this item ---
                        # Check if the item itself has children (common in OutlineItem structure)
                        if hasattr(item, "children") and item.children:
                            print(f"      '{title}' has children, recursing...")
                            self._add_bookmarks_recursively(
                                reader,
                                merger,
                                current_new_bookmark,
                                item.children,
                                page_offset,
                            )
                        # Note: If the structure was purely nested lists, the isinstance check above handles it.

                    else:
                        # Log if essential info is missing
                        print(
                            f"      Skipping bookmark: Invalid title or page number found (Title: {title}, Orig Page: {original_page_num})"
                        )

                except Exception as bookmark_error:
                    # Catch errors reading/processing a specific bookmark (e.g., malformed destination)
                    item_title_str = getattr(
                        item, "title", "[Unknown Title]"
                    )  # Safely get title for error msg
                    print(
                        f"      WARNING: Error processing bookmark '{item_title_str}': {bookmark_error}. Skipping."
                    )
                    # Continue with the next bookmark in the list

    def merge_pdfs(self):
        """Merge PDFs based on the current order in self.pdf_files_data, preserving and nesting bookmarks."""
        if not self.pdf_files_data:
            self.statusBar().showMessage("No PDFs loaded to merge.", 3000)
            return

        output_filename = self.output_name.text().strip()
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"merged_output_{timestamp}.pdf"
            self.output_name.setText(output_filename)  # Update the field

        if not output_filename.lower().endswith(".pdf"):
            output_filename += ".pdf"
            self.output_name.setText(output_filename)  # Update field if extension added

        output_path = os.path.join(self.output_dir, output_filename)

        # Confirm overwrite
        if os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                f"The file already exists:\n{output_path}\n\nDo you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # Default button
            )
            if reply == QMessageBox.StandardButton.No:
                self.statusBar().showMessage("Merge cancelled.", 3000)
                return

        merger = PdfMerger()
        self.statusBar().showMessage(
            "Merging started (processing bookmarks)...", 0
        )  # Persistent message
        QApplication.processEvents()  # Allow UI update

        success_count = 0
        error_files = []
        current_page_offset = 0  # Track page count *before* adding the current PDF

        try:
            print(f"--- Starting merge process. Output: {output_path} ---")
            print(f"--- Merging {len(self.pdf_files_data)} files in current order ---")

            # Iterate through the *current order* of pdf_files_data
            for pdf_path, name, _, _, _ in self.pdf_files_data:
                print(f"\n  Processing file: {name} ({pdf_path})")
                self.statusBar().showMessage(f"Processing: {name}...", 0)
                QApplication.processEvents()

                try:
                    # 1. Open the source PDF with PdfReader FIRST to access pages and outline
                    # Use 'with' context manager if PdfReader supports it, otherwise ensure closed.
                    # However, merger.append often handles file opening/closing itself.
                    # Opening here primarily to read metadata *before* appending.
                    reader = PdfReader(pdf_path, strict=False)
                    num_pages_in_source = len(reader.pages)

                    # Skip files with no pages
                    if num_pages_in_source == 0:
                        print(f"    Skipping '{name}': No pages found in file.")
                        error_files.append(f"{name} (no pages)")
                        continue  # Move to the next file in the list

                    # 2. Add the top-level bookmark for this file to the merger
                    # Use filename without extension as the default bookmark title
                    bookmark_title = os.path.splitext(name)[0]
                    print(
                        f"    Adding top-level bookmark: '{bookmark_title}' -> page {current_page_offset}"
                    )
                    # This bookmark points to the *start* page of this PDF within the merged document
                    parent_bookmark_obj = merger.add_outline_item(
                        bookmark_title,
                        current_page_offset,  # Page number where this file begins
                        # parent=None implicitly adds it at the top level
                    )

                    # 3. Process the original bookmarks from the source PDF recursively
                    try:
                        source_outline = reader.outline  # Get the outline structure
                        if source_outline:
                            print(
                                f"    Found original bookmarks in '{name}'. Processing..."
                            )
                            # Start the recursive function to add them under the parent bookmark
                            self._add_bookmarks_recursively(
                                reader,
                                merger,
                                parent_bookmark_obj,  # The bookmark created above is the parent
                                source_outline,  # The list/structure of original outline items
                                current_page_offset,  # Page offset needed to adjust destinations
                            )
                        else:
                            print("    No original bookmarks found in this file.")
                    except Exception as outline_read_error:
                        # Log error if outline itself is corrupt/unreadable but continue merge
                        print(
                            f"    WARNING: Could not read or process outline structure for '{name}': {outline_read_error}"
                        )
                        # Allow merging the pages even if bookmarks failed

                    # 4. Append the actual pages of the source PDF to the merger
                    # This should happen *after* outline processing to ensure correct page offsets
                    merger.append(pdf_path)
                    print(
                        f"    Appended {num_pages_in_source} pages. Total merger pages now: {len(merger.pages)}"
                    )
                    success_count += 1

                    # 5. CRITICAL: Update the page offset for the NEXT file
                    # The offset for the next file is the total number of pages currently in the merger
                    current_page_offset = len(merger.pages)

                except Exception as process_error:
                    # Catch errors during PdfReader init, page append, or general processing for *this specific file*
                    print(f"    ERROR processing file '{name}': {process_error}")
                    error_files.append(
                        f"{name} ({type(process_error).__name__})"
                    )  # Record filename and error type
                    self.statusBar().showMessage(
                        f"Skipping problematic file: {name}...", 0
                    )
                    QApplication.processEvents()
                    # Do not update page offset if the file failed to process/append

            # --- End of loop through files ---

            if success_count > 0:
                # Only write if at least one file was successfully processed
                self.statusBar().showMessage("Writing merged file...", 0)
                QApplication.processEvents()
                print(
                    f"\n--- Writing {success_count} merged PDF(s) ({len(merger.pages)} total pages) to file ---"
                )
                with open(output_path, "wb") as output_file:
                    merger.write(output_file)  # Write the merged content

                final_msg = (
                    f"Merged {success_count} PDF(s) successfully to {output_path}"
                )
                if error_files:
                    final_msg += f" ({len(error_files)} file(s) skipped or had errors)."
                self.statusBar().showMessage(
                    final_msg, 7000
                )  # Show success message longer
                print("--- Merge write successful ---")
            elif error_files:
                # No files succeeded, but there were errors
                self.statusBar().showMessage(
                    f"Merge failed. {len(error_files)} file(s) had errors or were skipped.",
                    5000,
                )
                print("--- Merge failed, all files had errors or were skipped ---")
            else:
                # Initial list was non-empty, but no files were added (e.g., all had 0 pages)
                # This case might be covered by the error_files list, but is a fallback.
                self.statusBar().showMessage(
                    "No valid PDFs were available to merge after processing.", 5000
                )
                print("--- Merge attempted but no files were valid or added ---")

        except Exception as merge_error:
            # Catch potential errors during the final merger.write() or other unexpected issues
            self.statusBar().showMessage(
                f"CRITICAL Error during merge process: {merge_error}", 6000
            )
            print(f"--- FATAL ERROR during merge process: {merge_error} ---")
            import traceback

            traceback.print_exc()
        finally:
            # Always try to close the merger object to release resources
            try:
                merger.close()
                print("--- PdfMerger closed ---")
            except Exception as close_error:
                # Log if closing fails, but don't prevent app from continuing if possible
                print(f"Warning: Error closing PdfMerger object: {close_error}")


if __name__ == "__main__":
    # It's good practice to wrap the app execution in a try/except
    # to catch potential initialization errors or critical failures.
    try:
        app = QApplication(sys.argv)

        # Optional: Attributes for better handling of High DPI displays
        # try:
        #     app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        #     app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        #     print("High DPI attributes set.")
        # except AttributeError:
        #     print("High DPI attributes not available in this Qt version.")

        window = PDFMergerApp()
        window.show()
        sys.exit(app.exec())  # Start the Qt event loop

    except Exception as e:
        # Catch any exception during app setup or execution
        print(f"FATAL ERROR during application startup or execution: {e}")
        import traceback

        traceback.print_exc()
        # Attempt to show a simple message box if the GUI system is partially available
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred.")
            # Be cautious about showing full exception details in production
            msg_box.setInformativeText(
                f"Details:\n{e}\n\nSee console for full traceback."
            )
            msg_box.setWindowTitle("Application Error")
            msg_box.exec()
        except Exception:
            pass  # Ignore if GUI isn't even available for the message box
        sys.exit(1)  # Exit with a non-zero code to indicate failure
