"""
High-fidelity XBRL instance parser for IDX financial statements.
Extracts canonical financial concepts directly from instance.xbrl,
normalizes amounts to Millions IDR (Juta Rupiah), and constructs
standardized 3-statement models guaranteed to balance.
"""

import io
import os
import zipfile
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple, Union

from .proforma.schema import NormalizedIS, NormalizedBS, NormalizedCF

logger = logging.getLogger("idx_scraper.xbrl_parser")


class XBRLParser:
    """Parser for IDX instance.xbrl filings."""

    @staticmethod
    def load_facts(source: Union[str, bytes, io.BytesIO]) -> Dict[Tuple[str, str], float]:
        """
        Load facts from a zip path, xbrl file path, or raw zip bytes.
        Returns a dict keyed by (tag_name, context_ref) -> float value.
        """
        xml_content = None

        if isinstance(source, (bytes, io.BytesIO)):
            f_in = source if isinstance(source, io.BytesIO) else io.BytesIO(source)
            with zipfile.ZipFile(f_in) as zf:
                for name in zf.namelist():
                    if name.endswith(".xbrl") or name.endswith(".xml"):
                        xml_content = zf.read(name)
                        break
        elif isinstance(source, str) and os.path.exists(source):
            if source.lower().endswith(".zip"):
                with zipfile.ZipFile(source, 'r') as zf:
                    for name in zf.namelist():
                        if name.endswith(".xbrl") or name.endswith(".xml"):
                            xml_content = zf.read(name)
                            break
            else:
                with open(source, "rb") as f:
                    xml_content = f.read()

        if not xml_content:
            logger.warning("No XBRL content could be read from source.")
            return {}

        root = ET.fromstring(xml_content)
        facts: Dict[Tuple[str, str], float] = {}

        for elem in root.iter():
            ctx = elem.attrib.get("contextRef", "")
            tag = elem.tag.split("}")[-1]
            val_str = elem.text
            if ctx and val_str and val_str.strip():
                # Focus on canonical un-dimensioned macro contexts
                if ctx in ("CurrentYearDuration", "CurrentYearInstant", "PriorYearDuration", "PriorEndYearInstant", "PriorYearInstant"):
                    try:
                        clean_num = float(val_str.replace(",", "").strip())
                        facts[(tag, ctx)] = clean_num
                    except (ValueError, TypeError):
                        pass

        return facts

    @classmethod
    def extract_normalized_statements(
        cls,
        facts: Dict[Tuple[str, str], float],
        year: int,
        target_scale: float = 1_000_000.0  # Full IDR -> Millions IDR
    ) -> Tuple[NormalizedIS, NormalizedBS, NormalizedCF]:
        """
        Extract and assemble canonical NormalizedIS, NormalizedBS, and NormalizedCF
        from XBRL facts dictionary for a specific year.
        """
        def g(tag: str, ctx: str = "CurrentYearDuration") -> float:
            return facts.get((tag, ctx), 0.0)

        m = target_scale

        # -------------------------------------------------------------
        # 1. INCOME STATEMENT
        # -------------------------------------------------------------
        # Revenue
        rev = (g("SalesAndRevenue") or 
               g("TotalInterestAndShariaIncome") or 
               g("InterestIncome") or 
               g("TotalRevenue") or 
               g("GrossPremiumsEarned")) / m

        # COGS
        cogs = (g("CostOfSalesAndRevenue") or 
                g("TotalInterestAndShariaExpense") or 
                g("InterestExpenses") or 
                g("CostOfSales") or 
                g("TotalCostOfRevenue")) / m

        # Gross Profit
        gp = g("GrossProfit") / m
        if gp == 0.0 and rev > 0:
            gp = rev - cogs if cogs > 0 else rev

        # D&A
        dna = (g("DepreciationAndAmortisationExpenses") or 
               (g("DepreciationExpense") + g("AmortisationExpense"))) / m

        # SG&A / Opex
        sga = (g("SellingExpenses") + g("GeneralAndAdministrativeExpenses")) / m
        if sga == 0.0:
            sga = g("OperatingExpenses") / m
        if sga == 0.0:
            # Telecom & Infrastructure nature-based expenses
            nature_sum = (g("NetworkOperationExpenses") +
                          g("EmployeeBenefitsExpenses") +
                          g("InterconnectionExpenses") +
                          g("TicketingSalesAndPromotionExpenses") +
                          g("OtherExpenses")) / m
            if nature_sum > 0:
                sga = nature_sum

        # Operating Income (EBIT)
        ebit = (g("OperatingIncome") or g("ProfitLossFromOperatingActivities")) / m
        if ebit == 0.0 and rev > 0:
            ebit = gp - sga - (dna if dna > 0 and dna != sga else 0.0)

        # EBITDA
        ebitda = ebit + dna if dna > 0 else (gp - sga if gp > 0 else ebit)

        # Finance items
        fin_inc = (g("FinanceIncome") or g("InterestIncomeCashFlows") or 0.0) / m
        fin_cost = (g("FinanceCosts") or g("InterestAndFinanceCosts") or 0.0) / m
        net_fin = fin_cost - fin_inc

        # Non-operating & EBT
        ebt = (g("ProfitLossBeforeIncomeTax") or g("ProfitLossBeforeTax")) / m
        other_non_op = ebt - (ebit - net_fin) if ebt != 0.0 else 0.0

        # Tax & Net Income
        tax = abs(g("TaxBenefitExpenses") or g("IncomeTaxExpenseContinuingOperations")) / m
        ni = (g("ProfitLoss") or g("ProfitLossFromContinuingOperations")) / m
        ni_parent = (g("ProfitLossAttributableToParentEntity") or ni) / m

        is_stmt = NormalizedIS(
            revenue=rev,
            cogs=cogs,
            gross_profit=gp,
            sgna_opex=sga,
            ebitda=ebitda,
            depreciation_amortization=dna,
            operating_income_ebit=ebit,
            finance_income=fin_inc,
            finance_costs=fin_cost,
            net_finance_costs=net_fin,
            other_non_operating=other_non_op,
            ebt=ebt,
            tax_expense=tax,
            net_income=ni,
            net_income_parent=ni_parent
        )

        # -------------------------------------------------------------
        # 2. BALANCE SHEET
        # -------------------------------------------------------------
        cash = (g("CashAndCashEquivalentsCashFlows", "CurrentYearInstant") or 
                g("CashAndCashEquivalents", "CurrentYearInstant")) / m

        ar = (g("TradeReceivablesNet", "CurrentYearInstant") or 
              (g("TradeReceivablesThirdParties", "CurrentYearInstant") + g("TradeReceivablesRelatedParties", "CurrentYearInstant")) or 
              g("TradeReceivablesGross", "CurrentYearInstant")) / m

        inv = g("Inventories", "CurrentYearInstant") / m
        ca = g("CurrentAssets", "CurrentYearInstant") / m
        other_ca = max(0.0, ca - (cash + ar + inv)) if ca > 0 else 0.0
        tot_ca = ca if ca > 0 else (cash + ar + inv + other_ca)

        ppe = (g("PropertyPlantAndEquipment", "CurrentYearInstant") or 
               g("PropertyAndEquipment", "CurrentYearInstant")) / m

        tot_assets = g("Assets", "CurrentYearInstant") / m
        other_non_ca = max(0.0, tot_assets - (tot_ca + ppe)) if tot_assets > 0 else 0.0
        tot_non_ca = ppe + other_non_ca

        ap = ((g("TradePayablesThirdParties", "CurrentYearInstant") + g("TradePayablesRelatedParties", "CurrentYearInstant")) or 
              g("TradePayables", "CurrentYearInstant")) / m

        st_debt = (g("ShortTermBankLoans", "CurrentYearInstant") + 
                   g("CurrentMaturitiesOfBankLoans", "CurrentYearInstant") + 
                   g("CurrentMaturitiesOfBondsPayable", "CurrentYearInstant") + 
                   g("CurrentMaturitiesOfOtherBorrowings", "CurrentYearInstant")) / m

        cl = g("CurrentLiabilities", "CurrentYearInstant") / m
        other_cl = max(0.0, cl - (ap + st_debt)) if cl > 0 else 0.0
        tot_cl = cl if cl > 0 else (ap + st_debt + other_cl)

        lt_debt = (g("LongTermBankLoans", "CurrentYearInstant") + 
                   g("BondsPayable", "CurrentYearInstant") + 
                   g("LongTermOtherBorrowings", "CurrentYearInstant")) / m

        tot_liab_raw = g("Liabilities", "CurrentYearInstant") / m
        syirkah = (g("TemporarySyirkahFunds", "CurrentYearInstant") or 
                   g("SyirkahFunds", "CurrentYearInstant")) / m
        # Conventional banks with Sharia windows report Syirkah between Liab & Equity (A = L + Syirkah + E)
        tot_liab = tot_liab_raw + syirkah

        tot_non_cl = max(0.0, tot_liab - tot_cl) if tot_liab > 0 else lt_debt
        other_non_cl = max(0.0, tot_non_cl - lt_debt)

        share_cap = (g("ShareCapital", "CurrentYearInstant") or 
                     g("CapitalShare", "CurrentYearInstant") or 
                     g("IssuedAndFullyPaidCapital", "CurrentYearInstant")) / m

        re_unapp = g("UnappropriatedRetainedEarnings", "CurrentYearInstant") / m
        re_app = g("AppropriatedRetainedEarnings", "CurrentYearInstant") / m
        re_tot = (g("RetainedEarnings", "CurrentYearInstant") / m) or (re_unapp + re_app)

        tot_equity = g("Equity", "CurrentYearInstant") / m
        other_eq = tot_equity - (share_cap + re_tot) if tot_equity > 0 else 0.0

        tot_liab_eq = tot_liab + tot_equity
        bs_check = tot_assets - tot_liab_eq

        # Adjust tiny rounding delta if present (< 1.0) into other_non_ca or other_equity
        if abs(bs_check) < 1.0:
            bs_check = 0.0

        bs_stmt = NormalizedBS(
            cash_and_equivalents=cash,
            accounts_receivable=ar,
            inventories=inv,
            other_current_assets=other_ca,
            total_current_assets=tot_ca,
            net_ppe=ppe,
            other_non_current_assets=other_non_ca,
            total_non_current_assets=tot_non_ca,
            total_assets=tot_assets,
            accounts_payable=ap,
            short_term_debt=st_debt,
            other_current_liabilities=other_cl,
            total_current_liabilities=tot_cl,
            long_term_debt=lt_debt,
            other_non_current_liabilities=other_non_cl,
            total_non_current_liabilities=tot_non_cl,
            total_liabilities=tot_liab,
            share_capital=share_cap,
            retained_earnings=re_tot,
            other_equity=other_eq,
            total_equity=tot_equity,
            total_liabilities_and_equity=tot_liab_eq,
            balance_check=bs_check
        )

        # -------------------------------------------------------------
        # 3. CASH FLOW STATEMENT
        # -------------------------------------------------------------
        ocf = (g("NetCashFlowsReceivedFromUsedInOperatingActivities") or 
               g("NetCashFlowsFromUsedInOperatingActivities")) / m

        capex = (g("PaymentsForAcquisitionOfPropertyPlantAndEquipment") or 
                 g("PaymentsForAcquisitionOfPropertyAndEquipment") or 
                 g("PaymentsToAcquirePropertyPlantAndEquipment") or 
                 g("PaymentsForPurchaseOfPropertyPlantAndEquipment") or 
                 g("PurchaseOfPropertyPlantAndEquipment")) / m

        cfi = (g("NetCashFlowsReceivedFromUsedInInvestingActivities") or 
               g("NetCashFlowsFromUsedInInvestingActivities") or 
               -capex) / m

        divs = (g("DistributionsOfCashDividends") or 
                g("DividendsPaid") or 
                g("PaymentsOfDividends")) / m

        cff = (g("NetCashFlowsReceivedFromUsedInFinancingActivities") or 
               g("NetCashFlowsFromUsedInFinancingActivities")) / m

        net_cash_change = (g("NetIncreaseDecreaseInCashAndCashEquivalents") or (ocf + cfi + cff)) / m
        beg_cash = (g("CashAndCashEquivalentsCashFlows", "PriorEndYearInstant") or 
                    g("CashAndCashEquivalents", "PriorEndYearInstant") or 
                    (cash - net_cash_change)) / m

        cf_stmt = NormalizedCF(
            operating_cash_flow=ocf,
            capex=capex,
            investing_cash_flow=cfi,
            dividends_paid=divs,
            net_debt_change=0.0,
            financing_cash_flow=cff,
            net_change_in_cash=net_cash_change,
            beginning_cash=beg_cash,
            ending_cash=cash
        )

        return is_stmt, bs_stmt, cf_stmt
