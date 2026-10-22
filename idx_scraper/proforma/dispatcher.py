"""
Archetype Dispatcher and Sector Auto-Detection Engine.
Identifies whether an IDX issuer belongs to the Corporate Archetype
(General Industry, Property, Infrastructure) or Financial Institutions Archetype
(Banks, Sharia Banks, Multifinance, Insurance, Securities).
"""

from typing import Dict, Any, List, Optional


KNOWN_BANKING_TICKERS = {
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BDMN", "BNGA", "BTPS", "BBTN",
    "MEGA", "BJBR", "BJTM", "BFIN", "ADMF", "PNBN", "BCIC", "BNII", "NISP",
    "BTPN", "AGRO", "ARTO", "BABP", "BACA", "BBHI", "BBKP", "BBYB", "BCAP",
    "BDMN", "BEKS", "BGTG", "BINA", "BJBR", "BJTM", "BKSW", "BMAS", "BNBA",
    "BNGA", "BNII", "BNLI", "BSIM", "BSWD", "BTPN", "BTPS", "BVIC", "DNAR",
    "INPC", "MAYA", "MCOR", "MEGA", "NISP", "NOBU", "PNBN", "PNBS", "SDRA"
}

FINANCIAL_KEYWORDS = [
    "bank", "perbankan", "keuangan", "pembiayaan", "financing",
    "financial", "asuransi", "insurance", "sekuritas", "securities",
    "reksadana", "multifinance"
]


def detect_archetype(
    ticker: str,
    general_info: Optional[Dict[str, str]] = None,
    sheet_names: Optional[List[str]] = None,
    facts: Optional[Dict[Any, float]] = None
) -> str:
    """
    Detect whether the ticker should be modeled as 'banking' or 'corporate'.
    
    Returns:
        'banking' or 'corporate'
    """
    clean_ticker = (ticker or "").strip().upper()

    # 1. Ticker registry check
    if clean_ticker in KNOWN_BANKING_TICKERS:
        return "banking"

    # 2. General information metadata check
    if general_info:
        metadata_str = " ".join(str(v).lower() for k, v in general_info.items() if any(
            x in str(k).lower() for x in ["sektor", "industri", "sector", "industry", "kegiatan", "bidang"]
        ))
        if any(kw in metadata_str for kw in FINANCIAL_KEYWORDS):
            return "banking"

    # 3. Excel sheet code prefix check (Entry Point 4/5/6/7: 4220000, 4322000, etc.)
    if sheet_names:
        for name in sheet_names:
            s_clean = name.strip()
            if any(s_clean.startswith(p) for p in ["4220000", "4322000", "4510000", "[42", "[43", "422", "432"]):
                return "banking"

    # 4. XBRL facts presence check
    if facts:
        banking_tags = [
            "TotalInterestAndShariaIncome",
            "TotalLoansGross",
            "AllowanceForImpairmentLossesForLoans",
            "CurrentAccountsWithBankIndonesia",
            "DepositsFromCustomers"
        ]
        fact_tags = {k[0] if isinstance(k, tuple) else str(k) for k in facts.keys()}
        if any(bt in fact_tags for bt in banking_tags):
            return "banking"

    # Default to non-financial Corporate Archetype
    return "corporate"
