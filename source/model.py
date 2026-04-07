from dataclasses import dataclass
from datetime import datetime

@dataclass
class PDFDocument:
    file_path: str
    name: str
    size_kb: float
    modified_dt: datetime
    pages: int
