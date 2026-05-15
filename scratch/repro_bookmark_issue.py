
import sys
import os
from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt

# Mocking the BookmarkItem and PDFDocument
class PDFDocument:
    def __init__(self, name):
        self.name = name

class BookmarkItem:
    def __init__(self, title, source_pdf):
        self.title = title
        self.source_pdf = source_pdf

def test_repro():
    app = QApplication(sys.argv)
    tree = QTreeWidget()
    tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
    
    pdf1 = PDFDocument("PDF 1")
    root1 = QTreeWidgetItem([pdf1.name])
    root1.setData(0, Qt.ItemDataRole.UserRole, pdf1)
    tree.addTopLevelItem(root1)
    
    bm1 = BookmarkItem("BM 1", pdf1)
    child1 = QTreeWidgetItem([bm1.title])
    child1.setData(0, Qt.ItemDataRole.UserRole, bm1)
    root1.addChild(child1)
    
    pdf2 = PDFDocument("PDF 2")
    root2 = QTreeWidgetItem([pdf2.name])
    root2.setData(0, Qt.ItemDataRole.UserRole, pdf2)
    tree.addTopLevelItem(root2)
    
    print(f"Initial top level items: {tree.topLevelItemCount()}")
    for i in range(tree.topLevelItemCount()):
        print(f"  Item {i}: {tree.topLevelItem(i).text(0)}")
    
    # Simulate a drag and drop that makes child1 a sibling of root1 and root2
    # In a real app, this happens by dropping between them.
    # Programmatically we can just do:
    tree.addTopLevelItem(child1) # This moves it from root1 to top level
    
    print(f"\nAfter move to top level:")
    print(f"Top level items: {tree.topLevelItemCount()}")
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        data = item.data(0, Qt.ItemDataRole.UserRole)
        type_str = "PDF" if isinstance(data, PDFDocument) else "Bookmark"
        print(f"  Item {i}: {item.text(0)} ({type_str})")
        
    # Check if we can drag it again if it was a PDF root (which it is now treated as by some logic)
    # The logic in BookmarksTreeWidget.dropEvent:
    # if dragged_item.parent() is None: event.ignore(); return
    
    parent = child1.parent()
    print(f"\nChild1 parent: {parent}")
    if parent is None:
        print("Child1 is now a top-level item and would be blocked from further dragging by current logic.")

if __name__ == "__main__":
    test_repro()
