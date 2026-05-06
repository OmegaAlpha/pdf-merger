from datetime import datetime
from model import PDFDocument

def test_pdf_document_creation():
    dt = datetime(2026, 4, 22, 12, 0, 0)
    pdf = PDFDocument(
        file_path="C:/dummy/test.pdf",
        name="test.pdf",
        size_kb=150.5,
        modified_dt=dt,
        pages=5
    )

    assert pdf.file_path == "C:/dummy/test.pdf"
    assert pdf.name == "test.pdf"
    assert pdf.size_kb == 150.5
    assert pdf.modified_dt == dt
    assert pdf.pages == 5
