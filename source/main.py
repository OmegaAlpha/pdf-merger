import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
import fitz # Used to preload shared libraries early if needed

from viewmodel import MainViewModel
from view import MainWindow
from theme_manager import ThemeManager

def main():
    try:
        if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(sys.argv)
        
        tm = ThemeManager(app)
        tm.apply_theme()
        
        # Initialize ViewModel
        vm = MainViewModel()
        
        # Initialize View
        window = MainWindow(vm, tm)
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("A critical error occurred.")
            msg_box.setInformativeText(f"Details:\n{e}\n\nSee console for full traceback.")
            msg_box.setWindowTitle("Application Error")
            msg_box.exec()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
