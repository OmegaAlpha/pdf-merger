import os
import fitz
import pytest
from PyQt6.QtCore import Qt, QModelIndex
from viewmodel import PDFListViewModel, MainViewModel

@pytest.fixture
def real_pdf(tmp_path):
    # MainViewModel reads real files with fitz.open, so we need a minimal real file
    file_path = tmp_path / "dummy_for_vm.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(file_path))
    doc.close()
    return str(file_path)

def test_pdf_list_model_sort():
    model = PDFListViewModel()
    from model import PDFDocument
    from datetime import datetime
    
    model.pdfs = [
        PDFDocument("a", "B_file.pdf", 100.0, datetime(2026, 1, 1), 2),
        PDFDocument("b", "A_file.pdf", 50.0, datetime(2026, 2, 1), 5),
    ]
    
    # Sort by Name (Col 0) Ascending
    model.sort(0, Qt.SortOrder.AscendingOrder)
    assert model.pdfs[0].name == "A_file.pdf"
    assert model.pdfs[1].name == "B_file.pdf"
    
    # Sort by Size (Col 1) Descending
    model.sort(1, Qt.SortOrder.DescendingOrder)
    assert model.pdfs[0].name == "B_file.pdf" # 100 > 50
    assert model.pdfs[1].name == "A_file.pdf"
    
    # Sort by Pages (Col 3) Ascending
    model.sort(3, Qt.SortOrder.AscendingOrder)
    assert model.pdfs[0].name == "B_file.pdf" # 2 < 5
    assert model.pdfs[1].name == "A_file.pdf"

def test_main_view_model_add_remove(qtbot, real_pdf):
    vm = MainViewModel()
    
    signals = []
    vm.status_message.connect(lambda msg, timeout: signals.append(msg))
    
    vm.add_pdfs([real_pdf])
        
    assert len(vm.pdf_list_model.pdfs) == 1
    assert vm.pdf_list_model.pdfs[0].name == "dummy_for_vm.pdf"
    assert any("Added 1 PDF(s)" in s for s in signals)
    
    # Test remove
    signals.clear()
    vm.remove_pdfs_by_indices([0])
        
    assert len(vm.pdf_list_model.pdfs) == 0
    assert any("Removed 1 PDF(s)" in s for s in signals)

def test_main_view_model_move_rows(qtbot):
    vm = MainViewModel()
    from model import PDFDocument
    from datetime import datetime
    
    # Add dummy manually
    docs = [
        PDFDocument(f"p{i}", f"F{i}.pdf", 1.0, datetime.now(), 1)
        for i in range(4) # F0, F1, F2, F3
    ]
    vm.pdf_list_model.pdfs = docs
    
    # Move F1 (index 1) to end (index 4)
    # The actual source row is 1, count is 1, destination_child_row is 4
    vm.move_rows(1, 1, 4)
    
    # Order should be F0, F2, F3, F1
    assert vm.pdf_list_model.pdfs[0].name == "F0.pdf"
    assert vm.pdf_list_model.pdfs[1].name == "F2.pdf"
    assert vm.pdf_list_model.pdfs[2].name == "F3.pdf"
    assert vm.pdf_list_model.pdfs[3].name == "F1.pdf"
