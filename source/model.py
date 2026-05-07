from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class PDFDocument:
    file_path: str
    name: str
    size_kb: float
    modified_dt: datetime
    pages: int
    custom_toc: List = field(default=None)
