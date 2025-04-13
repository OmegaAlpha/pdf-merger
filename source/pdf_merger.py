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
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    QItemSelection,
    QModelIndex,
)  # Added QItemSelection, QModelIndex
from PyPDF2 import PdfReader, PdfMerger  # Using PyPDF2 as in original code


class PDFMergerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Merger")
        self.setMinimumSize(QSize(600, 400))

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
        self.pdf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Enable drag and drop for rows
        self.pdf_table.setDragEnabled(True)
        self.pdf_table.setAcceptDrops(True)
        self.pdf_table.setDropIndicatorShown(True)  # Show where the drop will occur
        self.pdf_table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove  # Correct mode for reordering
        )
        # Crucial: Prevent Qt from trying to overwrite items during its default move
        self.pdf_table.setDragDropOverwriteMode(False)

        # Make items non-editable by default
        self.pdf_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Connect header click for manual sorting
        self.pdf_table.horizontalHeader().sectionClicked.connect(self.sort_table)

        # Connect to the model's rowsMoved signal
        self.pdf_table.model().rowsMoved.connect(self.on_rows_moved)

        self.layout.addWidget(self.pdf_table)

        # Buttons layout
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add PDFs")
        self.add_btn.clicked.connect(self.add_pdfs)
        btn_layout.addWidget(self.add_btn)

        # Add Remove Button
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
        self.setStatusBar(QStatusBar(self))  # Explicitly create and set status bar

        # Initialize data
        self.output_dir = os.path.expanduser("~")  # Default to home directory
        self.pdf_files = (
            []
        )  # List of tuples: (path, name, size (float), modified (datetime), pages (int))

    def add_pdfs(self):
        """Add PDF files to the table."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", self.output_dir, "PDF Files (*.pdf)"
        )
        if not files:  # No files selected
            return

        added_count = 0
        errors = []  # Keep track of errors

        for file_path in files:
            # Check if the file (by path) is already in the list
            if file_path in [f[0] for f in self.pdf_files]:
                print(f"Skipping duplicate: {os.path.basename(file_path)}")
                continue  # Skip to next file

            try:
                file_stats = os.stat(file_path)
                file_name = os.path.basename(file_path)
                file_size = file_stats.st_size / 1024
                modified = datetime.fromtimestamp(file_stats.st_mtime)

                # Use try-except specifically for PdfReader errors
                pages = 0  # Default pages to 0
                try:
                    # Make sure strict=False if you encounter slightly non-compliant PDFs
                    reader = PdfReader(file_path, strict=False)
                    pages = len(reader.pages)
                except Exception as page_error:
                    # This specific file has an issue reading pages, log it but still add the file
                    error_msg = f"Could not read pages from '{file_name}': {page_error}"
                    print(error_msg)  # Print to console for debugging
                    errors.append(error_msg)  # Add to list for status bar summary

                # Append even if page count failed (shows 0 pages)
                self.pdf_files.append(
                    (file_path, file_name, file_size, modified, pages)
                )
                added_count += 1
                print(f"Added: {file_name}, Pages: {pages}")  # Debug print

            except OSError as stat_error:
                # Error accessing file stats (permissions, not found after selection?)
                error_msg = f"Error accessing file '{os.path.basename(file_path)}': {stat_error}"
                print(error_msg)
                errors.append(error_msg)
            except Exception as e:
                # Catch other potential errors during processing
                error_msg = (
                    f"Unexpected error adding '{os.path.basename(file_path)}': {e}"
                )
                print(error_msg)
                errors.append(error_msg)

        if added_count > 0:
            print(f"Calling update_table after adding {added_count} files.")
            # Optional: sort initially if desired
            # self.pdf_files.sort(key=lambda x: x[1].lower())
            self.update_table()  # Refresh the display
            msg = f"Added {added_count} PDF(s)."
            if errors:
                msg += f" Encountered {len(errors)} error(s) (see console/logs)."
            self.statusBar().showMessage(msg, 5000)
        elif files and not errors:
            self.statusBar().showMessage("Selected PDF(s) already in list.", 3000)
        elif errors:
            self.statusBar().showMessage(
                f"Failed to add files. Encountered {len(errors)} error(s).", 5000
            )

    # --- THIS IS THE DEBUGGING VERSION OF update_table ---
    def update_table(self):
        """Update the table display based on self.pdf_files."""
        print("--- update_table called ---")
        print(f"--- self.pdf_files length: {len(self.pdf_files)}")
        # print(f"--- Full self.pdf_files data: {self.pdf_files}") # Optional: uncomment for full data view

        # --- Check Table Visibility ---
        if not self.pdf_table.isVisible():
            print("!!! WARNING: pdf_table is not visible !!!")
        if self.pdf_table.isHidden():
            print("!!! WARNING: pdf_table is hidden !!!")
        print(
            f"--- pdf_table geometry: {self.pdf_table.geometry()} ---"
        )  # Check size/position

        # --- Method 1: Standard Clear and Repopulate (Focus on basics) ---
        try:
            # Block signals (generally good practice, but keep commented if debugging signal issues)
            # self.pdf_table.model().blockSignals(True)

            print(f"--- Setting row count to: {len(self.pdf_files)} ---")
            # Clear existing rows first *before* setting new count
            self.pdf_table.setRowCount(0)
            # Now set the required number of rows
            self.pdf_table.setRowCount(len(self.pdf_files))

            print(f"--- Table row count after setting: {self.pdf_table.rowCount()} ---")
            print(
                f"--- Table column count: {self.pdf_table.columnCount()} ---"
            )  # Should be 4

            if self.pdf_table.rowCount() == 0 and len(self.pdf_files) > 0:
                print(
                    "!!! ERROR: Row count is 0 even though data exists and setRowCount was called."
                )
                # self.pdf_table.model().blockSignals(False) # Unblock if blocked
                return  # Stop if rows couldn't be set

            # Proceed with populating cells
            for row, pdf_data in enumerate(self.pdf_files):
                path, name, size, modified, pages = pdf_data
                print(f"  Populating row {row}: {name}")

                # Create basic items - ensure data types are correct
                name_item = QTableWidgetItem(str(name))  # Ensure string
                size_item = QTableWidgetItem(
                    f"{float(size):.1f}"
                )  # Ensure float format
                modified_item = QTableWidgetItem(modified.strftime("%Y-%m-%d %H:%M"))
                pages_item = QTableWidgetItem(str(pages))  # Ensure string

                # Explicitly check if item creation worked
                if name_item is None:
                    print(
                        f"!!! ERROR: Failed to create QTableWidgetItem for name at row {row}"
                    )
                    continue  # Skip this row if item creation fails

                # Set items for the current row
                self.pdf_table.setItem(row, 0, name_item)
                self.pdf_table.setItem(row, 1, size_item)
                self.pdf_table.setItem(row, 2, modified_item)
                self.pdf_table.setItem(row, 3, pages_item)

                # Verify item was set (optional detailed check)
                # check = self.pdf_table.item(row, 0)
                # if check:
                #     print(f"    Item(row={row}, col=0) text after set: '{check.text()}'")
                # else:
                #     print(f"!!! WARNING: Item(row={row}, col=0) is None immediately after setting!")

            # self.pdf_table.model().blockSignals(False) # Unblock if blocked

            # --- Force a repaint/update ---
            print("--- Forcing table repaint ---")
            self.pdf_table.viewport().update()  # Try to force a redraw of the viewport

        except Exception as e:
            print(f"!!! UNEXPECTED ERROR in update_table: {e} !!!")
            import traceback  # Import here for error case

            traceback.print_exc()  # Print full traceback for deep errors
            # Make sure signals are unblocked if an error occurred
            # self.pdf_table.model().blockSignals(False)

        # --- Final Check ---
        final_row_count = self.pdf_table.rowCount()
        print(f"--- update_table finished. Final row count: {final_row_count} ---")
        if final_row_count > 0:
            # Check first row, first column item exists
            item_check = self.pdf_table.item(0, 0)
            if item_check:
                print(f"--- Final check: item(0,0) text = '{item_check.text()}' ---")
            else:
                # If item is None, maybe the row exists but item setting failed earlier
                print("--- Final check: item(0,0) is None! ---")
            # Also check last row to be sure population likely completed
            last_row_item_check = self.pdf_table.item(final_row_count - 1, 0)
            if last_row_item_check:
                print(
                    f"--- Final check: item({final_row_count-1},0) text = '{last_row_item_check.text()}' ---"
                )
            else:
                print(f"--- Final check: item({final_row_count-1},0) is None! ---")

    def remove_selected_pdfs(self):
        """Remove selected rows from the table and the underlying data."""
        selected_indices = (
            self.pdf_table.selectionModel().selectedRows()
        )  # Get QModelIndex list
        if not selected_indices:
            self.statusBar().showMessage("No rows selected to remove.", 3000)
            return

        # Get row numbers and sort in descending order to avoid index shifting issues during removal
        rows_to_remove = sorted(
            [index.row() for index in selected_indices], reverse=True
        )

        removed_count = 0
        # Remove from the data list first
        for row in rows_to_remove:
            if 0 <= row < len(self.pdf_files):
                del self.pdf_files[row]
                removed_count += 1

        # Update the table to reflect the changes
        if removed_count > 0:
            self.update_table()  # Call the debugging version
            self.statusBar().showMessage(f"Removed {removed_count} PDF(s)", 3000)

    def on_rows_moved(self, parent, start, end, destination, row):
        """
        Update self.pdf_files list *after* rows have been moved in the table view.
        """
        if (
            parent.isValid() or destination.isValid()
        ):  # Should not happen in simple table move
            return

        # Ensure indices are somewhat sane before proceeding
        if start < 0 or end < start or row < -1:  # row can be -1 for move to end
            print(
                f"Warning: Invalid indices received in on_rows_moved: start={start}, end={end}, row={row}"
            )
            return  # Avoid processing potentially corrupt move signal data

        count = end - start + 1
        effective_row_count = len(self.pdf_files)  # Count before potential modification

        # Determine target index, handling move to the end
        # 'row' is the index *before which* items are inserted.
        # If row == -1 or row >= effective_row_count, it means move to the very end.
        if row == -1 or row >= effective_row_count:
            target_row = effective_row_count  # Index for appending
        else:
            target_row = row

        # Check if the source range is valid relative to current list size
        if end >= effective_row_count:
            print(
                f"Warning: Invalid source range in on_rows_moved: end={end}, current list length={effective_row_count}"
            )
            # As a fallback, maybe just refresh the table from current data?
            self.update_table()
            return

        # --- Logic to reorder self.pdf_files ---
        try:
            # 1. Get the items being moved (make sure indices are valid)
            if start >= 0 and end < len(self.pdf_files) and start <= end:
                moved_items = self.pdf_files[start : end + 1]
            else:
                print("Error: Invalid index range for slicing moved items.")
                self.update_table()  # Refresh to be safe
                return

            # 2. Remove the items from their original position
            # Create the list *without* the moved section
            remaining_items = self.pdf_files[:start] + self.pdf_files[end + 1 :]

            # 3. Calculate the correct insertion index in the *remaining_items* list
            # If the items were moved *downwards* (start < target_row), the target index
            # in the original list needs adjustment because items *before* it were removed.
            if start < target_row:
                # Items before the insertion point were removed, so adjust index down
                insert_index = target_row - count
            else:
                # Moved upwards or staying in place relative to others.
                # The target_row is the correct index *after* removal.
                insert_index = target_row

            # Ensure index is within the bounds of the list *after* removal
            insert_index = max(0, min(insert_index, len(remaining_items)))

            # 4. Insert the moved items at the calculated index
            self.pdf_files = (
                remaining_items[:insert_index]
                + moved_items
                + remaining_items[insert_index:]
            )

            # 5. *** CRITICAL ***: Refresh the table view entirely.
            print("--- Calling update_table after successful row move ---")
            self.update_table()  # Call the version with debug prints

            # Optional: Re-select the moved rows visually for better user feedback
            selection_model = self.pdf_table.selectionModel()
            selection_model.clearSelection()
            new_start_index = insert_index
            new_end_index = insert_index + count - 1

            # Select rows in the new positions using QItemSelection
            item_selection = QItemSelection()
            for r in range(new_start_index, new_end_index + 1):
                # Check row validity before creating index
                if 0 <= r < self.pdf_table.rowCount():
                    top_left_index = self.pdf_table.model().index(r, 0)
                    bottom_right_index = self.pdf_table.model().index(
                        r, self.pdf_table.columnCount() - 1
                    )
                    if top_left_index.isValid() and bottom_right_index.isValid():
                        item_selection.select(top_left_index, bottom_right_index)
                else:
                    print(f"Warning: Attempted to select invalid row {r} after move.")

            if not item_selection.isEmpty():
                selection_model.select(
                    item_selection, selection_model.Select | selection_model.Rows
                )  # Select full rows

        except IndexError as idx_err:
            print(f"Error during list manipulation in on_rows_moved: {idx_err}")
            print(
                f"State: start={start}, end={end}, row={row}, target_row={target_row}, len={effective_row_count}"
            )
            # As a recovery, force a table refresh from whatever the current self.pdf_files is
            self.update_table()
        except Exception as e:
            print(f"Unexpected error in on_rows_moved: {e}")
            import traceback  # Import here for error case

            traceback.print_exc()
            self.update_table()  # Try to recover view state

    def sort_table(self, column):
        """Sort self.pdf_files based on the clicked column and refresh the table."""
        current_order = self.pdf_table.horizontalHeader().sortIndicatorOrder()
        # Toggle order: if current is Ascending or None, sort Descending next. Else sort Ascending.
        reverse_sort = current_order == Qt.SortOrder.AscendingOrder

        # Determine sort key
        if column == 0:  # Name
            sort_key = lambda x: x[1].lower()
        elif column == 1:  # Size
            sort_key = lambda x: x[2]
        elif column == 2:  # Modified Date
            sort_key = lambda x: x[3]
        elif column == 3:  # Pages
            sort_key = lambda x: x[4]
        else:
            return  # Should not happen

        # Sort the data
        try:
            self.pdf_files.sort(key=sort_key, reverse=reverse_sort)
        except Exception as e:
            print(f"Error during sorting: {e}")
            self.statusBar().showMessage(f"Sorting error: {e}", 5000)
            return  # Don't update table if sort failed

        # Update the table display using the debugging version
        print("--- Calling update_table after sorting ---")
        self.update_table()

        # Update the sort indicator on the header
        new_order = (
            Qt.SortOrder.DescendingOrder
            if reverse_sort
            else Qt.SortOrder.AscendingOrder
        )
        self.pdf_table.horizontalHeader().setSortIndicator(column, new_order)

    def set_output_directory(self):
        """Set the output directory for the merged PDF."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_dir
        )
        if directory:
            self.output_dir = directory
            self.statusBar().showMessage(
                f"Output directory set to: {self.output_dir}", 3000
            )

    def merge_pdfs(self):
        """Merge PDFs in the order currently listed in self.pdf_files."""
        if not self.pdf_files:
            self.statusBar().showMessage("No PDFs loaded to merge.", 3000)
            return

        output_filename = self.output_name.text().strip()
        if not output_filename:
            # Provide a default if empty, or prompt user
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"merged_output_{timestamp}.pdf"
            self.output_name.setText(output_filename)  # Update the line edit
            # Alternatively show an error:
            # self.statusBar().showMessage("Please enter an output file name.", 3000)
            # return

        if not output_filename.lower().endswith(".pdf"):
            output_filename += ".pdf"

        output_path = os.path.join(self.output_dir, output_filename)

        # Optional: Check for overwrite
        if os.path.exists(output_path):
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                f"The file '{output_filename}' already exists in the selected directory.\nDo you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self.statusBar().showMessage("Merge cancelled.", 3000)
                return

        merger = PdfMerger()
        self.statusBar().showMessage("Merging started...", 0)  # Persistent message
        QApplication.processEvents()  # Allow UI update

        success_count = 0
        error_files = []

        try:
            # Directly use the ordered self.pdf_files list
            for pdf_path, name, _, _, _ in self.pdf_files:
                try:
                    # Consider using strict=False for robustness with slightly malformed PDFs
                    reader = PdfReader(pdf_path, strict=False)
                    if not reader.pages:  # Skip if PDF has no pages or couldn't be read
                        print(
                            f"Skipping '{name}' as it has no pages or could not be read properly."
                        )
                        error_files.append(name)
                        continue

                    bookmark_title = os.path.splitext(name)[0]
                    start_page_index = len(
                        merger.pages
                    )  # Page index before adding current PDF
                    merger.append(pdf_path)
                    # Add bookmark pointing to the first page of the just appended document
                    merger.add_outline_item(bookmark_title, start_page_index)
                    success_count += 1

                except Exception as append_error:
                    # Log specific file error but continue merging others
                    print(f"Error reading/appending file '{name}': {append_error}")
                    error_files.append(name)
                    # Update status bar immediately about skipping
                    self.statusBar().showMessage(
                        f"Skipping problematic file: {name}...", 0
                    )
                    QApplication.processEvents()  # Allow UI update

            if success_count > 0:
                with open(output_path, "wb") as output_file:
                    merger.write(output_file)
                final_msg = (
                    f"Merged {success_count} PDF(s) successfully to {output_path}"
                )
                if error_files:
                    final_msg += f" ({len(error_files)} file(s) skipped due to errors)."
                self.statusBar().showMessage(final_msg, 7000)
            elif error_files:
                self.statusBar().showMessage(
                    "Merge failed. All selected files encountered errors.", 5000
                )
            else:
                # This case should ideally not be reached if the list wasn't empty initially
                self.statusBar().showMessage(
                    "No valid PDFs were available to merge.", 5000
                )

        except Exception as merge_error:
            # Error during the final write operation
            self.statusBar().showMessage(
                f"Error during final merge write: {merge_error}", 5000
            )
            import traceback  # Import here for error case

            traceback.print_exc()
        finally:
            try:
                merger.close()  # Ensure resources are released
            except Exception as close_error:
                print(
                    f"Error closing PdfMerger: {close_error}"
                )  # Log potential close errors


if __name__ == "__main__":
    # It's good practice to wrap the app execution in a try/except
    # to catch potential initialization errors.
    try:
        app = QApplication(sys.argv)
        window = PDFMergerApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"FATAL ERROR during application startup: {e}")
        import traceback

        traceback.print_exc()
        # Optionally show a simple message box if GUI is partially up
        # msg_box = QMessageBox()
        # msg_box.setIcon(QMessageBox.Icon.Critical)
        # msg_box.setText("A critical error occurred on startup.")
        # msg_box.setInformativeText(str(e))
        # msg_box.setWindowTitle("Application Error")
        # msg_box.exec()
        sys.exit(1)  # Exit with an error code
