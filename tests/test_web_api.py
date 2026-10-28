"""
Unit and Integration Tests for Web UI and API Endpoints.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from web_app import app
from idx_scraper.proforma import (
    NormalizedIS, NormalizedBS, NormalizedCF, OperationalDrivers
)


class TestWebAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["author"], "abas YP74A")

    def test_index_page_rendered(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("Financial Statement & Modeling Engine", resp.text)
        self.assertIn("abas YP74A", resp.text)

    def test_scrape_empty_ticker(self):
        resp = self.client.post("/api/scrape", json={"ticker": ""})
        self.assertEqual(resp.status_code, 400)

    @patch("web_app.IDXFinancialScraper")
    def test_scrape_mock_success(self, MockScraperClass):
        mock_scraper = MagicMock()
        MockScraperClass.return_value = mock_scraper

        # Setup mock model result
        years = [2022, 2023, "2024-Q2"]
        mock_res = {
            "ticker": "TEST",
            "status": "success",
            "archetype": "corporate",
            "years": years,
            "ready_excel": "downloads/TEST/TEST_ReadyToForecast_Financials_2022_2024Q2.xlsx",
            "is_dict": {
                2022: NormalizedIS(revenue=100.0, gross_profit=40.0, operating_income_ebit=20.0, net_income=15.0),
                2023: NormalizedIS(revenue=110.0, gross_profit=44.0, operating_income_ebit=22.0, net_income=16.5),
                "2024-Q2": NormalizedIS(revenue=60.0, gross_profit=24.0, operating_income_ebit=12.0, net_income=9.0)
            },
            "bs_dict": {
                2022: NormalizedBS(total_assets=200.0, total_liabilities=100.0, total_equity=100.0, balance_check=0.0),
                2023: NormalizedBS(total_assets=220.0, total_liabilities=110.0, total_equity=110.0, balance_check=0.0),
                "2024-Q2": NormalizedBS(total_assets=240.0, total_liabilities=120.0, total_equity=120.0, balance_check=0.0)
            },
            "cf_dict": {
                2022: NormalizedCF(capex=5.0),
                2023: NormalizedCF(capex=6.0),
                "2024-Q2": NormalizedCF(capex=3.0)
            },
            "drivers_by_year": {
                2022: OperationalDrivers(),
                2023: OperationalDrivers(),
                "2024-Q2": OperationalDrivers()
            },
            "benchmarks": {
                "3_Year_Median": {"Gross Margin (%)": 0.40},
                "Historical_Average": {"Gross Margin (%)": 0.40}
            },
            "general_info": {
                "Nama entitas": "PT Test Company Tbk",
                "Sektor": "Consumer Goods"
            }
        }

        mock_scraper.build_latest_ready_to_forecast.return_value = mock_res

        resp = self.client.post("/api/scrape", json={"ticker": "TEST", "mode": "latest_interim"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["ticker"], "TEST")
        self.assertEqual(data["company_name"], "PT Test Company Tbk")
        self.assertEqual(data["archetype"], "corporate")
        self.assertEqual(data["period_labels"], ["2022", "2023", "2024-Q2 (6M)"])
        self.assertIn("income_statement", data["statements"])
        self.assertIn("balance_sheet", data["statements"])
        self.assertIn("cash_flow", data["statements"])
        self.assertIn("drivers", data)
        self.assertIn("benchmarks", data)

    def test_download_nonexistent_ticker(self):
        resp = self.client.get("/api/download/NONEXISTENT999")
        self.assertEqual(resp.status_code, 404)

    def test_download_existing_ticker(self):
        # We know BRIS has ReadyToForecast files in downloads/BRIS
        resp = self.client.get("/api/download/BRIS")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        self.assertIn("ReadyToForecast", resp.headers.get("content-disposition", ""))


if __name__ == "__main__":
    unittest.main()
