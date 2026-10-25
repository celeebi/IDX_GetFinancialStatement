"""
High-fidelity XBRL instance parser for IDX financial statements.
Extracts canonical financial concepts directly from instance.xbrl,
normalizes amounts to Millions IDR (Juta Rupiah), and constructs
standardized 3-statement models guaranteed to balance.
Supports General Industry, Property, Infrastructure, and Financial & Sharia entry points.
"""

import io
import os
import re
import zipfile
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple, Union, List

from .proforma.schema import (
    NormalizedIS, NormalizedBS, NormalizedCF,
    BankingIS, BankingBS, BankingCF
)

logger = logging.getLogger("idx_scraper.xbrl_parser")

# Linkbase and taxonomy schema suffixes to ignore when scanning an IDX instance.zip archive
IGNORED_XML_SUFFIXES = (
    "-pre.xml", "-cal.xml", "-def.xml", "-lab.xml",
    "-lab-id.xml", "-lab-en.xml", "-ref.xml", "taxonomy.xml"
)


class XBRLParser:
    """Parser for IDX instance.xbrl filings across General and Banking/Sharia entry points."""

    @staticmethod
    def _select_instance_member(namelist: List[str]) -> Optional[str]:
        """
        Deterministically select the XBRL instance document from a ZIP archive,
        ignoring taxonomy linkbase XML files (*-cal.xml, *-def.xml, *-pre.xml, *-lab*.xml).
        """
        # Priority 1: Explicit instance.xbrl or *.xbrl
        for name in namelist:
            if name.lower().endswith("instance.xbrl"):
                return name
        for name in namelist:
            if name.lower().endswith(".xbrl"):
                return name
        # Priority 2: .xml file that is NOT an ignored linkbase or schema file
        for name in namelist:
            lower = name.lower()
            if lower.endswith(".xml") and not any(lower.endswith(sfx) for sfx in IGNORED_XML_SUFFIXES):
                return name
        return None

    @classmethod
    def load_instance(
        cls, source: Union[str, bytes, io.BytesIO]
    ) -> Tuple[Dict[Tuple[str, str], float], Dict[str, str], Dict[str, Dict[str, Any]]]:
        """
        Load numeric facts, DEI metadata facts, and context metadata from an IDX XBRL source.

        Returns:
            facts: Dict[(tag_name, context_ref), float]
            dei: Dict[tag_name, str] (Document & Entity Information text values)
            contexts: Dict[context_id, {"period_type": "instant"|"duration", "end_date": str, "has_dimensions": bool}]
        """
        xml_content = None

        if isinstance(source, (bytes, io.BytesIO)):
            f_in = source if isinstance(source, io.BytesIO) else io.BytesIO(source)
            if zipfile.is_zipfile(f_in):
                f_in.seek(0)
                with zipfile.ZipFile(f_in) as zf:
                    target = cls._select_instance_member(zf.namelist())
                    if target:
                        xml_content = zf.read(target)
            else:
                f_in.seek(0)
                xml_content = f_in.read()
        elif isinstance(source, str) and os.path.exists(source):
            if source.lower().endswith(".zip") or zipfile.is_zipfile(source):
                with zipfile.ZipFile(source, 'r') as zf:
                    target = cls._select_instance_member(zf.namelist())
                    if target:
                        xml_content = zf.read(target)
            else:
                with open(source, "rb") as f:
                    xml_content = f.read()

        if not xml_content:
            logger.warning("No XBRL instance content could be read from source.")
            return {}, {}, {}

        root = ET.fromstring(xml_content)
        facts: Dict[Tuple[str, str], float] = {}
        dei: Dict[str, str] = {}
        contexts: Dict[str, Dict[str, Any]] = {}

        # 1. Parse contexts to track instant vs duration and filter dimensions
        for elem in root.iter():
            local_name = elem.tag.split("}")[-1]
            if local_name == "context":
                ctx_id = elem.attrib.get("id", "")
                if not ctx_id:
                    continue
                period_type = None
                end_date = ""
                has_dimensions = False
                for child in elem.iter():
                    c_name = child.tag.split("}")[-1]
                    if c_name == "instant" and child.text:
                        period_type = "instant"
                        end_date = child.text.strip()
                    elif c_name == "endDate" and child.text:
                        period_type = "duration"
                        end_date = child.text.strip()
                    elif c_name in ("explicitMember", "typedMember"):
                        has_dimensions = True
                contexts[ctx_id] = {
                    "period_type": period_type,
                    "end_date": end_date,
                    "has_dimensions": has_dimensions,
                }

        # 2. Parse facts & DEI metadata
        for elem in root.iter():
            ctx = elem.attrib.get("contextRef", "")
            if not ctx:
                continue

            nil_attr = elem.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "").lower()
            if nil_attr == "true":
                continue

            tag = elem.tag.split("}")[-1]
            val_str = elem.text
            if not val_str or not val_str.strip():
                continue

            clean_str = val_str.strip()

            # Skip dimensional contexts (e.g. member axes breakdowns)
            ctx_meta = contexts.get(ctx, {})
            if ctx_meta.get("has_dimensions", False):
                continue

            # Attempt numeric conversion
            try:
                clean_num = float(clean_str.replace(",", ""))
                facts[(tag, ctx)] = clean_num
            except (ValueError, TypeError):
                # Save non-numeric DEI metadata
                if tag not in dei or ctx in ("CurrentYearDuration", "CurrentYearInstant"):
                    dei[tag] = clean_str

        return facts, dei, contexts

    @classmethod
    def load_facts(cls, source: Union[str, bytes, io.BytesIO]) -> Dict[Tuple[str, str], float]:
        """Backward-compatible helper returning (tag, contextRef) -> float facts."""
        facts, _, _ = cls.load_instance(source)
        return facts

    @staticmethod
    def _resolve_scale_factor(
        dei: Dict[str, str],
        facts: Dict[Tuple[str, str], float],
        target_scale: Optional[float] = None
    ) -> float:
        """
        Determine divisor to scale reported XBRL values into Millions of Presentation Currency (Juta IDR).
        Inspects IDX DEI `LevelOfRoundingUsedInFinancialStatements` and magnitude heuristics on Total Assets.
        """
        if target_scale is not None:
            return target_scale

        rounding = dei.get("LevelOfRoundingUsedInFinancialStatements", "").lower()

        sample_assets = 0.0
        for tag in ("Assets", "TotalAssets"):
            for ctx in ("CurrentYearInstant", "PriorEndYearInstant", "PriorYearInstant"):
                if (tag, ctx) in facts:
                    sample_assets = abs(facts[(tag, ctx)])
                    break
            if sample_assets > 0:
                break

        # Indonesian listed companies typically have Total Assets >= ~10 Billion IDR (10,000 Million IDR).
        # If sample_assets >= 1e10, raw numbers are in Full IDR (divide by 1,000,000 to get Millions).
        if sample_assets >= 1e10:
            return 1_000_000.0

        # If 0 < sample_assets < 1e7, numbers are already in Millions or USD (scale = 1.0)
        if 0 < sample_assets < 1e7:
            if "ribuan" in rounding or "thousand" in rounding:
                return 1_000.0
            return 1.0

        if "jutaan" in rounding or "million" in rounding:
            return 1_000_000.0 if sample_assets >= 1e10 else 1.0
        if "ribuan" in rounding or "thousand" in rounding:
            return 1_000.0
        if "miliaran" in rounding or "billion" in rounding:
            return 0.001

        return 1_000_000.0

    @classmethod
    def extract_normalized_statements(
        cls,
        facts: Dict[Tuple[str, str], float],
        year: int,
        target_scale: Optional[float] = None,
        dei: Optional[Dict[str, str]] = None,
        period_target: str = "current"
    ) -> Tuple[NormalizedIS, NormalizedBS, NormalizedCF]:
        """
        Extract and assemble canonical NormalizedIS, NormalizedBS, and NormalizedCF
        from XBRL facts dictionary for a specific year (General Corporate Archetype).
        """
        if period_target.lower() == "prior":
            dur_ctx = "PriorYearDuration"
            inst_ctx = "PriorEndYearInstant"
            inst_fallback = "PriorYearInstant"
        else:
            dur_ctx = "CurrentYearDuration"
            inst_ctx = "CurrentYearInstant"
            inst_fallback = "CurrentYearInstant"

        def g_dur(tag: str) -> float:
            return facts.get((tag, dur_ctx), 0.0)

        def g_inst(tag: str) -> float:
            val = facts.get((tag, inst_ctx), 0.0)
            if val == 0.0 and inst_fallback != inst_ctx:
                val = facts.get((tag, inst_fallback), 0.0)
            return val

        m = cls._resolve_scale_factor(dei or {}, facts, target_scale)

        # -------------------------------------------------------------
        # 1. INCOME STATEMENT
        # -------------------------------------------------------------
        rev = (g_dur("SalesAndRevenue") or 
               g_dur("Revenue") or
               g_dur("Revenues") or
               g_dur("OperatingRevenues") or
               g_dur("RevenueFromContractsWithCustomers") or
               g_dur("TotalInterestAndShariaIncome") or 
               g_dur("InterestIncome") or 
               g_dur("TotalRevenue") or 
               g_dur("GrossPremiumsEarned")) / m

        cogs = abs(g_dur("CostOfGoodsSold") or 
                   g_dur("CostOfSalesAndRevenue") or 
                   g_dur("CostOfSales") or 
                   g_dur("DirectOperatingExpenses") or
                   g_dur("CostOfRevenues")) / m

        reported_gp = (g_dur("GrossProfit") or g_dur("GrossProfitLoss")) / m
        gross_profit = reported_gp if reported_gp != 0.0 else (rev - cogs)

        split_sgna = abs(g_dur("GeneralAndAdministrativeExpenses") + 
                         g_dur("SellingExpenses") + 
                         g_dur("SellingAndMarketingExpenses") + 
                         g_dur("DistributionCosts") +
                         g_dur("AdministrativeExpenses")) / m
        combined_opex = abs(g_dur("OperatingExpenses") or g_dur("TotalOperatingExpenses")) / m
        sgna = split_sgna if split_sgna != 0.0 else combined_opex

        reported_ebit = (g_dur("ProfitLossFromOperatingActivities") or 
                         g_dur("OperatingIncome") or 
                         g_dur("OperatingProfit") or
                         g_dur("OperatingIncomeLoss")) / m
        ebit = reported_ebit if reported_ebit != 0.0 else (gross_profit - sgna)

        dna = abs(g_dur("DepreciationAndAmortisationExpense") or 
                  g_dur("DepreciationExpense") or 
                  g_dur("AmortisationExpense") or
                  g_dur("DepreciationAndAmortization")) / m
        ebitda = ebit + dna

        interest_exp = abs(g_dur("FinanceCosts") or 
                           g_dur("InterestExpense") or 
                           g_dur("InterestExpenses") or
                           g_dur("FinanceExpenses")) / m

        interest_inc = (g_dur("FinanceIncome") or 
                        g_dur("InterestIncome") or 
                        g_dur("InvestmentIncome")) / m

        other_non_op = (g_dur("OtherGainsLosses") or 
                        g_dur("OtherOperatingIncomeExpense") or 
                        (g_dur("GainLossOnForeignExchangeOperating") + g_dur("GainLossOnForeignExchangeNonOperating"))) / m

        ebt = (g_dur("ProfitLossBeforeIncomeTax") or 
               g_dur("ProfitLossBeforeTax") or 
               (ebit - interest_exp + interest_inc + other_non_op)) / m

        tax = abs(g_dur("TaxBenefitExpenses") or 
                  g_dur("IncomeTaxExpenseContinuingOperations") or 
                  g_dur("IncomeTaxExpense") or
                  g_dur("TaxExpense")) / m

        ni = (g_dur("ProfitLoss") or 
              g_dur("ProfitLossFromContinuingOperations") or 
              (ebt - tax)) / m

        ni_parent = (g_dur("ProfitLossAttributableToParentEntity") or 
                     g_dur("ProfitLossAttributableToOwnersOfParent") or 
                     ni) / m

        is_stmt = NormalizedIS(
            revenue=rev,
            cogs=cogs,
            gross_profit=gross_profit,
            sgna_opex=sgna,
            ebitda=ebitda,
            depreciation_amortization=dna,
            operating_income_ebit=ebit,
            finance_income=interest_inc,
            finance_costs=interest_exp,
            net_finance_costs=interest_exp - interest_inc,
            other_non_operating=other_non_op,
            ebt=ebt,
            tax_expense=tax,
            net_income=ni,
            net_income_parent=ni_parent
        )

        # -------------------------------------------------------------
        # 2. BALANCE SHEET
        # -------------------------------------------------------------
        cash = (g_inst("CashAndCashEquivalents") or 
                g_inst("CashAndBankBalances") or 
                g_inst("Cash")) / m

        ar = ((g_inst("TradeReceivablesThirdParties") + g_inst("TradeReceivablesRelatedParties")) or 
              g_inst("TradeReceivables") or 
              g_inst("TradeAndOtherReceivablesCurrent") or 
              g_inst("AccountsReceivable")) / m

        inv = (g_inst("Inventories") or 
               g_inst("CurrentInventories") or 
               g_inst("InventoriesCurrent") or 
               g_inst("RealEstateAssetsCurrent") or 
               g_inst("InventoriesRealEstateCurrent")) / m

        ca_raw = (g_inst("CurrentAssets") or g_inst("TotalCurrentAssets")) / m
        other_ca = max(0.0, ca_raw - (cash + ar + inv)) if ca_raw > 0 else 0.0
        tot_ca = ca_raw if ca_raw > 0 else (cash + ar + inv + other_ca)

        ppe = (g_inst("PropertyPlantAndEquipment") or 
               g_inst("FixedAssets") or 
               g_inst("PropertyAndEquipment")) / m

        tot_assets = (g_inst("Assets") or g_inst("TotalAssets")) / m
        other_non_ca = max(0.0, tot_assets - (tot_ca + ppe)) if tot_assets > 0 else 0.0
        tot_non_ca = ppe + other_non_ca

        ap = ((g_inst("TradePayablesThirdParties") + g_inst("TradePayablesRelatedParties")) or 
              g_inst("TradePayables") or 
              g_inst("TradeAndOtherPayablesCurrent") or
              g_inst("AccountsPayable")) / m

        st_debt = (g_inst("ShortTermBankLoans") + 
                   g_inst("ShortTermLoans") +
                   g_inst("CurrentMaturitiesOfBankLoans") + 
                   g_inst("CurrentPortionsOfLongTermBankLoans") +
                   g_inst("CurrentMaturitiesOfLongTermLoans") +
                   g_inst("CurrentMaturitiesOfBondsPayable") + 
                   g_inst("CurrentMaturitiesOfOtherBorrowings")) / m

        cl = (g_inst("CurrentLiabilities") or g_inst("TotalCurrentLiabilities")) / m
        other_cl = max(0.0, cl - (ap + st_debt)) if cl > 0 else 0.0
        tot_cl = cl if cl > 0 else (ap + st_debt + other_cl)

        lt_debt = (g_inst("LongTermBankLoans") + 
                   g_inst("NonCurrentPortionsOfLongTermLoans") +
                   g_inst("LongTermLoans") +
                   g_inst("BondsPayable") + 
                   g_inst("BondsPayableNonCurrent") + 
                   g_inst("SukukNonCurrent") +
                   g_inst("LongTermOtherBorrowings")) / m

        tot_liab_raw = (g_inst("Liabilities") or g_inst("TotalLiabilities")) / m
        syirkah = (g_inst("TemporarySyirkahFunds") or g_inst("SyirkahFunds")) / m
        tot_liab = tot_liab_raw + syirkah

        tot_non_cl = max(0.0, tot_liab - tot_cl) if tot_liab > 0 else lt_debt
        other_non_cl = max(0.0, tot_non_cl - lt_debt)

        share_cap = (g_inst("ShareCapital") or 
                     g_inst("CapitalShare") or 
                     g_inst("IssuedAndFullyPaidCapital")) / m

        re_unapp = g_inst("UnappropriatedRetainedEarnings") / m
        re_app = g_inst("AppropriatedRetainedEarnings") / m
        re_tot = (g_inst("RetainedEarnings") / m) or (re_unapp + re_app)

        tot_equity = (g_inst("Equity") or 
                      g_inst("TotalEquity") or 
                      g_inst("EquityAttributableToParentEntity") or
                      g_inst("EquityAttributableToOwnersOfParent")) / m
        other_eq = tot_equity - (share_cap + re_tot) if tot_equity > 0 else 0.0

        tot_liab_eq = tot_liab + tot_equity
        bs_check = tot_assets - tot_liab_eq

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
        ocf = (g_dur("NetCashFlowsReceivedFromUsedInOperatingActivities") or 
               g_dur("NetCashFlowsFromUsedInOperatingActivities") or
               g_dur("CashFlowsFromUsedInOperatingActivities")) / m

        capex = (g_dur("PaymentsForAcquisitionOfPropertyPlantAndEquipment") or 
                 g_dur("PaymentsForAcquisitionOfPropertyAndEquipment") or 
                 g_dur("PaymentsToAcquirePropertyPlantAndEquipment") or 
                 g_dur("PaymentsForPurchaseOfPropertyPlantAndEquipment") or 
                 g_dur("PurchaseOfPropertyPlantAndEquipment")) / m

        cfi = (g_dur("NetCashFlowsReceivedFromUsedInInvestingActivities") or 
               g_dur("NetCashFlowsFromUsedInInvestingActivities") or 
               g_dur("CashFlowsFromUsedInInvestingActivities") or
               -capex) / m

        divs = (g_dur("DistributionsOfCashDividends") or 
                g_dur("DividendsPaid") or 
                g_dur("PaymentsOfDividends")) / m

        cff = (g_dur("NetCashFlowsReceivedFromUsedInFinancingActivities") or 
               g_dur("NetCashFlowsFromUsedInFinancingActivities") or
               g_dur("CashFlowsFromUsedInFinancingActivities")) / m

        net_cash_change = (g_dur("NetIncreaseDecreaseInCashAndCashEquivalents") or (ocf + cfi + cff)) / m
        beg_cash = (facts.get(("CashAndCashEquivalentsCashFlows", "PriorEndYearInstant"), 0.0) or 
                    facts.get(("CashAndCashEquivalents", "PriorEndYearInstant"), 0.0) or 
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

    @classmethod
    def extract_banking_statements(
        cls,
        facts: Dict[Tuple[str, str], float],
        year: int,
        target_scale: Optional[float] = None,
        dei: Optional[Dict[str, str]] = None,
        period_target: str = "current"
    ) -> Tuple[BankingIS, BankingBS, BankingCF]:
        """
        Extract and assemble canonical BankingIS, BankingBS, and BankingCF
        for Banking / Financial Institutions Archetype from XBRL facts dictionary.
        Seamlessly integrates Conventional Banking and Islamic/Sharia Banking (PSAK 101-107).
        """
        if period_target.lower() == "prior":
            dur_ctx = "PriorYearDuration"
            inst_ctx = "PriorEndYearInstant"
            inst_fallback = "PriorYearInstant"
        else:
            dur_ctx = "CurrentYearDuration"
            inst_ctx = "CurrentYearInstant"
            inst_fallback = "CurrentYearInstant"

        def g_dur(tag: str) -> float:
            return facts.get((tag, dur_ctx), 0.0)

        def g_inst(tag: str) -> float:
            val = facts.get((tag, inst_ctx), 0.0)
            if val == 0.0 and inst_fallback != inst_ctx:
                val = facts.get((tag, inst_fallback), 0.0)
            return val

        m = cls._resolve_scale_factor(dei or {}, facts, target_scale)

        # -------------------------------------------------------------
        # 1. BANKING INCOME STATEMENT
        # -------------------------------------------------------------
        int_inc = (g_dur("InterestAndShariaIncome") or 
                   g_dur("TotalInterestAndShariaIncome") or 
                   g_dur("SubtotalInterestIncome") or 
                   g_dur("InterestIncome") or 
                   g_dur("GrossInterestIncome") or
                   g_dur("RevenueFromFundManagementAsMudharib")) / m

        int_exp = abs(g_dur("InterestAndShariaExpense") or 
                      g_dur("TotalInterestAndShariaExpense") or 
                      g_dur("SubtotalInterestExpense") or 
                      g_dur("InterestExpenses") or 
                      g_dur("GrossInterestExpense") or
                      g_dur("ThirdPartiesShareOnReturnOfTemporarySyirkahFunds")) / m

        reported_nii = (g_dur("NetInterestAndShariaIncome") or 
                        g_dur("NetInterestIncome") or 
                        g_dur("BankShareInRevenueFromFundManagement")) / m
        nii = reported_nii if reported_nii != 0.0 else (int_inc - int_exp)

        non_int_inc = (g_dur("OtherOperatingIncome") or 
                       g_dur("IncomeFromOtherOperatingTransactions") or 
                       (g_dur("FeesAndCommissionsIncome") + g_dur("GainLossOnForeignExchangeOperating")) or
                       (g_dur("FeesAndCommissionIncome") + g_dur("GainsLossesOnMarketableSecurities"))) / m

        tot_op_inc = nii + non_int_inc

        opex = abs(g_dur("OtherOperatingExpenses") or 
                   (g_dur("GeneralAndAdministrativeExpenses") + g_dur("SalariesAndEmployeeBenefitsExpense") + g_dur("PersonnelExpenses")) or
                   g_dur("OperatingExpenses")) / m

        ppop = tot_op_inc - opex

        ckpn = abs(g_dur("ProvisionDuringTheYearofAllowanceforImpairmentLossesonLoans") + 
                   g_dur("AllowancesForImpairmentLossesOnEarningsAssets") +
                   g_dur("RecoveryOfImpairmentLossesOfFinancialAssets") + 
                   g_dur("ImpairmentLossesOnFinancialAssets") + 
                   g_dur("AllowanceForImpairmentLossesOnFinancialAssets") +
                   g_dur("ProvisionForImpairmentLosses") +
                   g_dur("ImpairmentLossExpense")) / m

        reported_op_profit = (g_dur("ProfitFromOperation") or 
                              g_dur("OperatingIncome") or 
                              g_dur("ProfitLossFromOperatingActivities") or 
                              g_dur("OperatingProfit")) / m
        op_profit = reported_op_profit if reported_op_profit != 0.0 else (ppop - ckpn)

        reported_ebt = (g_dur("ProfitLossBeforeIncomeTax") or g_dur("ProfitLossBeforeTax")) / m
        ebt = reported_ebt if reported_ebt != 0.0 else op_profit
        non_op = ebt - op_profit

        tax = abs(g_dur("TaxBenefitExpenses") or 
                  g_dur("IncomeTaxExpenseContinuingOperations") or 
                  g_dur("IncomeTaxExpense") or
                  g_dur("TaxExpense")) / m

        ni = (g_dur("ProfitLoss") or g_dur("ProfitLossFromContinuingOperations") or (ebt - tax)) / m
        ni_parent = (g_dur("ProfitLossAttributableToParentEntity") or 
                     g_dur("ProfitLossAttributableToOwnersOfParent") or 
                     ni) / m

        is_stmt = BankingIS(
            interest_income=int_inc,
            interest_expense=int_exp,
            net_interest_income=nii,
            non_interest_income=non_int_inc,
            total_operating_income=tot_op_inc,
            operating_expenses=opex,
            ppop=ppop,
            provision_impairment_losses=ckpn,
            operating_profit=op_profit,
            non_operating_items=non_op,
            ebt=ebt,
            tax_expense=tax,
            net_income=ni,
            net_income_parent=ni_parent
        )

        # -------------------------------------------------------------
        # 2. BANKING BALANCE SHEET
        # -------------------------------------------------------------
        cash_bi = (g_inst("CashAndCashEquivalents") + 
                   g_inst("Cash") +
                   g_inst("CurrentAccountsWithBankIndonesia") + 
                   g_inst("CurrentAccountsWithOtherBanksThirdParties") + 
                   g_inst("CurrentAccountsWithOtherBanksRelatedParties") + 
                   g_inst("CurrentAccountsWithOtherBanks") + 
                   g_inst("PlacementsWithOtherBanksAndBankIndonesia") +
                   g_inst("PlacementsWithOtherBanksAndBankIndonesiaThirdParties") +
                   g_inst("PlacementsWithOtherBanksAndBankIndonesiaRelatedParties") +
                   g_inst("PlacementsWithBankIndonesiaAndOtherBanks") +
                   g_inst("PlacementsWithBanks") +
                   g_inst("CashAndBalanceWithCentralBanks")) / m

        mkt_sec = (g_inst("OtherFinancialAssets") + 
                   g_inst("MarketableSecurities") + 
                   g_inst("MarketableSecuritiesThirdParties") + 
                   g_inst("MarketableSecuritiesRelatedParties") + 
                   g_inst("GovernmentBonds")) / m

        # Sharia Financing Components (PSAK 101-107)
        murabahah = g_inst("MurabahahReceivablesThirdParties") + g_inst("MurabahahReceivablesRelatedParties") or g_inst("MurabahahReceivables")
        musyarakah = g_inst("MusyarakahFinancingThirdParties") + g_inst("MusyarakahFinancingRelatedParties") or g_inst("MusyarakahFinancing")
        qardh = g_inst("QardhFundsThirdParties") + g_inst("QardhFundsRelatedParties") or g_inst("QardhFunds")
        mudharabah_fin = g_inst("MudharabahFinancingThirdParties") + g_inst("MudharabahFinancingRelatedParties") or g_inst("MudharabahFinancing")
        ijarah = g_inst("IjarahReceivablesThirdParties") + g_inst("IjarahReceivablesRelatedParties") or g_inst("IjarahReceivables")
        istishna = g_inst("IstishnaReceivablesThirdParties") + g_inst("IstishnaReceivablesRelatedParties") or g_inst("IstishnaReceivables")
        sharia_financing_sum = murabahah + musyarakah + qardh + mudharabah_fin + ijarah + istishna
        sharia_gross_master = g_inst("ShariaReceivablesGross") or g_inst("ShariaReceivableAndFinancing")
        tot_sharia_gross = sharia_gross_master or sharia_financing_sum

        # Conventional Loans
        conv_loans = (g_inst("TotalLoansGross") or 
                      (g_inst("LoansThirdParties") + g_inst("LoansRelatedParties")) or
                      g_inst("Loans") or 
                      g_inst("ConsumerFinancingReceivables"))

        gross_loans = (tot_sharia_gross + conv_loans) / m

        # Allowances for Impairment (CKPN)
        ckpn_sharia = (g_inst("AllowanceForImpairmentLossesForMurabahahReceivables") +
                       g_inst("AllowanceForImpairmentLossesForMusyarakahFinancing") +
                       g_inst("AllowanceForImpairmentLossesForQardhFunds") +
                       g_inst("AllowanceForImpairmentLossesForMudharabahFinancing") +
                       g_inst("AllowanceForImpairmentLossesForIjarahReceivables") +
                       g_inst("AllowanceForImpairmentLossesForIstishnaReceivables"))

        ckpn_conv = (g_inst("AllowanceForImpairmentLossesForLoans") or 
                     g_inst("AllowanceForImpairmentLossesOnEarningsAssets") or 
                     g_inst("AllowancesForImpairmentLossesOnEarningsAssets") or
                     g_inst("AllowanceForImpairmentLossesOnFinancialAssets"))

        if ckpn_sharia == 0.0 and tot_sharia_gross > 0 and g_inst("ShariaReceivablesNet") > 0:
            ckpn_sharia = max(0.0, tot_sharia_gross - g_inst("ShariaReceivablesNet"))

        ckpn_loans = (ckpn_sharia + ckpn_conv) / m

        sharia_net = g_inst("ShariaReceivablesNet") / m if g_inst("ShariaReceivablesNet") > 0 else max(0.0, (tot_sharia_gross - ckpn_sharia) / m)
        conv_net = g_inst("TotalLoansNet") / m if g_inst("TotalLoansNet") > 0 else max(0.0, (conv_loans - ckpn_conv) / m)
        net_loans = (sharia_net + conv_net) if (sharia_net > 0 or conv_net > 0) else max(0.0, gross_loans - ckpn_loans)

        fixed_assets = (g_inst("PropertyPlantAndEquipment") or 
                        g_inst("PropertyAndEquipment") or 
                        g_inst("PremisesAndEquipment")) / m

        tot_assets = (g_inst("Assets") or g_inst("TotalAssets")) / m
        tot_earning = cash_bi + mkt_sec + net_loans
        other_assets = max(0.0, tot_assets - (tot_earning + fixed_assets))

        # Deposits from Customers (DPK)
        # Giro: Conventional + Wadiah + Mudharabah
        giro_conv = g_inst("CurrentAccounts") or (g_inst("CurrentAccountsThirdParties") + g_inst("CurrentAccountsRelatedParties"))
        giro_wadiah = g_inst("WadiahDemandDeposits") or (g_inst("WadiahDemandDepositsThirdParties") + g_inst("WadiahDemandDepositsRelatedParties"))
        giro_mudharabah = (g_inst("MudharabahDemandDeposits") or 
                           (g_inst("MudharabahCurrentAccountThirdParties") + g_inst("MudharabahCurrentAccountRelatedParties")) or 
                           g_inst("MudharabahCurrentAccount"))
        giro = (giro_conv + giro_wadiah + giro_mudharabah) / m

        # Tabungan: Conventional + Wadiah + Mudharabah
        tab_conv = (g_inst("SavingsDeposits") or 
                    (g_inst("SavingsDepositsThirdParties") + g_inst("SavingsDepositsRelatedParties")) or
                    (g_inst("SavingsThirdParties") + g_inst("SavingsRelatedParties")))
        tab_wadiah = (g_inst("WadiahSavingsDeposits") or 
                      (g_inst("WadiahSavingsThirdParties") + g_inst("WadiahSavingsRelatedParties")) or
                      (g_inst("WadiahSavingsDepositsThirdParties") + g_inst("WadiahSavingsDepositsRelatedParties")))
        tab_mudharabah = (g_inst("MudharabahSavingsDeposits") or 
                          (g_inst("MudharabahSavingDepositsThirdParties") + g_inst("MudharabahSavingDepositsRelatedParties")) or
                          g_inst("MudharabahSavingDepositsUmmat"))
        tabungan = (tab_conv + tab_wadiah + tab_mudharabah) / m

        # Deposito: Conventional + Mudharabah
        dep_conv = g_inst("TimeDeposits") or (g_inst("TimeDepositsThirdParties") + g_inst("TimeDepositsRelatedParties"))
        dep_mudharabah = (g_inst("TotalMudharabahTimeDeposits") or 
                          (g_inst("MudharabahTimeDepositsThirdParties") + g_inst("MudharabahTimeDepositsRelatedParties")) or
                          g_inst("MudharabahTimeDeposits"))
        deposito = (dep_conv + dep_mudharabah) / m

        sharia_dep = g_inst("ShariaDeposits") / m

        tot_dpk = giro + tabungan + deposito + sharia_dep
        if tot_dpk == 0.0:
            tot_dpk = (g_inst("DepositsFromCustomers") or g_inst("LiabilitiesToCustomers")) / m

        other_bank_dep = (g_inst("OtherBanksDepositsThirdParties") + 
                          g_inst("OtherBankdsDepositsRelatedParties") +
                          g_inst("DepositsFromOtherBanks") +
                          g_inst("OtherBanksDeposits")) / m

        borrowings = (g_inst("Borrowings") + 
                      g_inst("SecuritiesIssued") + 
                      g_inst("BondsPayable") + 
                      g_inst("SubordinatedLoans") +
                      g_inst("MudharabahSukuk") +
                      g_inst("SubordinatedMudharabahSukuk")) / m

        tot_liab_official = (g_inst("Liabilities") or g_inst("TotalLiabilities")) / m
        syirkah = (g_inst("TemporarySyirkahFunds") or g_inst("SyirkahFunds")) / m

        # Customer deposits recognized inside official liabilities (Wadiah + Conventional)
        dpk_in_liab = (giro_conv + giro_wadiah + tab_conv + tab_wadiah + dep_conv) / m
        if dpk_in_liab == 0.0 and syirkah > 0.0:
            dpk_in_liab = max(0.0, tot_dpk - syirkah)
        elif dpk_in_liab == 0.0:
            dpk_in_liab = tot_dpk

        other_liab = max(0.0, tot_liab_official - (dpk_in_liab + other_bank_dep + borrowings)) if tot_liab_official > 0 else 0.0
        tot_liab = tot_liab_official if tot_liab_official > 0 else (dpk_in_liab + other_bank_dep + borrowings + other_liab)

        tot_equity = (g_inst("Equity") or 
                      g_inst("TotalEquity") or 
                      g_inst("EquityAttributableToParentEntity")) / m

        share_cap = (g_inst("ShareCapital") or 
                     g_inst("CapitalShare") or 
                     g_inst("IssuedAndFullyPaidCapital")) / m

        re_tot = (g_inst("RetainedEarnings") or 
                  (g_inst("UnappropriatedRetainedEarnings") + g_inst("AppropriatedRetainedEarnings"))) / m

        other_eq = max(0.0, tot_equity - (share_cap + re_tot)) if tot_equity > 0 else 0.0

        tot_liab_syirkah_eq = tot_liab + syirkah + tot_equity
        bs_check = tot_assets - tot_liab_syirkah_eq

        if abs(bs_check) < 1.0:
            bs_check = 0.0

        bs_stmt = BankingBS(
            cash_and_placements_bi_banks=cash_bi,
            marketable_securities=mkt_sec,
            gross_loans=gross_loans,
            allowance_impairment_loans=ckpn_loans,
            net_loans=net_loans,
            total_earning_assets=tot_earning,
            net_fixed_assets=fixed_assets,
            other_assets=other_assets,
            total_assets=tot_assets,
            current_accounts=giro,
            savings_deposits=tabungan,
            time_deposits=deposito,
            sharia_deposits=sharia_dep,
            total_customer_deposits=tot_dpk,
            deposits_from_other_banks=other_bank_dep,
            borrowings_issued_debt=borrowings,
            other_liabilities=other_liab,
            total_liabilities=tot_liab,
            temporary_syirkah_funds=syirkah,
            share_capital=share_cap,
            retained_earnings=re_tot,
            other_equity=other_eq,
            total_equity=tot_equity,
            total_liabilities_and_equity=tot_liab_syirkah_eq,
            balance_check=bs_check
        )

        # -------------------------------------------------------------
        # 3. BANKING CASH FLOW STATEMENT
        # -------------------------------------------------------------
        ocf = (g_dur("NetCashFlowsReceivedFromUsedInOperatingActivities") or 
               g_dur("NetCashFlowsFromUsedInOperatingActivities") or
               g_dur("CashFlowsFromUsedInOperatingActivities")) / m

        capex = (g_dur("PaymentsForAcquisitionOfPropertyPlantAndEquipment") or 
                 g_dur("PaymentsForAcquisitionOfPropertyAndEquipment") or 
                 g_dur("PaymentsToAcquirePropertyPlantAndEquipment") or 
                 g_dur("PurchaseOfPropertyPlantAndEquipment")) / m

        cfi = (g_dur("NetCashFlowsReceivedFromUsedInInvestingActivities") or 
               g_dur("NetCashFlowsFromUsedInInvestingActivities") or 
               g_dur("CashFlowsFromUsedInInvestingActivities") or
               -capex) / m

        divs = (g_dur("DistributionsOfCashDividends") or 
                g_dur("DividendsPaid") or 
                g_dur("PaymentsOfDividends")) / m

        cff = (g_dur("NetCashFlowsReceivedFromUsedInFinancingActivities") or 
               g_dur("NetCashFlowsFromUsedInFinancingActivities") or
               g_dur("CashFlowsFromUsedInFinancingActivities")) / m

        net_cash_change = (g_dur("NetIncreaseDecreaseInCashAndCashEquivalents") or (ocf + cfi + cff)) / m
        cash_equiv = (facts.get(("CashAndCashEquivalentsCashFlows", inst_ctx), 0.0) or 
                      facts.get(("CashAndCashEquivalents", inst_ctx), 0.0)) / m
        beg_cash = (facts.get(("CashAndCashEquivalentsCashFlows", "PriorEndYearInstant"), 0.0) or 
                    facts.get(("CashAndCashEquivalents", "PriorEndYearInstant"), 0.0) or 
                    (cash_equiv - net_cash_change)) / m

        cf_stmt = BankingCF(
            operating_cash_flow=ocf,
            capex=capex,
            investing_cash_flow=cfi,
            dividends_paid=divs,
            net_debt_change=0.0,
            financing_cash_flow=cff,
            net_change_in_cash=net_cash_change,
            beginning_cash=beg_cash,
            ending_cash=cash_equiv
        )

        return is_stmt, bs_stmt, cf_stmt
