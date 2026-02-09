"""
Base classes for engineering discipline calculators.

All discipline modules should implement DisciplineCalculator.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    REVIEW = "REVIEW"


@dataclass
class CalculationResult:
    calculation_type: str = ""
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ValidationResult:
    item_type: str
    item_tag: str
    sheet_id: Optional[int]
    drawing_number: Optional[str]
    extracted_value: str
    calculated_value: str
    tolerance_pct: float
    deviation_pct: float
    status: ValidationStatus
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d["status"] = self.status.value
        return d


class DisciplineCalculator(ABC):
    """Abstract base class for discipline calculators."""

    @property
    @abstractmethod
    def discipline_name(self) -> str:
        pass

    @abstractmethod
    def available_calculations(self) -> List[str]:
        pass

    @abstractmethod
    def run_calculation(self, calculation_type: str, params: Dict[str, Any]) -> CalculationResult:
        pass
