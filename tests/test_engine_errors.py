import pytest
from datetime import datetime
from unittest.mock import MagicMock
from model import PDFDocument
from engine import merge_pdfs_engine

def test_engine_zero_pages(mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 0)]
    mock_merged = MagicMock()
    mock_source = MagicMock()
    mock_source.page_count = 0
    mocker.patch("engine.fitz.open", side_effect=[mock_merged, mock_source])
    
    success, msg = merge_pdfs_engine(docs, "output.pdf")
    assert success is False
    assert "Merge failed. 1 file(s) had errors." in msg

def test_engine_file_open_exception(mocker):
    docs = [PDFDocument("missing.pdf", "missing.pdf", 1.0, datetime.now(), 1)]
    # fitz.open first returns merged doc, then raises error on source
    mock_merged = MagicMock()
    mocker.patch("engine.fitz.open", side_effect=[mock_merged, Exception("Simulated read error")])
    
    success, msg = merge_pdfs_engine(docs, "output.pdf")
    assert success is False
    assert "Merge failed. 1 file(s) had errors." in msg

def test_engine_toc_extraction_exception(mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    
    mock_merged = MagicMock()
    mock_source = MagicMock()
    mock_source.page_count = 5
    mock_source.get_toc.side_effect = Exception("Simulated TOC error")
    
    mocker.patch("engine.fitz.open", side_effect=[mock_merged, mock_source])
    
    success, msg = merge_pdfs_engine(docs, "output.pdf")
    assert success is True
    assert "Merged 1 PDF(s)" in msg

def test_engine_save_exception(mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    
    mock_merged = MagicMock()
    mock_merged.save.side_effect = PermissionError("Simulated save permission error")
    mock_source = MagicMock()
    mock_source.page_count = 5
    mock_source.get_toc.return_value = []
    
    mocker.patch("engine.fitz.open", side_effect=[mock_merged, mock_source])
    
    success, msg = merge_pdfs_engine(docs, "output.pdf")
    assert success is False
    assert "ERROR saving merged file" in msg
    assert "Simulated save permission error" in msg

def test_engine_fatal_merge_error(mocker):
    docs = [PDFDocument("dummy.pdf", "dummy.pdf", 1.0, datetime.now(), 1)]
    
    mock_merged = MagicMock()
    mock_merged.insert_pdf.side_effect = Exception("Simulated fatal insert error")
    mock_source = MagicMock()
    mock_source.page_count = 5
    
    mocker.patch("engine.fitz.open", side_effect=[mock_merged, mock_source])
    
    success, msg = merge_pdfs_engine(docs, "output.pdf")
    assert success is False
    assert "Merge failed. 1 file(s) had errors." in msg
