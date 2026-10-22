"""
4-Tier Normalization Engine.
Reconciles disparate IDX line items, performs waterfall child aggregation,
scales all values to Millions IDR, and guarantees mathematical balance.
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from .schema import NormalizedIS, NormalizedBS, NormalizedCF

logger = logging.getLogger("idx_scraper.proforma.normalizer")


class FinancialNormalizer:
    """Normalizes raw multi-year tables into clean 3-statement modeling accounts."""

    def __init__(self, target_scale: str = "millions"):
        self.target_scale = target_scale  # "millions"

    def _determine_scale_factor(self, total_assets: float, general_info: Optional[Dict[str, str]] = None) -> float:
        """
        Detect scale of reported data and return multiplier to convert to Millions IDR.
        Checks metadata in general_info first, then falls back to Total Assets threshold.
        """
        if general_info:
            for k, v in general_info.items():
                if "pembulatan" in k.lower():
                    v_low = str(v).lower()
                    if "miliar" in v_low or "billion" in v_low:
                        return 1_000.0  # Billions IDR -> Millions IDR
                    elif "juta" in v_low or "million" in v_low:
                        return 1.0  # Millions IDR
                    elif "ribu" in v_low or "thousand" in v_low:
                        return 0.001  # Thousands IDR -> Millions IDR
                    elif "satuan penuh" in v_low or "full" in v_low:
                        return 1.0 / 1_000_000.0  # Full IDR -> Millions IDR

        # Fallback heuristic based on typical asset ranges
        if total_assets > 1_000_000_000:
            return 1.0 / 1_000_000.0  # Full Rupiah -> Millions IDR
        elif total_assets > 1_000_000:
            return 1.0  # Millions IDR
        elif 0 < total_assets <= 1_000_000:
            return 1_000.0  # Billions IDR -> Millions IDR
        return 1.0

    @staticmethod
    def _find_val(df: pd.DataFrame, patterns: List[str], year_col: str) -> Optional[float]:
        """Search for a row matching any regex pattern (case-insensitive) and return float value."""
        if df.empty or year_col not in df.columns or "Item_ID" not in df.columns:
            return None

        for pat in patterns:
            try:
                # Try exact/substring match on Item_ID
                mask = df["Item_ID"].str.contains(pat, case=False, na=False, regex=True)
                matched = df[mask]
                if not matched.empty:
                    for _, row in matched.iterrows():
                        v = row.get(year_col)
                        if pd.notna(v) and v != "":
                            try:
                                return float(v)
                            except (ValueError, TypeError):
                                pass
            except Exception:
                pass
        return None

    def _resolve_waterfall(
        self,
        df: pd.DataFrame,
        primary_patterns: List[str],
        child_patterns: List[str] = [],
        year_col: str = "2024",
        scale: float = 1.0
    ) -> float:
        """
        Waterfall resolution:
        1. Check primary summary lines
        2. If none, sum child accounts
        3. If none, return 0.0
        """
        # 1. Primary
        val = self._find_val(df, primary_patterns, year_col)
        if val is not None and val != 0.0:
            return float(val) * scale

        # 2. Child aggregation
        if child_patterns:
            child_sum = 0.0
            found_any = False
            for c_pat in child_patterns:
                c_val = self._find_val(df, [c_pat], year_col)
                if c_val is not None and pd.notna(c_val):
                    child_sum += float(c_val)
                    found_any = True
            if found_any:
                return child_sum * scale

        return 0.0

    def normalize_year(
        self,
        year: int,
        df_is: pd.DataFrame,
        df_bs: pd.DataFrame,
        df_cf: pd.DataFrame,
        general_info: Dict[str, str] = {}
    ) -> Tuple[NormalizedIS, NormalizedBS, NormalizedCF]:
        """
        Normalize a single year's financial data across IS, BS, and CF.
        All figures are scaled to Millions IDR.
        """
        yr_str = str(year)

        # 1. Determine unit scale factor from Total Assets
        raw_assets = self._find_val(df_bs, [r"^jumlah aset\s*$", r"^total assets\s*$", r"^total aset\s*$"], yr_str)
        if raw_assets is None or raw_assets == 0:
            # Fallback to sum of current and non-current if total is missing
            ca_tmp = self._find_val(df_bs, [r"^jumlah aset lancar\s*$", r"^total current assets\s*$"], yr_str) or 0.0
            nca_tmp = self._find_val(df_bs, [r"^jumlah aset tidak lancar\s*$", r"^total non-current assets\s*$"], yr_str) or 0.0
            raw_assets = ca_tmp + nca_tmp
        scale = self._determine_scale_factor(raw_assets, general_info=general_info)

        # Detect banking industry
        sector_str = (general_info.get("Industri utama entitas", "") + " " + general_info.get("Sektor", "")).lower()
        is_bank = "bank" in sector_str or "keuangan" in sector_str or "sharia" in sector_str

        # ----------------------------------------------------
        # BALANCE SHEET RESOLUTION
        # ----------------------------------------------------
        bs = NormalizedBS()
        
        # Cash & Equivalents
        bs.cash_and_equivalents = self._resolve_waterfall(
            df_bs,
            primary_patterns=[
                r"^kas dan setara kas\s*$",
                r"^cash and cash equivalents\s*$",
                r"^kas\s*$"
            ],
            year_col=yr_str, scale=scale
        )

        # Accounts Receivable (or Bank Placements / Earning Assets for Banks)
        if is_bank:
            bs.accounts_receivable = self._resolve_waterfall(
                df_bs,
                primary_patterns=[
                    r"^giro pada bank indonesia\s*$",
                    r"^penempatan pada bank indonesia dan bank lain\s*$"
                ],
                year_col=yr_str, scale=scale
            )
        else:
            bs.accounts_receivable = self._resolve_waterfall(
                df_bs,
                primary_patterns=[r"^jumlah piutang usaha\s*$", r"^piutang usaha\s*$", r"^total trade receivables\s*$"],
                child_patterns=[
                    r"piutang usaha pihak ketiga",
                    r"piutang usaha pihak berelasi",
                    r"piutang usaha\s*-\s*pihak ketiga",
                    r"piutang usaha\s*-\s*pihak berelasi",
                ],
                year_col=yr_str, scale=scale
            )

        # Inventories (or Kredit yang Diberikan / Loans for Banks)
        if is_bank:
            bs.inventories = self._resolve_waterfall(
                df_bs,
                primary_patterns=[r"^kredit yang diberikan\s*$", r"^loans\s*$"],
                year_col=yr_str, scale=scale
            )
        else:
            bs.inventories = self._resolve_waterfall(
                df_bs,
                primary_patterns=[r"^jumlah persediaan\s*$", r"^persediaan lancar\s*$", r"^persediaan\s*$", r"^inventories\s*$"],
                child_patterns=[r"persediaan lainnya", r"persediaan bahan baku", r"persediaan barang jadi"],
                year_col=yr_str, scale=scale
            )

        # Total Current Assets
        official_current_assets = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^jumlah aset lancar\s*$", r"^total current assets\s*$"],
            year_col=yr_str, scale=scale
        )
        if official_current_assets > 0:
            bs.total_current_assets = official_current_assets
            sub_ca = bs.cash_and_equivalents + bs.accounts_receivable + bs.inventories
            bs.other_current_assets = max(0.0, bs.total_current_assets - sub_ca)
        else:
            # Banks or unclassified balance sheets: group liquid & earning assets
            bs.total_current_assets = bs.cash_and_equivalents + bs.accounts_receivable + bs.inventories
            bs.other_current_assets = 0.0

        # Net PP&E
        bs.net_ppe = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^aset tetap\s*$", r"^property,? plant and equipment\s*$", r"^properti dan peralatan\s*$"],
            year_col=yr_str, scale=scale
        )

        # Total Assets (Exact Total)
        official_total_assets = self._resolve_waterfall(
            df_bs, [r"^jumlah aset\s*$", r"^total assets\s*$"], year_col=yr_str, scale=scale
        )

        # Total Non-Current Assets
        official_non_current = self._resolve_waterfall(
            df_bs, [r"^jumlah aset tidak lancar\s*$", r"^total non-current assets\s*$"], year_col=yr_str, scale=scale
        )
        if official_non_current > 0:
            bs.total_non_current_assets = official_non_current
            bs.other_non_current_assets = max(0.0, bs.total_non_current_assets - bs.net_ppe)
        elif official_total_assets > 0:
            bs.total_non_current_assets = max(0.0, official_total_assets - bs.total_current_assets)
            bs.other_non_current_assets = max(0.0, bs.total_non_current_assets - bs.net_ppe)
        else:
            bs.other_non_current_assets = 0.0
            bs.total_non_current_assets = bs.net_ppe

        bs.total_assets = official_total_assets if official_total_assets > 0 else (bs.total_current_assets + bs.total_non_current_assets)

        # Accounts Payable (or Simpanan Nasabah / Deposits for Banks)
        if is_bank:
            bs.accounts_payable = self._resolve_waterfall(
                df_bs,
                primary_patterns=[r"^simpanan nasabah\s*$", r"^simpanan dari nasabah\s*$", r"^deposits\s*$"],
                year_col=yr_str, scale=scale
            )
        else:
            bs.accounts_payable = self._resolve_waterfall(
                df_bs,
                primary_patterns=[r"^jumlah utang usaha\s*$", r"^utang usaha\s*$", r"^trade payables\s*$"],
                child_patterns=[r"utang usaha pihak ketiga", r"utang usaha pihak berelasi"],
                year_col=yr_str, scale=scale
            )

        # Short-Term Debt
        bs.short_term_debt = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^pinjaman jangka pendek\s*$", r"^short-term bank loans\s*$"],
            child_patterns=[
                r"pinjaman bank jangka pendek",
                r"bagian lancar atas pinjaman jangka panjang",
                r"bagian lancar atas utang bank",
                r"liabilitas sewa jangka pendek",
                r"utang bank jangka pendek"
            ],
            year_col=yr_str, scale=scale
        )

        # Total Current Liabilities
        official_current_liab = self._resolve_waterfall(
            df_bs, [r"^jumlah liabilitas jangka pendek\s*$", r"^total current liabilities\s*$"], year_col=yr_str, scale=scale
        )
        if official_current_liab > 0:
            bs.total_current_liabilities = official_current_liab
            sub_cl = bs.accounts_payable + bs.short_term_debt
            bs.other_current_liabilities = max(0.0, bs.total_current_liabilities - sub_cl)
        else:
            bs.total_current_liabilities = bs.accounts_payable + bs.short_term_debt
            bs.other_current_liabilities = 0.0

        # Long-Term Debt
        bs.long_term_debt = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^pinjaman jangka panjang\s*$", r"^long-term debt\s*$"],
            child_patterns=[
                r"pinjaman bank jangka panjang setelah dikurangi bagian yang jatuh tempo",
                r"pinjaman bank jangka panjang",
                r"utang obligasi",
                r"liabilitas sewa jangka panjang"
            ],
            year_col=yr_str, scale=scale
        )

        # Total Non-Current Liabilities
        official_non_current_liab = self._resolve_waterfall(
            df_bs, [
                r"^jumlah liabilitas jangka panjang\s*$",
                r"^jumlah liabilitas tidak lancar\s*$",
                r"^total non-current liabilities\s*$"
            ],
            year_col=yr_str, scale=scale
        )

        # Total Liabilities + Dana Syirkah Temporer (for banks)
        official_liab = self._resolve_waterfall(
            df_bs, [r"^jumlah liabilitas\s*$", r"^total liabilities\s*$"], year_col=yr_str, scale=scale
        )
        syirkah_funds = self._resolve_waterfall(
            df_bs, [r"^jumlah dana syirkah temporer\s*$", r"^dana syirkah temporer\s*$"], year_col=yr_str, scale=scale
        )

        if official_liab > 0:
            bs.total_liabilities = official_liab + syirkah_funds
            if official_non_current_liab > 0:
                bs.total_non_current_liabilities = official_non_current_liab
            else:
                bs.total_non_current_liabilities = max(0.0, bs.total_liabilities - bs.total_current_liabilities)
            bs.other_non_current_liabilities = max(0.0, bs.total_non_current_liabilities - bs.long_term_debt)
        else:
            bs.total_non_current_liabilities = (official_non_current_liab if official_non_current_liab > 0 else bs.long_term_debt) + syirkah_funds
            bs.other_non_current_liabilities = max(0.0, bs.total_non_current_liabilities - bs.long_term_debt)
            bs.total_liabilities = bs.total_current_liabilities + bs.total_non_current_liabilities

        # Total Equity
        official_equity = self._resolve_waterfall(
            df_bs, [r"^jumlah ekuitas\s*$", r"^total equity\s*$"], year_col=yr_str, scale=scale
        )
        bs.total_equity = official_equity if official_equity > 0 else max(0.0, bs.total_assets - bs.total_liabilities)

        # Retained Earnings
        bs.retained_earnings = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^saldo laba\s*$", r"^retained earnings\s*$"],
            child_patterns=[
                r"saldo laba yang telah ditentukan penggunaannya",
                r"saldo laba yang belum ditentukan penggunaannya",
                r"saldo laba belum dicadangkan"
            ],
            year_col=yr_str, scale=scale
        )

        # Share Capital & Other Equity
        bs.share_capital = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^modal saham\s*$", r"^share capital\s*$"],
            child_patterns=[r"tambahan modal disetor"],
            year_col=yr_str, scale=scale
        )
        bs.other_equity = max(0.0, bs.total_equity - (bs.share_capital + bs.retained_earnings))

        # Liabilities & Equity Total
        bs.total_liabilities_and_equity = bs.total_liabilities + bs.total_equity
        bs.balance_check = round(bs.total_assets - bs.total_liabilities_and_equity, 2)

        # ----------------------------------------------------
        # INCOME STATEMENT RESOLUTION
        # ----------------------------------------------------
        is_stmt = NormalizedIS()

        # Revenue
        if is_bank:
            is_stmt.revenue = self._resolve_waterfall(
                df_is,
                primary_patterns=[r"^pendapatan bunga\s*$", r"^pendapatan bunga dan syariah\s*$"],
                year_col=yr_str, scale=scale
            )
            is_stmt.cogs = self._resolve_waterfall(
                df_is,
                primary_patterns=[r"^beban bunga\s*$", r"^beban bagi hasil syariah\s*$"],
                year_col=yr_str, scale=scale
            )
        else:
            is_stmt.revenue = self._resolve_waterfall(
                df_is,
                primary_patterns=[
                    r"^penjualan dan pendapatan usaha\s*$",
                    r"^pendapatan usaha\s*$",
                    r"^jumlah pendapatan\s*$",
                    r"^penjualan bersih\s*$",
                    r"^sales and revenue\s*$"
                ],
                year_col=yr_str, scale=scale
            )
            is_stmt.cogs = self._resolve_waterfall(
                df_is,
                primary_patterns=[
                    r"^beban pokok penjualan\s*$",
                    r"^beban pokok pendapatan\s*$",
                    r"^beban pokok penjualan dan pendapatan\s*$",
                    r"^cost of sales and revenue\s*$"
                ],
                child_patterns=[r"beban operasional jaringan"],  # Telco fallback
                year_col=yr_str, scale=scale
            )

        # Gross Profit
        is_stmt.gross_profit = max(0.0, is_stmt.revenue - is_stmt.cogs)

        # D&A
        is_stmt.depreciation_amortization = self._resolve_waterfall(
            df_is,
            primary_patterns=[r"beban penyusutan dan amortisasi", r"depreciation and amortisation"],
            year_col=yr_str, scale=scale
        )

        # SG&A / Operating Expenses
        raw_sgna = self._resolve_waterfall(
            df_is,
            primary_patterns=[r"^beban usaha\b", r"^beban operasional\b", r"^operating expenses\b"],
            child_patterns=[r"beban umum dan administrasi", r"beban penjualan"],
            year_col=yr_str, scale=scale
        )
        is_stmt.sgna_opex = raw_sgna

        # Operating Income (EBIT)
        official_ebit = self._resolve_waterfall(
            df_is, [r"^laba usaha\b", r"^laba operasi\b", r"^operating profit\b"], year_col=yr_str, scale=scale
        )
        if official_ebit != 0.0:
            is_stmt.operating_income_ebit = official_ebit
            is_stmt.ebitda = is_stmt.operating_income_ebit + is_stmt.depreciation_amortization
        else:
            is_stmt.operating_income_ebit = is_stmt.gross_profit - is_stmt.sgna_opex
            is_stmt.ebitda = is_stmt.operating_income_ebit + is_stmt.depreciation_amortization

        # Finance Income & Finance Costs
        is_stmt.finance_income = self._resolve_waterfall(
            df_is, [r"^pendapatan keuangan\b", r"^finance income\b", r"^pendapatan bunga\b"], year_col=yr_str, scale=scale
        )
        is_stmt.finance_costs = self._resolve_waterfall(
            df_is, [r"^beban keuangan\b", r"^finance costs\b", r"^beban bunga\b"], year_col=yr_str, scale=scale
        )
        is_stmt.net_finance_costs = is_stmt.finance_income - is_stmt.finance_costs

        # EBT (Profit before tax)
        official_ebt = self._resolve_waterfall(
            df_is,
            primary_patterns=[
                r"laba \(rugi\) sebelum pajak penghasilan",
                r"jumlah laba \(rugi\) sebelum beban pajak",
                r"profit \(loss\) before tax"
            ],
            year_col=yr_str, scale=scale
        )
        is_stmt.ebt = official_ebt if official_ebt != 0.0 else (is_stmt.operating_income_ebit + is_stmt.net_finance_costs)

        # Tax Expense
        raw_tax = self._resolve_waterfall(
            df_is, [r"beban pajak penghasilan", r"tax expense", r"pendapatan \(beban\) pajak"], year_col=yr_str, scale=scale
        )
        is_stmt.tax_expense = abs(raw_tax)

        # Net Income
        official_ni = self._resolve_waterfall(
            df_is,
            primary_patterns=[
                r"^jumlah laba \(rugi\)\b",
                r"^laba tahun berjalan\b",
                r"^laba bersih\b",
                r"^total profit \(loss\)\b"
            ],
            year_col=yr_str, scale=scale
        )
        is_stmt.net_income = official_ni if official_ni != 0.0 else (is_stmt.ebt - is_stmt.tax_expense)

        # Net Income to Parent
        is_stmt.net_income_parent = self._resolve_waterfall(
            df_is,
            primary_patterns=[
                r"laba \(rugi\) yang dapat diatribusikan ke entitas induk",
                r"laba yang dapat diatribusikan kepada pemilik entitas induk",
                r"profit attributable to parent"
            ],
            year_col=yr_str, scale=scale
        )
        if is_stmt.net_income_parent == 0.0:
            is_stmt.net_income_parent = is_stmt.net_income

        # ----------------------------------------------------
        # CASH FLOW STATEMENT RESOLUTION
        # ----------------------------------------------------
        cf = NormalizedCF()

        # Operating Cash Flow
        cf.operating_cash_flow = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"arus kas bersih yang diperoleh dari.*aktivitas operasi",
                r"arus kas dari aktivitas operasi",
                r"net cash flows.*operating activities"
            ],
            year_col=yr_str, scale=scale
        )

        # Capex
        cf.capex = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"perolehan aset tetap",
                r"pembayaran untuk perolehan aset tetap",
                r"pembelian aset tetap",
                r"acquisition of property,? plant and equipment"
            ],
            year_col=yr_str, scale=scale
        )
        cf.capex = abs(cf.capex)

        # Investing Cash Flow
        cf.investing_cash_flow = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"arus kas bersih yang digunakan untuk aktivitas investasi",
                r"arus kas dari aktivitas investasi",
                r"net cash flows.*investing activities"
            ],
            year_col=yr_str, scale=scale
        )

        # Dividends Paid
        cf.dividends_paid = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"pembayaran dividen kas",
                r"pembayaran dividen",
                r"dividen yang dibayarkan",
                r"dividends paid"
            ],
            year_col=yr_str, scale=scale
        )
        cf.dividends_paid = abs(cf.dividends_paid)

        # Financing Cash Flow
        cf.financing_cash_flow = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"arus kas bersih yang digunakan untuk.*aktivitas pendanaan",
                r"arus kas dari aktivitas pendanaan",
                r"net cash flows.*financing activities"
            ],
            year_col=yr_str, scale=scale
        )

        # Net Change in Cash
        cf.net_change_in_cash = self._resolve_waterfall(
            df_cf,
            primary_patterns=[
                r"kenaikan \(penurunan\) bersih kas dan setara kas",
                r"net increase \(decrease\) in cash and cash equivalents"
            ],
            year_col=yr_str, scale=scale
        )

        # Ending Cash
        cf.ending_cash = bs.cash_and_equivalents
        cf.beginning_cash = max(0.0, cf.ending_cash - cf.net_change_in_cash)

        return is_stmt, bs, cf
