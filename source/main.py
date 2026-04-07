import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
import fitz # Used to preload shared libraries early if needed

from viewmodel import MainViewModel
from view import MainWindow

def main():
    try:
        app = QApplication(sys.argv)
        
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
