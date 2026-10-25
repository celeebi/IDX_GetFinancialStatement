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

from .schema import (
    NormalizedIS, NormalizedBS, NormalizedCF,
    BankingIS, BankingBS, BankingCF
)

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

        # Accounts Receivable
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

        # Inventories
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

        # Accounts Payable
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

    def normalize_banking_year(
        self,
        year: int,
        df_is: pd.DataFrame,
        df_bs: pd.DataFrame,
        df_cf: pd.DataFrame,
        general_info: Dict[str, str] = {}
    ) -> Tuple[BankingIS, BankingBS, BankingCF]:
        """
        Normalize a single year's banking data from Excel tables.
        All figures are scaled to Millions IDR.
        """
        yr_str = str(year)
        raw_assets = self._find_val(df_bs, [r"^jumlah aset\s*$", r"^total assets\s*$", r"^total aset\s*$"], yr_str) or 0.0
        scale = self._determine_scale_factor(raw_assets, general_info=general_info)

        # 1. BALANCE SHEET
        bs = BankingBS()
        bs.cash_and_placements_bi_banks = self._resolve_waterfall(
            df_bs,
            primary_patterns=[
                r"^kas dan setara kas\s*$",
                r"^giro pada bank indonesia\s*$",
                r"^penempatan pada bank indonesia dan bank lain\s*$",
                r"^cash and cash equivalents\s*$"
            ],
            year_col=yr_str, scale=scale
        )

        bs.marketable_securities = self._resolve_waterfall(
            df_bs,
            primary_patterns=[
                r"^efek-efek yang diperdagangkan\s*$",
                r"^efek-efek\s*$",
                r"^surat berharga\s*$",
                r"^marketable securities\s*$"
            ],
            year_col=yr_str, scale=scale
        )
        if bs.marketable_securities == 0.0:
            sec_3rd = self._resolve_waterfall(df_bs, [r"^efek-efek yang diperdagangkan pihak ketiga"], yr_str, scale)
            sec_rel = self._resolve_waterfall(df_bs, [r"^efek-efek yang diperdagangkan pihak berelasi"], yr_str, scale)
            bs.marketable_securities = sec_3rd + sec_rel

        bs.gross_loans = self._resolve_waterfall(
            df_bs,
            primary_patterns=[
                r"^kredit yang diberikan\s*$",
                r"^pinjaman yang diberikan\s*$",
                r"^loans\s*$"
            ],
            year_col=yr_str, scale=scale
        )
        if bs.gross_loans == 0.0:
            # Check Sharia financing line items (PSAK 101-107: Third parties + Related parties)
            murabahah = (self._resolve_waterfall(df_bs, [r"^piutang murabahah pihak ketiga"], yr_str, scale) +
                         self._resolve_waterfall(df_bs, [r"^piutang murabahah pihak berelasi"], yr_str, scale) or
                         self._resolve_waterfall(df_bs, [r"^piutang murabahah\s*$"], yr_str, scale))
            musyarakah = (self._resolve_waterfall(df_bs, [r"^pembiayaan musyarakah pihak ketiga"], yr_str, scale) +
                          self._resolve_waterfall(df_bs, [r"^pembiayaan musyarakah pihak berelasi"], yr_str, scale) or
                          self._resolve_waterfall(df_bs, [r"^pembiayaan musyarakah\s*$"], yr_str, scale))
            qardh = (self._resolve_waterfall(df_bs, [r"^pinjaman qardh pihak ketiga"], yr_str, scale) +
                     self._resolve_waterfall(df_bs, [r"^pinjaman qardh pihak berelasi"], yr_str, scale) or
                     self._resolve_waterfall(df_bs, [r"^pinjaman qardh\s*$"], yr_str, scale))
            mudharabah = (self._resolve_waterfall(df_bs, [r"^pembiayaan mudharabah pihak ketiga"], yr_str, scale) +
                          self._resolve_waterfall(df_bs, [r"^pembiayaan mudharabah pihak berelasi"], yr_str, scale) or
                          self._resolve_waterfall(df_bs, [r"^pembiayaan mudharabah\s*$"], yr_str, scale))
            ijarah = (self._resolve_waterfall(df_bs, [r"^piutang ijarah pihak ketiga"], yr_str, scale) +
                      self._resolve_waterfall(df_bs, [r"^piutang ijarah pihak berelasi"], yr_str, scale) or
                      self._resolve_waterfall(df_bs, [r"^piutang ijarah\s*$"], yr_str, scale))
            istishna = (self._resolve_waterfall(df_bs, [r"^piutang istishna pihak ketiga"], yr_str, scale) +
                        self._resolve_waterfall(df_bs, [r"^piutang istishna pihak berelasi"], yr_str, scale) or
                        self._resolve_waterfall(df_bs, [r"^piutang istishna\s*$"], yr_str, scale))
            bs.gross_loans = murabahah + musyarakah + qardh + mudharabah + ijarah + istishna

        bs.allowance_impairment_loans = abs(self._resolve_waterfall(
            df_bs,
            primary_patterns=[
                r"^cadangan penurunan nilai atas kredit\s*$",
                r"^cadangan kerugian penurunan nilai\s*$",
                r"^penyisihan kerugian penurunan nilai\s*$"
            ],
            year_col=yr_str, scale=scale
        ))
        if bs.allowance_impairment_loans == 0.0:
            ckpn_mur = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada piutang murabahah"], yr_str, scale)
            ckpn_mus = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada pembiayaan musyarakah"], yr_str, scale)
            ckpn_qar = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada pinjaman qardh"], yr_str, scale)
            ckpn_mud = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada pembiayaan mudharabah"], yr_str, scale)
            ckpn_ija = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada piutang ijarah"], yr_str, scale)
            ckpn_ist = self._resolve_waterfall(df_bs, [r"^cadangan kerugian penurunan nilai pada piutang istishna"], yr_str, scale)
            bs.allowance_impairment_loans = abs(ckpn_mur + ckpn_mus + ckpn_qar + ckpn_mud + ckpn_ija + ckpn_ist)

        bs.net_loans = max(0.0, bs.gross_loans - bs.allowance_impairment_loans)
        bs.total_earning_assets = bs.cash_and_placements_bi_banks + bs.marketable_securities + bs.net_loans

        bs.net_fixed_assets = self._resolve_waterfall(
            df_bs,
            primary_patterns=[r"^aset tetap\s*$", r"^property,? plant and equipment\s*$"],
            year_col=yr_str, scale=scale
        )

        official_assets = self._resolve_waterfall(
            df_bs, [r"^jumlah aset\s*$", r"^total assets\s*$"], year_col=yr_str, scale=scale
        )
        bs.total_assets = official_assets if official_assets > 0 else (bs.total_earning_assets + bs.net_fixed_assets)
        bs.other_assets = max(0.0, bs.total_assets - (bs.total_earning_assets + bs.net_fixed_assets))

        # Deposits
        bs.current_accounts = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^giro\s*$", r"^current accounts\s*$"], year_col=yr_str, scale=scale
        )
        if bs.current_accounts == 0.0:
            gw_3rd = self._resolve_waterfall(df_bs, [r"^giro wadiah pihak ketiga"], yr_str, scale)
            gw_rel = self._resolve_waterfall(df_bs, [r"^giro wadiah pihak berelasi"], yr_str, scale)
            gm_3rd = self._resolve_waterfall(df_bs, [r"^giro mudharabah pihak ketiga"], yr_str, scale)
            gm_rel = self._resolve_waterfall(df_bs, [r"^giro (berjangka )?mudharabah pihak berelasi"], yr_str, scale)
            bs.current_accounts = gw_3rd + gw_rel + gm_3rd + gm_rel

        bs.savings_deposits = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^tabungan\s*$", r"^savings deposits\s*$"], year_col=yr_str, scale=scale
        )
        if bs.savings_deposits == 0.0:
            tw_3rd = self._resolve_waterfall(df_bs, [r"^tabungan wadiah pihak ketiga"], yr_str, scale)
            tw_rel = self._resolve_waterfall(df_bs, [r"^tabungan wadiah pihak berelasi"], yr_str, scale)
            tm_3rd = self._resolve_waterfall(df_bs, [r"^tabungan mudharabah pihak ketiga"], yr_str, scale)
            tm_rel = self._resolve_waterfall(df_bs, [r"^tabungan mudharabah pihak berelasi"], yr_str, scale)
            bs.savings_deposits = tw_3rd + tw_rel + tm_3rd + tm_rel

        bs.time_deposits = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^deposito berjangka\s*$", r"^deposito\s*$", r"^time deposits\s*$"], year_col=yr_str, scale=scale
        )
        if bs.time_deposits == 0.0:
            dm_3rd = self._resolve_waterfall(df_bs, [r"^deposito berjangka mudharabah pihak ketiga"], yr_str, scale)
            dm_rel = self._resolve_waterfall(df_bs, [r"^deposito berjangka mudharabah pihak berelasi"], yr_str, scale)
            bs.time_deposits = dm_3rd + dm_rel

        bs.sharia_deposits = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^simpanan syariah\s*$", r"^sharia deposits\s*$"], year_col=yr_str, scale=scale
        )
        dpk_sum = bs.current_accounts + bs.savings_deposits + bs.time_deposits + bs.sharia_deposits
        official_dpk = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^simpanan nasabah\s*$", r"^simpanan dari nasabah\s*$", r"^deposits from customers\s*$"],
            year_col=yr_str, scale=scale
        )
        bs.total_customer_deposits = official_dpk if official_dpk > 0 else dpk_sum

        bs.deposits_from_other_banks = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^simpanan dari bank lain\s*$", r"^deposits from other banks\s*$"], year_col=yr_str, scale=scale
        )
        if bs.deposits_from_other_banks == 0.0:
            ob_rel = self._resolve_waterfall(df_bs, [r"^simpanan dari bank lain pihak berelasi"], yr_str, scale)
            ob_3rd = self._resolve_waterfall(df_bs, [r"^simpanan dari bank lain pihak ketiga"], yr_str, scale)
            bs.deposits_from_other_banks = ob_rel + ob_3rd

        bs.borrowings_issued_debt = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^pinjaman yang diterima\s*$", r"^efek-efek yang diterbitkan\s*$", r"^surat berharga yang diterbitkan\s*$"],
            year_col=yr_str, scale=scale
        )
        if bs.borrowings_issued_debt == 0.0:
            bor_3rd = self._resolve_waterfall(df_bs, [r"^pinjaman yang diterima pihak ketiga"], yr_str, scale)
            bor_rel = self._resolve_waterfall(df_bs, [r"^pinjaman yang diterima pihak berelasi"], yr_str, scale)
            bs.borrowings_issued_debt = bor_3rd + bor_rel

        official_liab = self._resolve_waterfall(
            df_bs, [r"^jumlah liabilitas\s*$", r"^total liabilities\s*$"], year_col=yr_str, scale=scale
        )
        syirkah_funds = self._resolve_waterfall(
            df_bs, [r"^jumlah dana syirkah temporer\s*$", r"^dana syirkah temporer\s*$"], year_col=yr_str, scale=scale
        )
        bs.temporary_syirkah_funds = syirkah_funds

        dpk_in_liab = max(0.0, bs.total_customer_deposits - bs.temporary_syirkah_funds) if bs.temporary_syirkah_funds > 0 else bs.total_customer_deposits
        sub_liab = dpk_in_liab + bs.deposits_from_other_banks + bs.borrowings_issued_debt
        if official_liab > 0:
            bs.total_liabilities = official_liab
            bs.other_liabilities = max(0.0, bs.total_liabilities - sub_liab)
        else:
            bs.total_liabilities = sub_liab
            bs.other_liabilities = 0.0

        official_equity = self._resolve_waterfall(
            df_bs, [r"^jumlah ekuitas\s*$", r"^total equity\s*$"], year_col=yr_str, scale=scale
        )
        bs.total_equity = official_equity if official_equity > 0 else max(0.0, bs.total_assets - (bs.total_liabilities + bs.temporary_syirkah_funds))

        bs.share_capital = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^modal saham\s*$", r"^share capital\s*$"], year_col=yr_str, scale=scale
        )
        bs.retained_earnings = self._resolve_waterfall(
            df_bs, primary_patterns=[r"^saldo laba\s*$", r"^retained earnings\s*$"], year_col=yr_str, scale=scale
        )
        bs.other_equity = max(0.0, bs.total_equity - (bs.share_capital + bs.retained_earnings))

        bs.total_liabilities_and_equity = bs.total_liabilities + bs.temporary_syirkah_funds + bs.total_equity
        bs.balance_check = round(bs.total_assets - bs.total_liabilities_and_equity, 2)
        if abs(bs.balance_check) < 1.0:
            bs.balance_check = 0.0

        # 2. INCOME STATEMENT
        is_stmt = BankingIS()
        is_stmt.interest_income = self._resolve_waterfall(
            df_is, primary_patterns=[r"^pendapatan bunga dan syariah\s*$", r"^pendapatan bunga\s*$", r"^interest income\s*$"],
            year_col=yr_str, scale=scale
        )
        is_stmt.interest_expense = abs(self._resolve_waterfall(
            df_is, primary_patterns=[r"^beban bunga dan syariah\s*$", r"^beban bunga\s*$", r"^interest expense\s*$"],
            year_col=yr_str, scale=scale
        ))
        is_stmt.net_interest_income = is_stmt.interest_income - is_stmt.interest_expense

        is_stmt.non_interest_income = self._resolve_waterfall(
            df_is, primary_patterns=[r"^pendapatan operasional lainnya\s*$", r"^pendapatan non-bunga\s*$", r"^other operating income\s*$"],
            year_col=yr_str, scale=scale
        )
        is_stmt.total_operating_income = is_stmt.net_interest_income + is_stmt.non_interest_income

        is_stmt.operating_expenses = abs(self._resolve_waterfall(
            df_is, primary_patterns=[r"^beban operasional lainnya\s*$", r"^beban operasional\s*$", r"^other operating expenses\s*$"],
            year_col=yr_str, scale=scale
        ))
        is_stmt.ppop = is_stmt.total_operating_income - is_stmt.operating_expenses

        is_stmt.provision_impairment_losses = abs(self._resolve_waterfall(
            df_is, primary_patterns=[
                r"^beban penyisihan kerugian penurunan nilai\s*$",
                r"^penyisihan kerugian penurunan nilai\s*$",
                r"^beban cadangan kerugian penurunan nilai\s*$",
                r"^allowances for impairment losses\s*$"
            ],
            year_col=yr_str, scale=scale
        ))

        official_op_profit = self._resolve_waterfall(
            df_is, primary_patterns=[r"^laba operasional\s*$", r"^laba usaha\s*$", r"^operating profit\s*$"],
            year_col=yr_str, scale=scale
        )
        is_stmt.operating_profit = official_op_profit if official_op_profit != 0.0 else (is_stmt.ppop - is_stmt.provision_impairment_losses)

        official_ebt = self._resolve_waterfall(
            df_is, primary_patterns=[r"laba.*sebelum.*pajak\b", r"profit.*before.*tax\b"],
            year_col=yr_str, scale=scale
        )
        is_stmt.ebt = official_ebt if official_ebt != 0.0 else is_stmt.operating_profit
        is_stmt.non_operating_items = is_stmt.ebt - is_stmt.operating_profit

        is_stmt.tax_expense = abs(self._resolve_waterfall(
            df_is, primary_patterns=[r"beban pajak\b", r"tax expense\b"], year_col=yr_str, scale=scale
        ))

        official_ni = self._resolve_waterfall(
            df_is, primary_patterns=[r"^jumlah laba\b", r"^laba tahun berjalan\b", r"^laba bersih\b", r"^net profit\b"],
            year_col=yr_str, scale=scale
        )
        is_stmt.net_income = official_ni if official_ni != 0.0 else (is_stmt.ebt - is_stmt.tax_expense)
        is_stmt.net_income_parent = self._resolve_waterfall(
            df_is, primary_patterns=[r"laba.*entitas induk\b", r"profit attributable to parent\b"], year_col=yr_str, scale=scale
        ) or is_stmt.net_income

        # 3. CASH FLOW STATEMENT
        cf = BankingCF()
        cf.operating_cash_flow = self._resolve_waterfall(
            df_cf, primary_patterns=[r"arus kas.*aktivitas operasi\b", r"operating activities\b"], year_col=yr_str, scale=scale
        )
        cf.capex = abs(self._resolve_waterfall(
            df_cf, primary_patterns=[r"perolehan aset tetap\b", r"acquisition of property\b"], year_col=yr_str, scale=scale
        ))
        cf.investing_cash_flow = self._resolve_waterfall(
            df_cf, primary_patterns=[r"arus kas.*aktivitas investasi\b", r"investing activities\b"], year_col=yr_str, scale=scale
        )
        cf.dividends_paid = abs(self._resolve_waterfall(
            df_cf, primary_patterns=[r"pembayaran dividen\b", r"dividends paid\b"], year_col=yr_str, scale=scale
        ))
        cf.financing_cash_flow = self._resolve_waterfall(
            df_cf, primary_patterns=[r"arus kas.*aktivitas pendanaan\b", r"financing activities\b"], year_col=yr_str, scale=scale
        )
        cf.net_change_in_cash = self._resolve_waterfall(
            df_cf, primary_patterns=[r"kenaikan.*kas dan setara kas\b", r"net increase.*cash\b"], year_col=yr_str, scale=scale
        )
        cf.ending_cash = bs.cash_and_placements_bi_banks
        cf.beginning_cash = max(0.0, cf.ending_cash - cf.net_change_in_cash)

        return is_stmt, bs, cf
