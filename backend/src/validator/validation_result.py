from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    valid: bool
    stage: str
    message: str
    error_type: Optional[str] = None
    details: Optional[dict] = None