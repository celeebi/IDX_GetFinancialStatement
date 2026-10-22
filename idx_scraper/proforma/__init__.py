"""
Universal Pro Forma Normalization & Ready-to-Forecast Modeling Module.
Standardizes disparate IDX financial statement filings into clean 3-statement modeling accounts.
"""

from .schema import (
    NormalizedIS, NormalizedBS, NormalizedCF, OperationalDrivers,
    CorporateIS, CorporateBS, CorporateCF, CorporateDrivers,
    BankingIS, BankingBS, BankingCF, BankingDrivers
)
from .normalizer import FinancialNormalizer
from .drivers import DriverCalculator, BankingDriverCalculator
from .export_ready import ReadyToForecastExporter
from .dispatcher import detect_archetype

__all__ = [
    "NormalizedIS",
    "NormalizedBS",
    "NormalizedCF",
    "OperationalDrivers",
    "CorporateIS",
    "CorporateBS",
    "CorporateCF",
    "CorporateDrivers",
    "BankingIS",
    "BankingBS",
    "BankingCF",
    "BankingDrivers",
    "FinancialNormalizer",
    "DriverCalculator",
    "BankingDriverCalculator",
    "ReadyToForecastExporter",
    "detect_archetype",
]
