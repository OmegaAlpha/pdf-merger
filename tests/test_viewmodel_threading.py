import os
import fitz
import pytest
import time
from PySide6.QtCore import Qt, QTimer
from viewmodel import MainViewModel, PDFDocument
from datetime import datetime

@pytest.fixture
def dummy_pdf(tmp_path):
    path = tmp_path / "threading_test.pdf"
    doc = fitz.open()
    for i in range(10):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {i+1}")
    doc.save(str(path))
    doc.close()
    return str(path)

def test_rapid_thumbnail_requests(qtbot, dummy_pdf):
    """Verify that rapid requests for thumbnails do not cause a crash."""
    vm = MainViewModel()
    
    # Setup model
    vm.pdf_list_model.pdfs = [
        PDFDocument(dummy_pdf, "test.pdf", 10.0, datetime.now(), 10)
    ]
    
    # Rapidly call request_thumbnails
    for _ in range(50):
        vm.request_thumbnails(dummy_pdf)
        # No wait here, just spamming the requests
    
    # Give some time for threads to finish or crash
    qtbot.wait(2000)
    
    # Verify that we have some workers in the abandoned list
    # (depending on timing, some might have already finished)
    print(f"Active/abandoned workers: {len(vm._active_workers)}")
    
    # Final wait to ensure cleanup
    qtbot.waitUntil(lambda: len(vm._active_workers) == 0 and vm.thumbnail_worker is None, timeout=10000)
    
    assert len(vm._active_workers) == 0
    assert vm.thumbnail_worker is None
    # If we reached here without a crash/segfault, the test passed.

def test_rapid_add_pdfs(qtbot, dummy_pdf):
    """Verify that rapid add_pdf calls do not cause a crash."""
    vm = MainViewModel()
    
    for _ in range(10):
        vm.add_pdfs([dummy_pdf])
        
    # Wait for completion
    qtbot.waitUntil(lambda: len(vm.pdf_list_model.pdfs) > 0, timeout=5000)
    qtbot.waitUntil(lambda: len(vm._active_workers) == 0 and vm.add_worker is None, timeout=5000)
    
    assert len(vm._active_workers) == 0
    assert vm.add_worker is None
