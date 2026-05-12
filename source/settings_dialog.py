from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import QSettings, QEvent

class SettingsDialog(QDialog):
    def __init__(self, theme_manager, language_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.language_manager = language_manager
        
        self.setFixedSize(400, 200)
        
        self.layout = QVBoxLayout(self)
        
        # Theme Setting
        theme_layout = QHBoxLayout()
        self.theme_label = QLabel()
        self.theme_combo = QComboBox()
        # We store the internal key to avoid issues with translations changing the text
        self.theme_combo.addItem("System Default", "System Default")
        self.theme_combo.addItem("Light", "Light")
        self.theme_combo.addItem("Dark", "Dark")
        
        # Load current theme
        current_pref = self.theme_manager.get_current_preference()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_pref:
                self.theme_combo.setCurrentIndex(i)
                break
            
        theme_layout.addWidget(self.theme_label)
        theme_layout.addWidget(self.theme_combo)
        self.layout.addLayout(theme_layout)

        # Language Setting
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        
        for code, name in self.language_manager.supported_languages.items():
            self.lang_combo.addItem(name, code)
            
        # Load current language
        current_lang = self.language_manager.current_lang
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current_lang:
                self.lang_combo.setCurrentIndex(i)
                break
                
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo)
        self.layout.addLayout(lang_layout)
        
        self.layout.addStretch()
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.layout.addWidget(self.button_box)
        
        self.retranslateUi()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.setWindowTitle(self.tr("Settings"))
        self.theme_label.setText(self.tr("Appearance Theme:"))
        self.lang_label.setText(self.tr("Language:"))
        
        # Translate theme combo items
        theme_translations = {
            "System Default": self.tr("System Default"),
            "Light": self.tr("Light"),
            "Dark": self.tr("Dark")
        }
        for i in range(self.theme_combo.count()):
            key = self.theme_combo.itemData(i)
            self.theme_combo.setItemText(i, theme_translations.get(key, key))

    def accept(self):
        settings = QSettings("PDFMerger", "PDFMergerApp")
        
        # Save theme
        theme_pref = self.theme_combo.itemData(self.theme_combo.currentIndex())
        settings.setValue("theme_preference", theme_pref)
        self.theme_manager.apply_theme()
        
        # Save and apply language
        lang_code = self.lang_combo.itemData(self.lang_combo.currentIndex())
        self.language_manager.apply_language(lang_code)
        
        super().accept()
