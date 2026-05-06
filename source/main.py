import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
import fitz # Used to preload shared libraries early if needed

from viewmodel import MainViewModel
from view import MainWindow

def main():
    try:
        if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(sys.argv)
        
        import os
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(__file__)
        qss_path = os.path.join(base_dir, "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        
        # Initialize ViewModel
        vm = MainViewModel()
        
        # Initialize View
        window = MainWindow(vm)
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
