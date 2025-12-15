from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Receipt:
    id: Optional[int]
    date: datetime
    total_amount: float
    merchant_name: str
    items: str  # JSON string or simple text description for now
    raw_text: str # The full text extracted by OCR
    image_path: str
