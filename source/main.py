import sys
import os
import traceback

# If running as a Nuitka standalone executable, we need to add the executable's 
# directory to sys.path so it can find the uncompiled 'pymupdf' and 'fitz' data directories.
if "__compiled__" in globals():
    sys.path.insert(0, os.path.dirname(sys.executable))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
import fitz # Used to preload shared libraries early if needed

# For Windows, ensure High DPI awareness is set before QApplication is initialized
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # 1 = Process_System_DPI_Aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from viewmodel import MainViewModel
from view import MainWindow
from theme_manager import ThemeManager
from language_manager import LanguageManager

def main():
    try:
        if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(sys.argv)
        
        tm = ThemeManager(app)
        tm.apply_theme()
        
        # Initialize Language
        lm = LanguageManager(app)
        lm.init_language()
        
        # Initialize ViewModel
        vm = MainViewModel()
        
        # Initialize View
        window = MainWindow(vm, tm, lm)
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
