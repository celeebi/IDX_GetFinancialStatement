"""
Universal Financial Modeling Chart of Accounts Schemas.
Standardized dataclasses for Income Statement, Balance Sheet, Cash Flow, and Operational Drivers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class NormalizedIS:
    """Standardized Income Statement (in Millions IDR)."""
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    sgna_opex: float = 0.0
    ebitda: float = 0.0
    depreciation_amortization: float = 0.0
    operating_income_ebit: float = 0.0
    finance_income: float = 0.0
    finance_costs: float = 0.0
    net_finance_costs: float = 0.0
    other_non_operating: float = 0.0
    ebt: float = 0.0
    tax_expense: float = 0.0
    net_income: float = 0.0
    net_income_parent: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "Gross Revenue": self.revenue,
            "Cost of Goods Sold (COGS)": self.cogs,
            "Gross Profit": self.gross_profit,
            "SG&A / Operating Expenses": self.sgna_opex,
            "EBITDA": self.ebitda,
            "Depreciation & Amortization": self.depreciation_amortization,
            "Operating Income (EBIT)": self.operating_income_ebit,
            "Finance Income": self.finance_income,
            "Finance Costs": self.finance_costs,
            "Net Finance Costs": self.net_finance_costs,
            "Other Non-Operating Items": self.other_non_operating,
            "Earnings Before Tax (EBT)": self.ebt,
            "Income Tax Expense": self.tax_expense,
            "Net Income": self.net_income,
            "Net Income (Parent Entity)": self.net_income_parent,
        }


@dataclass
class NormalizedBS:
    """Standardized Balance Sheet (in Millions IDR)."""
    # Current Assets
    cash_and_equivalents: float = 0.0
    accounts_receivable: float = 0.0
    inventories: float = 0.0
    other_current_assets: float = 0.0
    total_current_assets: float = 0.0

    # Non-Current Assets
    net_ppe: float = 0.0
    other_non_current_assets: float = 0.0
    total_non_current_assets: float = 0.0
    total_assets: float = 0.0

    # Current Liabilities
    accounts_payable: float = 0.0
    short_term_debt: float = 0.0
    other_current_liabilities: float = 0.0
    total_current_liabilities: float = 0.0

    # Non-Current Liabilities
    long_term_debt: float = 0.0
    other_non_current_liabilities: float = 0.0
    total_non_current_liabilities: float = 0.0
    total_liabilities: float = 0.0

    # Equity
    share_capital: float = 0.0
    retained_earnings: float = 0.0
    other_equity: float = 0.0
    total_equity: float = 0.0
    total_liabilities_and_equity: float = 0.0
    balance_check: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "Cash & Cash Equivalents": self.cash_and_equivalents,
            "Accounts Receivable": self.accounts_receivable,
            "Inventories": self.inventories,
            "Other Current Assets": self.other_current_assets,
            "Total Current Assets": self.total_current_assets,
            "Net PP&E": self.net_ppe,
            "Other Non-Current Assets": self.other_non_current_assets,
            "Total Non-Current Assets": self.total_non_current_assets,
            "TOTAL ASSETS": self.total_assets,
            "Accounts Payable": self.accounts_payable,
            "Short-Term Debt": self.short_term_debt,
            "Other Current Liabilities": self.other_current_liabilities,
            "Total Current Liabilities": self.total_current_liabilities,
            "Long-Term Debt": self.long_term_debt,
            "Other Non-Current Liabilities": self.other_non_current_liabilities,
            "Total Non-Current Liabilities": self.total_non_current_liabilities,
            "TOTAL LIABILITIES": self.total_liabilities,
            "Share Capital & Additional Capital": self.share_capital,
            "Retained Earnings": self.retained_earnings,
            "Other Equity & Reserves": self.other_equity,
            "TOTAL EQUITY": self.total_equity,
            "TOTAL LIABILITIES & EQUITY": self.total_liabilities_and_equity,
            "BALANCE CHECK (Assets - Liab&Eq)": self.balance_check,
        }


@dataclass
class NormalizedCF:
    """Standardized Cash Flow Statement (in Millions IDR)."""
    operating_cash_flow: float = 0.0
    capex: float = 0.0
    investing_cash_flow: float = 0.0
    dividends_paid: float = 0.0
    net_debt_change: float = 0.0
    financing_cash_flow: float = 0.0
    net_change_in_cash: float = 0.0
    beginning_cash: float = 0.0
    ending_cash: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "Operating Cash Flow (CFO)": self.operating_cash_flow,
            "Capital Expenditures (Capex)": self.capex,
            "Investing Cash Flow (CFI)": self.investing_cash_flow,
            "Dividends Paid": self.dividends_paid,
            "Net Debt Issued / (Repaid)": self.net_debt_change,
            "Financing Cash Flow (CFF)": self.financing_cash_flow,
            "Net Change in Cash": self.net_change_in_cash,
            "Beginning Cash": self.beginning_cash,
            "Ending Cash": self.ending_cash,
        }


@dataclass
class OperationalDrivers:
    """Historical modeling ratios and forecasting drivers."""
    revenue_growth_yoy: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    sgna_pct_revenue: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    effective_tax_rate_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None
    dso_days: Optional[float] = None
    dio_days: Optional[float] = None
    dpo_days: Optional[float] = None
    other_ca_pct_rev: Optional[float] = None
    other_cl_pct_rev: Optional[float] = None
    capex_pct_rev: Optional[float] = None
    dna_pct_ppe: Optional[float] = None
    dividend_payout_pct: Optional[float] = None
    effective_borrowing_rate_pct: Optional[float] = None
    effective_interest_income_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Revenue Growth (YoY)": self.revenue_growth_yoy,
            "Gross Margin (%)": self.gross_margin_pct,
            "SG&A / Opex (% Rev)": self.sgna_pct_revenue,
            "EBITDA Margin (%)": self.ebitda_margin_pct,
            "Operating Margin (EBIT %)": self.operating_margin_pct,
            "Effective Tax Rate (%)": self.effective_tax_rate_pct,
            "Net Profit Margin (%)": self.net_margin_pct,
            "DSO - Days Sales Outstanding (Days)": self.dso_days,
            "DIO - Days Inventory Outstanding (Days)": self.dio_days,
            "DPO - Days Payable Outstanding (Days)": self.dpo_days,
            "Other Current Assets (% Rev)": self.other_ca_pct_rev,
            "Other Current Liabilities (% Rev)": self.other_cl_pct_rev,
            "Capex (% of Revenue)": self.capex_pct_rev,
            "D&A (% of Net PP&E)": self.dna_pct_ppe,
            "Dividend Payout Ratio (%)": self.dividend_payout_pct,
            "Effective Borrowing Rate (% Debt)": self.effective_borrowing_rate_pct,
            "Effective Interest Yield (% Cash)": self.effective_interest_income_pct,
        }
