"""
Unit and Integration Tests for Dynamic Horizon Case A (Latest 5 Annual Years + Interim Quarters).
"""

import os
import shutil
import tempfile
import unittest
import openpyxl
from unittest.mock import MagicMock

from idx_scraper.year_utils import (
    period_sort_key, format_period_label, format_period_slug,
    is_annual_period, resolve_latest_filing_horizon
)
from idx_scraper.scraper import IDXFinancialScraper, inspect_file_metadata
from idx_scraper.proforma import (
    NormalizedIS, NormalizedBS, NormalizedCF, DriverCalculator,
    BankingIS, BankingBS, BankingCF, BankingDriverCalculator
)


class TestDynamicHorizon(unittest.TestCase):

    def test_period_sort_key_chronological(self):
        periods = ["2025-Q2", 2020, "2025-Q1", 2024, 2021, "2025-Q3", 2023, 2022]
        sorted_p = sorted(periods, key=period_sort_key)
        expected = [2020, 2021, 2022, 2023, 2024, "2025-Q1", "2025-Q2", "2025-Q3"]
        self.assertEqual(sorted_p, expected)

    def test_format_period_label(self):
        self.assertEqual(format_period_label(2024), "2024")
        self.assertEqual(format_period_label("2024"), "2024")
        self.assertEqual(format_period_label("2025-Q1"), "2025-Q1 (3M)")
        self.assertEqual(format_period_label("2025-Q2"), "2025-Q2 (6M)")
        self.assertEqual(format_period_label("2025-Q3"), "2025-Q3 (9M)")

    def test_format_period_slug(self):
        periods = [2020, 2021, 2022, 2023, 2024, "2025-Q2"]
        slug = format_period_slug(periods)
        self.assertEqual(slug, "2020_2024_2025Q2")

    def test_is_annual_period(self):
        self.assertTrue(is_annual_period(2024))
        self.assertTrue(is_annual_period("2024"))
        self.assertFalse(is_annual_period("2025-Q1"))
        self.assertFalse(is_annual_period("2025_tw2"))

    def test_resolve_latest_filing_horizon_case_a(self):
        """Case A: 2024 is latest annual audited report, 2025 has Q2 interim."""
        mock_api = MagicMock()
        def mock_reports(year, period, kode_emiten, **kwargs):
            if year == 2025 and period == "audit":
                return {"Results": []}
            if year == 2024 and period == "audit":
                return {"Results": [{"FilingId": "2024_aud"}]}
            if year == 2025 and period == "tw3":
                return {"Results": []}
            if year == 2025 and period == "tw2":
                return {"Results": [{"FilingId": "2025_tw2"}]}
            if year == 2025 and period == "tw1":
                return {"Results": [{"FilingId": "2025_tw1"}]}
            return {"Results": []}

        mock_api.get_financial_reports.side_effect = mock_reports

        horizon = resolve_latest_filing_horizon(mock_api, ticker="BBCA", max_annual_years=5)
        self.assertEqual(horizon["latest_annual_year"], 2024)
        self.assertEqual(horizon["annual_years"], [2020, 2021, 2022, 2023, 2024])
        self.assertEqual(len(horizon["interim_quarters"]), 2)
        self.assertEqual(horizon["interim_quarters"][0]["key"], "2025-Q1")
        self.assertEqual(horizon["interim_quarters"][1]["key"], "2025-Q2")
        self.assertEqual(
            horizon["all_periods"],
            ["2020", "2021", "2022", "2023", "2024", "2025-Q1", "2025-Q2"]
        )

    def test_resolve_latest_filing_horizon_case_b(self):
        """Case B: 2025 annual audited report is published -> takes 2021-2025 with NO interim quarters."""
        mock_api = MagicMock()
        def mock_reports(year, period, kode_emiten, **kwargs):
            if year == 2025 and period == "audit":
                return {"Results": [{"FilingId": "2025_aud"}]}
            if year == 2024 and period == "audit":
                return {"Results": [{"FilingId": "2024_aud"}]}
            return {"Results": []}

        mock_api.get_financial_reports.side_effect = mock_reports

        horizon = resolve_latest_filing_horizon(mock_api, ticker="BBCA", max_annual_years=5)
        self.assertEqual(horizon["latest_annual_year"], 2025)
        self.assertEqual(horizon["annual_years"], [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(len(horizon["interim_quarters"]), 0)
        self.assertEqual(horizon["all_periods"], ["2021", "2022", "2023", "2024", "2025"])

    def test_inspect_file_metadata_quarterly(self):
        f1 = "FinancialStatement-2025-tw2-BBRI.xlsx"
        t, y, p, ft = inspect_file_metadata(f1)
        self.assertEqual(t, "BBRI")
        self.assertEqual(y, 2025)
        self.assertEqual(p, "tw2")
        self.assertEqual(ft, "xlsx")

        f2 = "FinancialStatement-2024-Tahunan-BBRI.xlsx"
        t, y, p, ft = inspect_file_metadata(f2)
        self.assertEqual(t, "BBRI")
        self.assertEqual(y, 2024)
        self.assertEqual(p, "audit")
        self.assertEqual(ft, "xlsx")

    def test_driver_benchmarks_strictly_annual(self):
        """Verify benchmarks ignore interim quarters so baseline isn't distorted."""
        periods = [2022, 2023, 2024, "2025-Q2"]
        is_dict = {}
        bs_dict = {}
        cf_dict = {}

        # 2022 (annual)
        is_22 = NormalizedIS(revenue=100.0, gross_profit=40.0, operating_income_ebit=20.0, net_income=15.0)
        bs_22 = NormalizedBS(accounts_receivable=10.0, inventories=15.0, accounts_payable=8.0)
        cf_22 = NormalizedCF(capex=5.0)
        is_dict[2022], bs_dict[2022], cf_dict[2022] = is_22, bs_22, cf_22

        # 2023 (annual)
        is_23 = NormalizedIS(revenue=110.0, gross_profit=44.0, operating_income_ebit=22.0, net_income=16.5)
        bs_23 = NormalizedBS(accounts_receivable=11.0, inventories=16.5, accounts_payable=8.8)
        cf_23 = NormalizedCF(capex=5.5)
        is_dict[2023], bs_dict[2023], cf_dict[2023] = is_23, bs_23, cf_23

        # 2024 (annual)
        is_24 = NormalizedIS(revenue=120.0, gross_profit=48.0, operating_income_ebit=24.0, net_income=18.0)
        bs_24 = NormalizedBS(accounts_receivable=12.0, inventories=18.0, accounts_payable=9.6)
        cf_24 = NormalizedCF(capex=6.0)
        is_dict[2024], bs_dict[2024], cf_dict[2024] = is_24, bs_24, cf_24

        # 2025-Q2 (interim: 6M revenue = 65.0)
        is_25q2 = NormalizedIS(revenue=65.0, gross_profit=26.0, operating_income_ebit=13.0, net_income=9.75)
        bs_25q2 = NormalizedBS(accounts_receivable=13.0, inventories=19.5, accounts_payable=10.4)
        cf_25q2 = NormalizedCF(capex=3.0)
        is_dict["2025-Q2"], bs_dict["2025-Q2"], cf_dict["2025-Q2"] = is_25q2, bs_25q2, cf_25q2

        drivers = DriverCalculator.calculate_drivers(periods, is_dict, bs_dict, cf_dict)
        benchmarks = DriverCalculator.build_summary_benchmarks(drivers)

        # Revenue growth YoY for 2025-Q2 should be None (not comparing 6M to 12M)
        self.assertIsNone(drivers["2025-Q2"].revenue_growth_yoy)
        # Margin should be calculated
        self.assertAlmostEqual(drivers["2025-Q2"].gross_margin_pct, 0.40, places=2)

        # 3-Year Median and 5-Year Average should be computed exclusively from 2022, 2023, 2024
        # Gross margin across 22, 23, 24 is 0.40
        self.assertAlmostEqual(benchmarks["3_Year_Median"]["Gross Margin (%)"], 0.40, places=2)
        self.assertAlmostEqual(benchmarks["5_Year_Average"]["Gross Margin (%)"], 0.40, places=2)


if __name__ == "__main__":
    unittest.main()
