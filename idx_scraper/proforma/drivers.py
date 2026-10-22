"""
Historical Operational Drivers and Ratio Computation Engine.
Calculates YoY growth rates, margins, working capital days (DSO, DIO, DPO),
Capex intensity, D&A rates, and statistical benchmarks (3-Year Median, 5-Year Average).
"""

from typing import Dict, Any, List, Optional
import statistics
import pandas as pd

from .schema import (
    NormalizedIS, NormalizedBS, NormalizedCF, OperationalDrivers,
    BankingIS, BankingBS, BankingCF, BankingDrivers
)


class DriverCalculator:
    """Computes historical forecasting drivers and ratios across multiple years."""

    @staticmethod
    def calculate_drivers(
        years: List[int],
        is_dict: Dict[int, NormalizedIS],
        bs_dict: Dict[int, NormalizedBS],
        cf_dict: Dict[int, NormalizedCF]
    ) -> Dict[int, OperationalDrivers]:
        """Compute operational drivers for each year."""
        drivers_by_year: Dict[int, OperationalDrivers] = {}
        sorted_years = sorted(years)

        for idx, yr in enumerate(sorted_years):
            d = OperationalDrivers()
            is_stmt = is_dict.get(yr, NormalizedIS())
            bs_stmt = bs_dict.get(yr, NormalizedBS())
            cf_stmt = cf_dict.get(yr, NormalizedCF())

            rev = is_stmt.revenue
            cogs = is_stmt.cogs

            # 1. Revenue Growth YoY
            if idx > 0:
                prev_yr = sorted_years[idx - 1]
                prev_rev = is_dict.get(prev_yr, NormalizedIS()).revenue
                if prev_rev > 0:
                    d.revenue_growth_yoy = (rev - prev_rev) / prev_rev

            # 2. Margins
            if rev > 0:
                d.gross_margin_pct = is_stmt.gross_profit / rev
                d.sgna_pct_revenue = is_stmt.sgna_opex / rev
                d.ebitda_margin_pct = is_stmt.ebitda / rev
                d.operating_margin_pct = is_stmt.operating_income_ebit / rev
                d.net_margin_pct = is_stmt.net_income / rev
                d.other_ca_pct_rev = bs_stmt.other_current_assets / rev
                d.other_cl_pct_rev = bs_stmt.other_current_liabilities / rev
                d.capex_pct_rev = cf_stmt.capex / rev

            # 3. Tax rate
            if is_stmt.ebt > 0:
                d.effective_tax_rate_pct = is_stmt.tax_expense / is_stmt.ebt

            # 4. Working Capital Days
            if rev > 0 and bs_stmt.accounts_receivable > 0:
                d.dso_days = (bs_stmt.accounts_receivable / rev) * 365.0
            else:
                d.dso_days = 0.0

            if cogs > 0 and bs_stmt.inventories > 0:
                d.dio_days = (bs_stmt.inventories / cogs) * 365.0
            else:
                d.dio_days = 0.0

            if cogs > 0 and bs_stmt.accounts_payable > 0:
                d.dpo_days = (bs_stmt.accounts_payable / cogs) * 365.0
            else:
                d.dpo_days = 0.0

            # 5. D&A % of Net PP&E
            if bs_stmt.net_ppe > 0:
                d.dna_pct_ppe = is_stmt.depreciation_amortization / bs_stmt.net_ppe

            # 6. Dividend Payout
            if is_stmt.net_income > 0 and cf_stmt.dividends_paid > 0:
                d.dividend_payout_pct = cf_stmt.dividends_paid / is_stmt.net_income
            else:
                d.dividend_payout_pct = 0.0

            # 7. Financing Rates
            total_debt = bs_stmt.short_term_debt + bs_stmt.long_term_debt
            if total_debt > 0 and is_stmt.finance_costs > 0:
                d.effective_borrowing_rate_pct = is_stmt.finance_costs / total_debt

            if bs_stmt.cash_and_equivalents > 0 and is_stmt.finance_income > 0:
                d.effective_interest_income_pct = is_stmt.finance_income / bs_stmt.cash_and_equivalents

            drivers_by_year[yr] = d

        return drivers_by_year

    @staticmethod
    def build_summary_benchmarks(
        drivers_by_year: Dict[int, OperationalDrivers]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Compute 3-Year Median and 5-Year Average benchmarks across computed drivers.
        Returns: {"3_Year_Median": {...}, "5_Year_Average": {...}}
        """
        sorted_years = sorted(drivers_by_year.keys())
        last_3_years = sorted_years[-3:] if len(sorted_years) >= 3 else sorted_years

        keys = list(OperationalDrivers().to_dict().keys())
        median_3yr: Dict[str, Optional[float]] = {}
        avg_5yr: Dict[str, Optional[float]] = {}

        for k in keys:
            # Last 3 years values
            vals_3 = [drivers_by_year[y].to_dict().get(k) for y in last_3_years]
            vals_3_valid = [v for v in vals_3 if v is not None and isinstance(v, (int, float))]
            median_3yr[k] = statistics.median(vals_3_valid) if vals_3_valid else None

            # All years values
            vals_all = [drivers_by_year[y].to_dict().get(k) for y in sorted_years]
            vals_all_valid = [v for v in vals_all if v is not None and isinstance(v, (int, float))]
            avg_5yr[k] = statistics.mean(vals_all_valid) if vals_all_valid else None

        return {
            "3_Year_Median": median_3yr,
            "5_Year_Average": avg_5yr,
            "Historical_Average": avg_5yr
        }


class BankingDriverCalculator:
    """Computes historical forecasting drivers and ratios for Banking / Financial Institutions."""

    @staticmethod
    def calculate_drivers(
        years: List[int],
        is_dict: Dict[int, BankingIS],
        bs_dict: Dict[int, BankingBS],
        cf_dict: Dict[int, BankingCF]
    ) -> Dict[int, BankingDrivers]:
        """Compute operational drivers for each year for a banking entity."""
        drivers_by_year: Dict[int, BankingDrivers] = {}
        sorted_years = sorted(years)

        for idx, yr in enumerate(sorted_years):
            d = BankingDrivers()
            is_stmt = is_dict.get(yr, BankingIS())
            bs_stmt = bs_dict.get(yr, BankingBS())
            cf_stmt = cf_dict.get(yr, BankingCF())

            # 1. Growth Rates YoY
            if idx > 0:
                prev_yr = sorted_years[idx - 1]
                prev_bs = bs_dict.get(prev_yr, BankingBS())
                if prev_bs.gross_loans > 0 and bs_stmt.gross_loans > 0:
                    d.loan_growth_yoy = (bs_stmt.gross_loans - prev_bs.gross_loans) / prev_bs.gross_loans
                if prev_bs.total_customer_deposits > 0 and bs_stmt.total_customer_deposits > 0:
                    d.deposit_growth_yoy = (bs_stmt.total_customer_deposits - prev_bs.total_customer_deposits) / prev_bs.total_customer_deposits

            # 2. Net Interest Margin (NIM %) = NII / Earning Assets
            if bs_stmt.total_earning_assets > 0:
                d.net_interest_margin_pct = is_stmt.net_interest_income / bs_stmt.total_earning_assets

            # 3. Cost of Funds (CoF %) = Interest Expense / Total Deposits (DPK)
            if bs_stmt.total_customer_deposits > 0:
                d.cost_of_funds_pct = is_stmt.interest_expense / bs_stmt.total_customer_deposits

            # 4. Loan-to-Deposit Ratio (LDR %) = Gross Loans / Total Deposits (DPK)
            if bs_stmt.total_customer_deposits > 0 and bs_stmt.gross_loans > 0:
                d.loan_to_deposit_ratio_pct = bs_stmt.gross_loans / bs_stmt.total_customer_deposits

            # 5. CASA Ratio (%) = (Current Accounts + Savings) / Total Customer Deposits
            if bs_stmt.total_customer_deposits > 0:
                casa_amt = bs_stmt.current_accounts + bs_stmt.savings_deposits
                d.casa_ratio_pct = casa_amt / bs_stmt.total_customer_deposits

            # 6. Cost-to-Income / BOPO (CIR %) = Operating Expenses / Total Operating Income
            if is_stmt.total_operating_income > 0:
                d.cost_to_income_ratio_pct = is_stmt.operating_expenses / is_stmt.total_operating_income

            # 7. Credit Cost / Provisioning Rate (%) = CKPN / Gross Loans
            if bs_stmt.gross_loans > 0 and is_stmt.provision_impairment_losses > 0:
                d.provision_rate_credit_cost_pct = is_stmt.provision_impairment_losses / bs_stmt.gross_loans

            # 8. Return on Assets (ROA %) & Return on Equity (ROE %)
            if bs_stmt.total_assets > 0:
                d.return_on_assets_pct = is_stmt.net_income / bs_stmt.total_assets
            if bs_stmt.total_equity > 0:
                d.return_on_equity_pct = is_stmt.net_income / bs_stmt.total_equity

            # 9. Capital / Solvency: Equity to Assets (%)
            if bs_stmt.total_assets > 0:
                d.equity_to_assets_pct = bs_stmt.total_equity / bs_stmt.total_assets

            # 10. Effective Tax Rate (%)
            if is_stmt.ebt > 0:
                d.effective_tax_rate_pct = is_stmt.tax_expense / is_stmt.ebt

            # 11. Dividend Payout Ratio (%)
            if is_stmt.net_income > 0 and cf_stmt.dividends_paid > 0:
                d.dividend_payout_pct = cf_stmt.dividends_paid / is_stmt.net_income
            else:
                d.dividend_payout_pct = 0.0

            drivers_by_year[yr] = d

        return drivers_by_year

    @staticmethod
    def build_summary_benchmarks(
        drivers_by_year: Dict[int, BankingDrivers]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """Compute 3-Year Median and Historical Average benchmarks across banking drivers."""
        sorted_years = sorted(drivers_by_year.keys())
        last_3_years = sorted_years[-3:] if len(sorted_years) >= 3 else sorted_years

        keys = list(BankingDrivers().to_dict().keys())
        median_3yr: Dict[str, Optional[float]] = {}
        avg_hist: Dict[str, Optional[float]] = {}

        for k in keys:
            vals_3 = [drivers_by_year[y].to_dict().get(k) for y in last_3_years]
            vals_3_valid = [v for v in vals_3 if v is not None and isinstance(v, (int, float))]
            median_3yr[k] = statistics.median(vals_3_valid) if vals_3_valid else None

            vals_all = [drivers_by_year[y].to_dict().get(k) for y in sorted_years]
            vals_all_valid = [v for v in vals_all if v is not None and isinstance(v, (int, float))]
            avg_hist[k] = statistics.mean(vals_all_valid) if vals_all_valid else None

        return {
            "3_Year_Median": median_3yr,
            "5_Year_Average": avg_hist,
            "Historical_Average": avg_hist
        }

