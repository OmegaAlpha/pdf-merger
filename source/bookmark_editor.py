import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QMessageBox,
    QLabel
)
from PySide6.QtCore import Qt, QEvent

class BookmarkEditorDialog(QDialog):
    def __init__(self, toc: list, max_pages: int, pdf_name: str, parent=None):
        super().__init__(parent)
        self.toc = toc
        self.max_pages = max_pages
        self.pdf_name = pdf_name
        
        self.resize(600, 400)
        
        self.layout = QVBoxLayout(self)
        
        self.info_label = QLabel("")
        self.layout.addWidget(self.info_label)
        
        self.tree = QTreeWidget()
        self.tree.setColumnWidth(0, 400)
        
        # Enable Drag and Drop for reordering and reparenting
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.layout.addWidget(self.tree)
        
        # Populate Tree
        self._populate_tree()
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("")
        self.add_child_btn = QPushButton("")
        self.remove_btn = QPushButton("")
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.add_child_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("")
        self.cancel_btn = QPushButton("")
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        self.layout.addLayout(btn_layout)
        
        # Connect Signals
        self.add_btn.clicked.connect(self.on_add)
        self.add_child_btn.clicked.connect(self.on_add_child)
        self.remove_btn.clicked.connect(self.on_remove)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.retranslateUi()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Edit Bookmarks - {0}").format(self.pdf_name))
        self.info_label.setText(self.tr("Editing bookmarks for {0} ({1} pages). Double-click a cell to edit.\nDrag and drop items to reorder them.").format(self.pdf_name, self.max_pages))
        self.tree.setHeaderLabels([self.tr("Title"), self.tr("Page")])
        
        self.add_btn.setText(self.tr("Add"))
        self.add_child_btn.setText(self.tr("Add Child"))
        self.remove_btn.setText(self.tr("Remove"))
        self.save_btn.setText(self.tr("Save"))
        self.cancel_btn.setText(self.tr("Cancel"))
        
    def _populate_tree(self):
        self.tree.clear()
        if not self.toc:
            return
            
        last_item_at_level = {}
        for item_data in self.toc:
            if not item_data or len(item_data) < 3:
                continue
                
            level = item_data[0]
            title = str(item_data[1])
            page = str(item_data[2])
            
            item = QTreeWidgetItem([title, page])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            if level == 1:
                self.tree.addTopLevelItem(item)
            else:
                parent = last_item_at_level.get(level - 1)
                if parent:
                    parent.addChild(item)
                else:
                    # Fallback if structure is malformed
                    self.tree.addTopLevelItem(item)
                    
            last_item_at_level[level] = item
            item.setExpanded(True)
            
    def _create_new_item(self, title=None, page="1"):
        if title is None:
            title = self.tr("New Bookmark")
        item = QTreeWidgetItem([title, page])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        return item
        
    def on_add(self):
        selected = self.tree.selectedItems()
        new_item = self._create_new_item()
        
        if selected:
            # Add as sibling
            parent = selected[0].parent()
            if parent:
                parent.addChild(new_item)
            else:
                index = self.tree.indexOfTopLevelItem(selected[0])
                self.tree.insertTopLevelItem(index + 1, new_item)
        else:
            self.tree.addTopLevelItem(new_item)
            
        self.tree.setCurrentItem(new_item)
        self.tree.editItem(new_item, 0)
        
    def on_add_child(self):
        selected = self.tree.selectedItems()
        new_item = self._create_new_item()
        
        if selected:
            parent = selected[0]
            parent.addChild(new_item)
            parent.setExpanded(True)
        else:
            self.tree.addTopLevelItem(new_item)
            
        self.tree.setCurrentItem(new_item)
        self.tree.editItem(new_item, 0)
        
    def on_remove(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
            
        item = selected[0]
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(index)
            
    def get_updated_toc(self):
        toc = []
        
        def traverse(item, level):
            title = item.text(0).strip()
            if not title:
                title = self.tr("Untitled")
                
            try:
                page = int(item.text(1))
                if page < 1: page = 1
                if page > self.max_pages: page = self.max_pages
            except ValueError:
                page = 1
                
            toc.append([level, title, page])
            for i in range(item.childCount()):
                traverse(item.child(i), level + 1)
                
        for i in range(self.tree.topLevelItemCount()):
            traverse(self.tree.topLevelItem(i), 1)
            
        return toc
