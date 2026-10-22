"""
Typed API wrappers for IDX primary endpoints.
"""

from typing import List, Dict, Any, Optional
import logging
from .client import IDXClient

logger = logging.getLogger("idx_scraper.api")


class IDXApi:
    """Wrapper for IDX REST endpoints."""

    def __init__(self, client: Optional[IDXClient] = None):
        self.client = client or IDXClient()
        self._cached_emitens: Optional[List[Dict[str, str]]] = None

    def get_emitens(self, emiten_type: str = "s", force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Fetch universe of listed companies.
        emiten_type: 's' for stocks (saham), 'o' for bonds (obligasi), '*' for all.
        """
        if self._cached_emitens is not None and not force_refresh:
            return self._cached_emitens

        url = "/primary/Helper/GetEmiten"
        params = {"emitenType": emiten_type}
        resp = self.client.get(url, params=params)
        data = resp.json()
        self._cached_emitens = data
        return data

    def search_emiten(self, keyword: str) -> List[Dict[str, str]]:
        """Find companies by ticker code or company name."""
        keyword = keyword.strip().upper()
        emitens = self.get_emitens()
        return [
            e for e in emitens
            if keyword in e.get("KodeEmiten", "").upper() or keyword in e.get("NamaEmiten", "").upper()
        ]

    def get_financial_reports(
        self,
        year: int,
        period: str = "audit",
        kode_emiten: Optional[str] = None,
        report_type: str = "rdf",
        page: int = 1,
        page_size: int = 50,
        sort_column: str = "KodeEmiten",
        sort_order: str = "asc"
    ) -> Dict[str, Any]:
        """
        Query financial report filings from IDX.
        
        Args:
            year: Filing year (e.g. 2024, 2023, 2022, 2021, 2020, 2019)
            period: 'tw1', 'tw2', 'tw3', or 'audit' (Tahunan)
            kode_emiten: Stock ticker symbol (e.g. 'BBCA') or None for all
            report_type: 'rdf' (Financial Statement) or 'ar' (Annual Report)
            page: 1-based page index
            page_size: Results per page
        """
        url = "/primary/ListedCompany/GetFinancialReport"
        params = {
            "indexFrom": page,
            "pageSize": page_size,
            "year": str(year),
            "reportType": report_type,
            "EmitenType": "s",
            "SortColumn": sort_column,
            "SortOrder": sort_order,
        }
        if period:
            params["periode"] = period
        if kode_emiten:
            params["kodeEmiten"] = kode_emiten.strip().upper()

        resp = self.client.get(url, params=params)
        return resp.json()

    @staticmethod
    def find_attachment_by_type(report_item: Dict[str, Any], file_ext: str = ".xlsx", prefix: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search attachments in a report item for a specific file type (e.g., '.xlsx', '.zip', '.pdf').
        Optionally match filename prefix (e.g., 'FinancialStatement-').
        """
        attachments = report_item.get("Attachments", [])
        for att in attachments:
            fname = att.get("File_Name", "")
            ftype = att.get("File_Type", "").lower()
            if ftype == file_ext.lower() or fname.lower().endswith(file_ext.lower()):
                if prefix:
                    if fname.lower().startswith(prefix.lower()):
                        return att
                else:
                    return att
        return None

    def get_filing_history(
        self,
        kode_emiten: str,
        start_year: int,
        end_year: int,
        period: str = "audit"
    ) -> List[Dict[str, Any]]:
        """
        Query filing history for a specific ticker over a multi-year range.
        Returns a list of records containing report metadata and standardized Excel attachment details.
        """
        ticker = kode_emiten.strip().upper()
        history = []

        for year in range(start_year, end_year + 1):
            try:
                data = self.get_financial_reports(year=year, period=period, kode_emiten=ticker, page=1, page_size=5)
                results = data.get("Results", [])
                if results:
                    report = results[0]
                    xlsx_att = self.find_attachment_by_type(report, file_ext=".xlsx", prefix="FinancialStatement")
                    if not xlsx_att:
                        # Fallback to any xlsx attachment
                        xlsx_att = self.find_attachment_by_type(report, file_ext=".xlsx")

                    zip_att = self.find_attachment_by_type(report, file_ext=".zip", prefix="instance")
                    if not zip_att:
                        zip_att = self.find_attachment_by_type(report, file_ext=".zip")

                    record = {
                        "ticker": ticker,
                        "company_name": report.get("NamaEmiten"),
                        "year": year,
                        "period": report.get("Report_Period", period),
                        "file_modified": report.get("File_Modified"),
                        "attachment": xlsx_att,
                        "zip_attachment": zip_att,
                        "all_attachments": report.get("Attachments", [])
                    }
                    history.append(record)
                else:
                    logger.info(f"No filing found for {ticker} in year {year} ({period}).")
            except Exception as e:
                logger.error(f"Error querying {ticker} year {year}: {e}")

        return history
