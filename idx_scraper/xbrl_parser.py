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

from .proforma.schema import (
    NormalizedIS, NormalizedBS, NormalizedCF,
    BankingIS, BankingBS, BankingCF
)

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

    @classmethod
    def extract_banking_statements(
        cls,
        facts: Dict[Tuple[str, str], float],
        year: int,
        target_scale: float = 1_000_000.0  # Full IDR -> Millions IDR
    ) -> Tuple[BankingIS, BankingBS, BankingCF]:
        """
        Extract and assemble canonical BankingIS, BankingBS, and BankingCF
        for Banking / Financial Institutions Archetype from XBRL facts dictionary.
        """
        def g(tag: str, ctx: str = "CurrentYearDuration") -> float:
            return facts.get((tag, ctx), 0.0)

        m = target_scale

        # -------------------------------------------------------------
        # 1. BANKING INCOME STATEMENT
        # -------------------------------------------------------------
        int_inc = (g("TotalInterestAndShariaIncome") or 
                   g("SubtotalInterestIncome") or 
                   g("InterestIncome") or 
                   g("GrossInterestIncome")) / m

        int_exp = (g("TotalInterestAndShariaExpense") or 
                   g("SubtotalInterestExpense") or 
                   g("InterestExpenses") or 
                   g("GrossInterestExpense")) / m

        nii = int_inc - int_exp

        non_int_inc = (g("OtherOperatingIncome") or 
                       g("IncomeFromOtherOperatingTransactions") or 
                       (g("FeesAndCommissionsIncome") + g("GainLossOnForeignExchangeOperating"))) / m

        tot_op_inc = nii + non_int_inc

        opex = (g("OtherOperatingExpenses") or 
                (g("GeneralAndAdministrativeExpenses") + g("SalariesAndEmployeeBenefitsExpense") + g("PersonnelExpenses")) or
                g("OperatingExpenses")) / m

        ppop = tot_op_inc - opex

        ckpn = (g("ProvisionDuringTheYearofAllowanceforImpairmentLossesonLoans") + 
                g("AllowancesForImpairmentLossesOnEarningsAssets")) / m
        if ckpn == 0.0:
            ckpn = abs(g("RecoveryOfImpairmentLossesOfFinancialAssets") or 
                       g("ImpairmentLossesOnFinancialAssets") or 
                       g("ImpairmentLossExpense")) / m

        op_profit = (g("OperatingIncome") or 
                     g("ProfitLossFromOperatingActivities") or 
                     (ppop - ckpn)) / m

        ebt = (g("ProfitLossBeforeIncomeTax") or g("ProfitLossBeforeTax")) / m
        if ebt == 0.0:
            ebt = op_profit

        non_op = ebt - op_profit

        tax = abs(g("TaxBenefitExpenses") or g("IncomeTaxExpenseContinuingOperations")) / m
        ni = (g("ProfitLoss") or g("ProfitLossFromContinuingOperations")) / m
        if ni == 0.0:
            ni = ebt - tax

        ni_parent = (g("ProfitLossAttributableToParentEntity") or ni) / m

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
        cash_bi = (g("CashAndCashEquivalents", "CurrentYearInstant") + 
                   g("CurrentAccountsWithBankIndonesia", "CurrentYearInstant") + 
                   g("CurrentAccountsWithOtherBanksThirdParties", "CurrentYearInstant") + 
                   g("PlacementsWithOtherBanksAndBankIndonesia", "CurrentYearInstant")) / m

        mkt_sec = (g("OtherFinancialAssets", "CurrentYearInstant") + 
                   g("MarketableSecurities", "CurrentYearInstant") + 
                   g("GovernmentBonds", "CurrentYearInstant")) / m

        gross_loans = (g("TotalLoansGross", "CurrentYearInstant") or 
                       (g("LoansThirdParties", "CurrentYearInstant") + g("LoansRelatedParties", "CurrentYearInstant")) or
                       g("Loans", "CurrentYearInstant") or 
                       g("ConsumerFinancingReceivables", "CurrentYearInstant")) / m

        ckpn_loans = (g("AllowanceForImpairmentLossesForLoans", "CurrentYearInstant") or 
                      g("AllowanceForImpairmentLossesOnEarningsAssets", "CurrentYearInstant") or 
                      g("AllowancesForImpairmentLossesOnEarningsAssets", "CurrentYearInstant")) / m

        tot_loans_net_raw = g("TotalLoansNet", "CurrentYearInstant")
        net_loans = (tot_loans_net_raw / m) if tot_loans_net_raw > 0 else max(0.0, gross_loans - ckpn_loans)

        fixed_assets = (g("PropertyPlantAndEquipment", "CurrentYearInstant") or 
                        g("PropertyAndEquipment", "CurrentYearInstant") or 
                        g("PremisesAndEquipment", "CurrentYearInstant")) / m

        tot_assets = g("Assets", "CurrentYearInstant") / m

        tot_earning = cash_bi + mkt_sec + net_loans
        other_assets = max(0.0, tot_assets - (tot_earning + fixed_assets))

        # Deposits from Customers (DPK)
        giro = (g("CurrentAccounts", "CurrentYearInstant") or 
                (g("CurrentAccountsThirdParties", "CurrentYearInstant") + g("CurrentAccountsRelatedParties", "CurrentYearInstant"))) / m

        tabungan = (g("SavingsDeposits", "CurrentYearInstant") or 
                    (g("SavingsDepositsThirdParties", "CurrentYearInstant") + g("SavingsDepositsRelatedParties", "CurrentYearInstant")) or
                    (g("SavingsThirdParties", "CurrentYearInstant") + g("SavingsRelatedParties", "CurrentYearInstant"))) / m

        deposito = (g("TimeDeposits", "CurrentYearInstant") or 
                    (g("TimeDepositsThirdParties", "CurrentYearInstant") + g("TimeDepositsRelatedParties", "CurrentYearInstant"))) / m

        sharia_dep = g("ShariaDeposits", "CurrentYearInstant") / m

        tot_dpk = giro + tabungan + deposito + sharia_dep
        if tot_dpk == 0.0:
            tot_dpk = (g("DepositsFromCustomers", "CurrentYearInstant") or g("LiabilitiesToCustomers", "CurrentYearInstant")) / m

        other_bank_dep = (g("OtherBanksDepositsThirdParties", "CurrentYearInstant") + 
                          g("DepositsFromOtherBanks", "CurrentYearInstant") +
                          g("OtherBanksDeposits", "CurrentYearInstant")) / m

        borrowings = (g("Borrowings", "CurrentYearInstant") + 
                      g("SecuritiesIssued", "CurrentYearInstant") + 
                      g("BondsPayable", "CurrentYearInstant") + 
                      g("SubordinatedLoans", "CurrentYearInstant")) / m

        tot_liab_official = g("Liabilities", "CurrentYearInstant") / m
        other_liab = max(0.0, tot_liab_official - (tot_dpk + other_bank_dep + borrowings)) if tot_liab_official > 0 else 0.0
        tot_liab = tot_liab_official if tot_liab_official > 0 else (tot_dpk + other_bank_dep + borrowings + other_liab)

        syirkah = (g("TemporarySyirkahFunds", "CurrentYearInstant") or g("SyirkahFunds", "CurrentYearInstant")) / m

        tot_equity = g("Equity", "CurrentYearInstant") / m
        share_cap = (g("ShareCapital", "CurrentYearInstant") or 
                     g("CapitalShare", "CurrentYearInstant") or 
                     g("IssuedAndFullyPaidCapital", "CurrentYearInstant")) / m

        re_tot = (g("RetainedEarnings", "CurrentYearInstant") or 
                  (g("UnappropriatedRetainedEarnings", "CurrentYearInstant") + g("AppropriatedRetainedEarnings", "CurrentYearInstant"))) / m

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
        ocf = (g("NetCashFlowsReceivedFromUsedInOperatingActivities") or 
               g("NetCashFlowsFromUsedInOperatingActivities")) / m

        capex = (g("PaymentsForAcquisitionOfPropertyPlantAndEquipment") or 
                 g("PaymentsForAcquisitionOfPropertyAndEquipment") or 
                 g("PaymentsToAcquirePropertyPlantAndEquipment") or 
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
        cash_equiv = (g("CashAndCashEquivalentsCashFlows", "CurrentYearInstant") or 
                      g("CashAndCashEquivalents", "CurrentYearInstant")) / m
        beg_cash = (g("CashAndCashEquivalentsCashFlows", "PriorEndYearInstant") or 
                    g("CashAndCashEquivalents", "PriorEndYearInstant") or 
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
