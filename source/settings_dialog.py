from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import QSettings

class SettingsDialog(QDialog):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("Settings")
        self.setFixedSize(350, 150)
        
        self.layout = QVBoxLayout(self)
        
        # Theme Setting
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Appearance Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        
        # Load current
        current_pref = self.theme_manager.get_current_preference()
        index = self.theme_combo.findText(current_pref)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
            
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        self.layout.addLayout(theme_layout)
        
        self.layout.addStretch()
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.layout.addWidget(self.button_box)
        
    def accept(self):
        settings = QSettings("PDFMerger", "PDFMergerApp")
        settings.setValue("theme_preference", self.theme_combo.currentText())
        self.theme_manager.apply_theme()
        super().accept()
