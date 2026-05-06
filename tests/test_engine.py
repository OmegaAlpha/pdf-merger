import os
import fitz
import pytest
from datetime import datetime
from model import PDFDocument
from engine import merge_pdfs_engine

@pytest.fixture
def dummy_pdfs(tmp_path):
    pdf_paths = []
    
    # Create two dummy PDFs
    for i in range(2):
        doc = fitz.open()
        
        # Add 2 pages each
        page1 = doc.new_page()
        page1.insert_text(fitz.Point(50, 50), f"PDF {i+1} Page 1")
        page2 = doc.new_page()
        page2.insert_text(fitz.Point(50, 50), f"PDF {i+1} Page 2")
        
        # Add a basic ToC (1-based level, title, 1-based page)
        toc = [
            [1, f"Document {i+1}", 1],
            [2, f"Doc {i+1} - P2", 2]
        ]
        doc.set_toc(toc)
        
        file_path = tmp_path / f"test_{i+1}.pdf"
        doc.save(file_path)
        doc.close()
        
        pdf_paths.append(str(file_path))
        
    return pdf_paths

def test_merge_pdfs_engine_success(tmp_path, dummy_pdfs):
    output_path = str(tmp_path / "merged.pdf")
    
    pdf_docs = []
    for path in dummy_pdfs:
        pdf_docs.append(PDFDocument(
            file_path=path,
            name=os.path.basename(path),
            size_kb=10.0,
            modified_dt=datetime.now(),
            pages=2
        ))
        
    success, msg = merge_pdfs_engine(pdf_docs, output_path)
    
    assert success is True
    assert "Merged 2 PDF(s)" in msg
    assert os.path.exists(output_path)
    
    # Verify merged document
    result_doc = fitz.open(output_path)
    assert result_doc.page_count == 4
    
    # Verify ToC points to right pages
    result_toc = result_doc.get_toc()
    assert len(result_toc) == 4 # 2 from doc1 + 2 from doc2 (generated bookmarks omitted due to existing page 1 bookmarks)
    
    # Close the doc to prevent file locks in windows
    result_doc.close()

def test_merge_pdfs_engine_empty_list(tmp_path):
    output_path = str(tmp_path / "never_created.pdf")
    success, msg = merge_pdfs_engine([], output_path)
    
    assert success is False
    assert "No PDFs to merge" in msg
    assert not os.path.exists(output_path)
