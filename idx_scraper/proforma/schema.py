"""
Universal Financial Modeling Chart of Accounts Schemas.
Standardized dataclasses for Income Statement, Balance Sheet, Cash Flow, and Operational Drivers
across both Corporate (General Industry, Property, Infrastructure) and Banking / Financial archetypes.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


# ==============================================================================
# ARCHETYPE A: CORPORATE / OPERATING COMPANIES (General, Property, Infrastructure)
# ==============================================================================

@dataclass
class NormalizedIS:
    """Standardized Income Statement for Corporate Archetype (in Millions IDR)."""
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
    """Standardized Balance Sheet for Corporate Archetype (in Millions IDR)."""
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
    """Historical modeling ratios and forecasting drivers for Corporate Archetype."""
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


# Aliases for explicit corporate taxonomy
CorporateIS = NormalizedIS
CorporateBS = NormalizedBS
CorporateCF = NormalizedCF
CorporateDrivers = OperationalDrivers


# ==============================================================================
# ARCHETYPE B: FINANCIAL INSTITUTIONS & BANKING (Entry Points 4, 5, 6, 7)
# ==============================================================================

@dataclass
class BankingIS:
    """Standardized Income Statement for Banking / Financial Institutions (in Millions IDR)."""
    interest_income: float = 0.0
    interest_expense: float = 0.0
    net_interest_income: float = 0.0
    non_interest_income: float = 0.0
    total_operating_income: float = 0.0
    operating_expenses: float = 0.0
    ppop: float = 0.0  # Pre-Provision Operating Profit
    provision_impairment_losses: float = 0.0  # CKPN
    operating_profit: float = 0.0
    non_operating_items: float = 0.0
    ebt: float = 0.0
    tax_expense: float = 0.0
    net_income: float = 0.0
    net_income_parent: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "Interest & Sharia Income": self.interest_income,
            "Interest & Sharia Expense": self.interest_expense,
            "Net Interest Income (NII)": self.net_interest_income,
            "Non-Interest & Fee Income": self.non_interest_income,
            "Total Operating Income": self.total_operating_income,
            "Operating Expenses (Opex)": self.operating_expenses,
            "Pre-Provision Operating Profit (PPOP)": self.ppop,
            "Provision for Impairment (CKPN)": self.provision_impairment_losses,
            "Operating Profit": self.operating_profit,
            "Non-Operating Items": self.non_operating_items,
            "Earnings Before Tax (EBT)": self.ebt,
            "Income Tax Expense": self.tax_expense,
            "Net Income": self.net_income,
            "Net Income (Parent Entity)": self.net_income_parent,
        }


@dataclass
class BankingBS:
    """Standardized Balance Sheet for Banking / Financial Institutions (in Millions IDR)."""
    # Earning & Liquid Assets
    cash_and_placements_bi_banks: float = 0.0
    marketable_securities: float = 0.0
    gross_loans: float = 0.0
    allowance_impairment_loans: float = 0.0  # CKPN
    net_loans: float = 0.0
    total_earning_assets: float = 0.0

    # Non-Earning / Other Assets
    net_fixed_assets: float = 0.0
    other_assets: float = 0.0
    total_assets: float = 0.0

    # Liabilities: Customer Deposits (DPK)
    current_accounts: float = 0.0
    savings_deposits: float = 0.0
    time_deposits: float = 0.0
    sharia_deposits: float = 0.0
    total_customer_deposits: float = 0.0

    # Other Liabilities & Syirkah
    deposits_from_other_banks: float = 0.0
    borrowings_issued_debt: float = 0.0
    other_liabilities: float = 0.0
    total_liabilities: float = 0.0
    temporary_syirkah_funds: float = 0.0

    # Equity
    share_capital: float = 0.0
    retained_earnings: float = 0.0
    other_equity: float = 0.0
    total_equity: float = 0.0
    total_liabilities_and_equity: float = 0.0
    balance_check: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "Cash & Placements with BI & Banks": self.cash_and_placements_bi_banks,
            "Marketable Securities": self.marketable_securities,
            "Gross Loans & Financing": self.gross_loans,
            "Allowance for Impairment (CKPN)": self.allowance_impairment_loans,
            "Net Loans & Financing": self.net_loans,
            "Total Earning Assets": self.total_earning_assets,
            "Premises & Fixed Assets (Net)": self.net_fixed_assets,
            "Other Assets (Tax, Intangibles, etc.)": self.other_assets,
            "TOTAL ASSETS": self.total_assets,
            "Current Accounts (Giro)": self.current_accounts,
            "Savings Deposits (Tabungan)": self.savings_deposits,
            "Time Deposits (Deposito)": self.time_deposits,
            "Total Customer Deposits (DPK)": self.total_customer_deposits,
            "Deposits from Other Banks": self.deposits_from_other_banks,
            "Borrowings & Debt Issued": self.borrowings_issued_debt,
            "Other Liabilities": self.other_liabilities,
            "TOTAL LIABILITIES": self.total_liabilities,
            "Temporary Syirkah Funds": self.temporary_syirkah_funds,
            "Share Capital & Additional Capital": self.share_capital,
            "Retained Earnings": self.retained_earnings,
            "Other Equity & Reserves": self.other_equity,
            "TOTAL EQUITY": self.total_equity,
            "TOTAL LIABILITIES, SYIRKAH & EQUITY": self.total_liabilities_and_equity,
            "BALANCE CHECK (Assets - Liab&Eq)": self.balance_check,
        }


@dataclass
class BankingCF(NormalizedCF):
    """Standardized Cash Flow Statement for Banking Archetype (in Millions IDR)."""
    pass


@dataclass
class BankingDrivers:
    """Historical modeling ratios and forecasting drivers for Banking Archetype."""
    loan_growth_yoy: Optional[float] = None
    deposit_growth_yoy: Optional[float] = None
    net_interest_margin_pct: Optional[float] = None  # NIM (%) = NII / Total Earning Assets
    cost_of_funds_pct: Optional[float] = None        # CoF (%) = Interest Expense / Total Deposits (DPK)
    loan_to_deposit_ratio_pct: Optional[float] = None # LDR (%) = Gross Loans / Total Deposits (DPK)
    casa_ratio_pct: Optional[float] = None           # CASA (%) = (Giro + Tabungan) / Total Deposits
    cost_to_income_ratio_pct: Optional[float] = None # CIR / BOPO (%) = Opex / Total Operating Income
    provision_rate_credit_cost_pct: Optional[float] = None # Credit Cost (%) = Provision / Gross Loans
    return_on_assets_pct: Optional[float] = None     # ROA (%) = Net Income / Total Assets
    return_on_equity_pct: Optional[float] = None     # ROE (%) = Net Income / Total Equity
    equity_to_assets_pct: Optional[float] = None     # Equity / Total Assets (%)
    effective_tax_rate_pct: Optional[float] = None
    dividend_payout_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Loan Growth (YoY)": self.loan_growth_yoy,
            "Deposit Growth (YoY)": self.deposit_growth_yoy,
            "Net Interest Margin (NIM %)": self.net_interest_margin_pct,
            "Cost of Funds (CoF %)": self.cost_of_funds_pct,
            "Loan-to-Deposit Ratio (LDR %)": self.loan_to_deposit_ratio_pct,
            "CASA Ratio (%)": self.casa_ratio_pct,
            "Cost-to-Income / BOPO (CIR %)": self.cost_to_income_ratio_pct,
            "Credit Cost / Provision Rate (%)": self.provision_rate_credit_cost_pct,
            "Return on Assets (ROA %)": self.return_on_assets_pct,
            "Return on Equity (ROE %)": self.return_on_equity_pct,
            "Equity to Assets Ratio (%)": self.equity_to_assets_pct,
            "Effective Tax Rate (%)": self.effective_tax_rate_pct,
            "Dividend Payout Ratio (%)": self.dividend_payout_pct,
        }

