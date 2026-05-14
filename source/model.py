from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class PDFDocument:
    file_path: str
    name: str
    size_kb: float
    modified_dt: datetime
    pages: int
    custom_toc: Optional[List] = field(default=None) # Kept for legacy project loading
    missing: bool = field(default=False)

@dataclass
class BookmarkItem:
    title: str
    page: int
    level: int
    source_pdf: PDFDocument
