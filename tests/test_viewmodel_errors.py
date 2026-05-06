import os
import pytest
from PyQt6.QtCore import Qt, QModelIndex, QUrl, QMimeData
from viewmodel import MainViewModel, PDFListViewModel, MergeWorker
from model import PDFDocument
from datetime import datetime

def test_main_view_model_add_pdfs_invalid(qtbot, tmp_path):
    vm = MainViewModel()
    
    # Create a non-PDF file
    text_file = tmp_path / "test.txt"
    text_file.write_text("hello")
    
    # Create a directory
    some_dir = tmp_path / "somedir"
    some_dir.mkdir()
    
    # Add them
    with qtbot.waitSignal(vm.status_message, timeout=1000) as blocker:
        vm.add_pdfs([str(text_file), str(some_dir)])
        
    assert len(vm.pdf_list_model.pdfs) == 2
    assert "Added 2 PDF(s)" in blocker.args[0]
    assert "error(s)" in blocker.args[0]

def test_main_view_model_remove_out_of_bounds():
    vm = MainViewModel()
    vm.pdf_list_model.pdfs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    
    # Try to remove index 5 which doesn't exist
    vm.remove_pdfs_by_indices([5])
    assert len(vm.pdf_list_model.pdfs) == 1 # Shouldn't crash, shouldn't remove

def test_main_view_model_move_out_of_bounds():
    vm = MainViewModel()
    vm.pdf_list_model.pdfs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    
    # Try to move index 5
    vm.move_rows(5, 1, 0)
    assert len(vm.pdf_list_model.pdfs) == 1

def test_main_view_model_start_merge_empty(qtbot):
    vm = MainViewModel()
    with qtbot.waitSignal(vm.status_message, timeout=1000) as blocker:
        vm.start_merge("output.pdf")
    assert blocker.args[0] == "No PDFs loaded."

def test_merge_worker_signals(qtbot, mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    worker = MergeWorker(docs, "output.pdf")
    
    # Mock engine to simulate success
    mocker.patch("viewmodel.merge_pdfs_engine", return_value=(True, "Success message"))
    
    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args[0] is True
    assert blocker.args[1] == "Success message"

def test_merge_worker_exception(qtbot, mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    worker = MergeWorker(docs, "output.pdf")
    
    # Mock engine to return error
    mocker.patch("viewmodel.merge_pdfs_engine", return_value=(False, "Simulated worker error"))
    
    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.run()
        
    assert blocker.args[0] is False
    assert "Simulated worker error" in blocker.args[1]

def test_pdf_list_model_data_invalid_role():
    model = PDFListViewModel()
    model.pdfs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    index = model.index(0, 0)
    
    # UserRole is not supported by our data()
    assert model.data(index, Qt.ItemDataRole.UserRole) == "dummy.pdf"
    
    # Invalid column
    invalid_index = model.index(0, 5)
    assert model.data(invalid_index, Qt.ItemDataRole.DisplayRole) is None

def test_pdf_list_model_sort_empty():
    model = PDFListViewModel()
    # Shouldn't crash
    model.sort(0, Qt.SortOrder.AscendingOrder)
    assert len(model.pdfs) == 0

def test_main_view_model_slots(qtbot, mocker):
    vm = MainViewModel()
    
    vm.worker = mocker.MagicMock()
    
    with qtbot.waitSignal(vm.status_message, timeout=1000) as blocker:
        vm._on_merge_finished(True, "Done!")
    assert "Done!" in blocker.args[0]
    
    vm.worker = mocker.MagicMock()
    with qtbot.waitSignal(vm.status_message, timeout=1000) as blocker:
        vm._on_merge_finished(False, "Error!")
    assert "Error!" in blocker.args[0]
