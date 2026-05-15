
import sys
import os
from PySide6.QtWidgets import QApplication, QTreeWidgetItem
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QDragMoveEvent, QDropEvent

# Add source to path
sys.path.append(os.path.join(os.getcwd(), 'source'))

from bookmarks_pane import BookmarksPane, BookmarksTreeWidget
from viewmodel import MainViewModel
from model import PDFDocument, BookmarkItem
from datetime import datetime

def test_snap_to_pdf():
    app = QApplication.instance() or QApplication(sys.argv)
    vm = MainViewModel()
    
    # Add dummy PDFs
    pdf1 = PDFDocument("file1.pdf", "file1.pdf", 100, datetime.now(), 10)
    pdf2 = PDFDocument("file2.pdf", "file2.pdf", 200, datetime.now(), 20)
    vm.pdf_list_model.pdfs = [pdf1, pdf2]
    
    pane = BookmarksPane(vm)
    tree = pane.tree
    
    print(f"Initial top level: {tree.topLevelItemCount()}")
    
    # Manually add a bookmark at top level (escaping the PDF containers)
    # Between PDF1 and PDF2
    escaped_bm = BookmarkItem("Escaped", 1, 1, pdf1)
    escaped_item = QTreeWidgetItem(["Escaped", "1"])
    escaped_item.setData(0, Qt.ItemDataRole.UserRole, escaped_bm)
    tree.insertTopLevelItem(1, escaped_item)
    
    print(f"Top level after escape: {tree.topLevelItemCount()}")
    print(f"Item 1 text: {tree.topLevelItem(1).text(0)}")
    
    # Call sync - this should trigger the snap-to-pdf logic
    pane._sync_to_viewmodel()
    
    print(f"Top level after sync: {tree.topLevelItemCount()}")
    
    # Verify it was moved into PDF1 (which was the PDF above it)
    root1 = tree.topLevelItem(0)
    print(f"PDF1 children count: {root1.childCount()}")
    found = False
    for i in range(root1.childCount()):
        if root1.child(i).text(0) == "Escaped":
            found = True
            break
            
    assert found == True
    print("Snap-to-PDF verification successful!")

if __name__ == "__main__":
    try:
        test_snap_to_pdf()
    except Exception as e:
        print(f"Error in test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
