"""
High-level scraper coordinator for IDX financial statements.
Orchestrates API queries, file downloads, parsing, and multi-year compilation.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from .client import IDXClient
from .api import IDXApi
from .excel_parser import parse_financial_statement_file
from .xbrl_parser import XBRLParser
from .multi_year import merge_statement_tables
from .year_utils import format_year_range_slug, format_year_range_label
from .proforma import (
    FinancialNormalizer, DriverCalculator, BankingDriverCalculator,
    ReadyToForecastExporter, detect_archetype
)

logger = logging.getLogger("idx_scraper.scraper")


class IDXFinancialScraper:
    """Coordinator for scraping and compiling IDX financial statements."""

    def __init__(self, output_dir: str = "downloads", client: Optional[IDXClient] = None):
        self.output_dir = output_dir
        self.client = client or IDXClient()
        self.api = IDXApi(self.client)
        os.makedirs(self.output_dir, exist_ok=True)

    def scrape_ticker(
        self,
        ticker: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        years: Optional[List[int]] = None,
        period: str = "audit",
        parse_and_export: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape financial statements for a specific ticker across a single year, a range, or an arbitrary list of years.
        
        Args:
            ticker: Stock ticker code (e.g., 'BBCA', 'TLKM', 'ASII')
            start_year: Optional start year
            end_year: Optional end year
            years: Optional explicit list of years (e.g. [2023], [2020, 2021, 2022], [2019, 2021, 2023])
            period: Reporting period ('audit', 'tw1', 'tw2', 'tw3')
            parse_and_export: Whether to parse Excel files and export a multi-year consolidated Excel workbook
        """
        ticker = ticker.strip().upper()

        # Resolve years to query
        if years is not None:
            years_to_query = sorted(list(set(years)))
        elif start_year is not None and end_year is not None:
            years_to_query = list(range(min(start_year, end_year), max(start_year, end_year) + 1))
        elif start_year is not None:
            years_to_query = [start_year]
        else:
            years_to_query = [2020, 2021, 2022, 2023, 2024]

        year_label = format_year_range_label(years_to_query)
        year_slug = format_year_range_slug(years_to_query)
        print(f"\n[+] Searching filings for {ticker} ({year_label}, Period: {period})...")

        # 1. Query filing history
        filings = self.api.get_filing_history(
            kode_emiten=ticker,
            years=years_to_query,
            period=period
        )

        if not filings:
            print(f"[-] No filings found for {ticker} across: {year_label}.")
            return {"ticker": ticker, "status": "no_filings", "downloaded_files": [], "compiled_excel": None}

        # Check if any requested years were not found on IDX
        filing_years_found = {f["year"] for f in filings}
        missing_years = [y for y in years_to_query if y not in filing_years_found]
        if missing_years:
            print(f"  [i] Note: No online filings published on IDX portal for years {missing_years}.")
            print(f"  [+] Found {len(filings)} filings: {sorted(list(filing_years_found))}")
        else:
            print(f"[+] Found {len(filings)} filings for {ticker}.")

        # 2. Download standardized Excel files
        downloaded_files = []
        parsed_reports = []

        ticker_dir = os.path.join(self.output_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)

        for f in filings:
            year = f["year"]
            att = f.get("attachment")
            if not att:
                print(f"  [!] Year {year}: No standardized Excel attachment found.")
                continue

            file_path = att.get("File_Path")
            file_name = att.get("File_Name")
            dest_dir = os.path.join(ticker_dir, str(year))
            dest_file = os.path.join(dest_dir, file_name)

            print(f"  [*] Downloading Year {year}: {file_name}...")
            newly_downloaded = self.client.download_file(file_path, dest_file, overwrite=False)
            downloaded_files.append(dest_file)

            # Download XBRL zip if available
            zip_att = f.get("zip_attachment")
            if zip_att and zip_att.get("File_Path"):
                z_path = zip_att.get("File_Path")
                z_name = zip_att.get("File_Name") or "instance.zip"
                dest_zip = os.path.join(dest_dir, z_name)
                print(f"  [*] Downloading Year {year} XBRL: {z_name}...")
                self.client.download_file(z_path, dest_zip, overwrite=False)
                downloaded_files.append(dest_zip)

            # 3. Parse if requested
            if parse_and_export and os.path.exists(dest_file):
                try:
                    parsed = parse_financial_statement_file(dest_file)
                    parsed["year"] = year
                    parsed_reports.append(parsed)
                except Exception as e:
                    logger.error(f"Error parsing {dest_file}: {e}")

        compiled_excel_path = None
        if parse_and_export and parsed_reports:
            print(f"[+] Compiling multi-year statements ({len(parsed_reports)} years)...")
            
            # Sort reports chronologically
            parsed_reports.sort(key=lambda x: x.get("year", 0))

            bs_multi = merge_statement_tables(parsed_reports, "balance_sheet")
            is_multi = merge_statement_tables(parsed_reports, "income_statement")
            cf_multi = merge_statement_tables(parsed_reports, "cash_flow")

            # Collect latest general info
            latest_info = parsed_reports[-1].get("general_info", {})
            info_df = pd.DataFrame(list(latest_info.items()), columns=["Field", "Value"])

            compiled_excel_name = f"{ticker}_financial_statements_{year_slug}.xlsx"
            compiled_excel_path = os.path.join(ticker_dir, compiled_excel_name)

            with pd.ExcelWriter(compiled_excel_path, engine="openpyxl") as writer:
                if not bs_multi.empty:
                    bs_multi.to_excel(writer, sheet_name="Balance_Sheet", index=False)
                if not is_multi.empty:
                    is_multi.to_excel(writer, sheet_name="Income_Statement", index=False)
                if not cf_multi.empty:
                    cf_multi.to_excel(writer, sheet_name="Cash_Flow", index=False)
                if not info_df.empty:
                    info_df.to_excel(writer, sheet_name="General_Info", index=False)

            print(f"[OK] Successfully compiled multi-year workbook: {compiled_excel_path}")

        return {
            "ticker": ticker,
            "status": "success",
            "filings_count": len(filings),
            "downloaded_files": downloaded_files,
            "compiled_excel": compiled_excel_path,
            "parsed_reports": parsed_reports
        }

    def build_ready_to_forecast(
        self,
        ticker: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        years: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Extract, normalize, and compile clean historical financial statements
        and operational drivers into a Ready-to-Forecast Excel model across any time horizon.
        """
        ticker = ticker.strip().upper()

        # Resolve years to process
        if years is not None:
            years_to_process = sorted(list(set(years)))
        elif start_year is not None and end_year is not None:
            years_to_process = list(range(min(start_year, end_year), max(start_year, end_year) + 1))
        elif start_year is not None:
            years_to_process = [start_year]
        else:
            years_to_process = [2020, 2021, 2022, 2023, 2024]

        year_label = format_year_range_label(years_to_process)
        year_slug = format_year_range_slug(years_to_process)
        print(f"\n[+] Preparing Ready-to-Forecast Financials for {ticker} ({year_label})...")

        # 1. Ensure files are scraped and multi-year raw tables exist
        scrape_res = self.scrape_ticker(
            ticker=ticker,
            years=years_to_process,
            period="audit",
            parse_and_export=True
        )

        compiled_excel = scrape_res.get("compiled_excel")
        if not compiled_excel or not os.path.exists(compiled_excel):
            print(f"[-] Could not find compiled historical statements for {ticker}.")
            return {"status": "error", "message": "Raw files could not be scraped"}

        ticker_dir = os.path.join(self.output_dir, ticker)

        # 2. Read compiled tables
        xls = pd.ExcelFile(compiled_excel)
        df_bs = pd.read_excel(xls, "Balance_Sheet") if "Balance_Sheet" in xls.sheet_names else pd.DataFrame()
        df_is = pd.read_excel(xls, "Income_Statement") if "Income_Statement" in xls.sheet_names else pd.DataFrame()
        df_cf = pd.read_excel(xls, "Cash_Flow") if "Cash_Flow" in xls.sheet_names else pd.DataFrame()
        
        info_dict = {}
        if "General_Info" in xls.sheet_names:
            df_info = pd.read_excel(xls, "General_Info")
            for _, r in df_info.iterrows():
                if pd.notna(r.iloc[0]):
                    info_dict[str(r.iloc[0])] = str(r.iloc[1]) if pd.notna(r.iloc[1]) else ""

        # Filter years_to_process to only those years where data was actually found
        # (either downloaded in ticker_dir or present in compiled Excel)
        valid_years = []
        for y in years_to_process:
            y_dir = os.path.join(ticker_dir, str(y))
            if os.path.exists(y_dir) or str(y) in df_bs.columns or str(y) in df_is.columns:
                valid_years.append(y)

        if not valid_years:
            valid_years = years_to_process

        # Detect sector & financial modeling archetype
        archetype = detect_archetype(
            ticker=ticker,
            general_info=info_dict,
            sheet_names=xls.sheet_names
        )
        arch_desc = "Banking & Financial Institutions Model" if archetype == "banking" else "Corporate Operating Model"
        print(f"[+] Detected Archetype: {archetype.upper()} ({arch_desc})")

        # 3. Normalize each year (Primary: XBRL instance, Fallback: Excel waterfall)
        normalizer = FinancialNormalizer(target_scale="millions")
        is_dict = {}
        bs_dict = {}
        cf_dict = {}

        print(f"[+] Normalizing statements across {len(valid_years)} year(s) (Primary: XBRL, Fallback: Excel)...")

        for yr in valid_years:
            year_dir = os.path.join(ticker_dir, str(yr))
            zip_candidates = [
                os.path.join(year_dir, "instance.zip"),
                os.path.join(year_dir, f"instance-{yr}.zip"),
            ]
            if os.path.exists(year_dir):
                for f_name in os.listdir(year_dir):
                    if f_name.endswith(".zip"):
                        candidate = os.path.join(year_dir, f_name)
                        if candidate not in zip_candidates:
                            zip_candidates.append(candidate)

            xbrl_loaded = False
            for z_path in zip_candidates:
                if os.path.exists(z_path):
                    try:
                        facts, dei, contexts = XBRLParser.load_instance(z_path)
                        if facts:
                            if archetype == "banking":
                                is_stmt, bs_stmt, cf_stmt = XBRLParser.extract_banking_statements(facts, yr, dei=dei)
                            else:
                                is_stmt, bs_stmt, cf_stmt = XBRLParser.extract_normalized_statements(facts, yr, dei=dei)
                            is_dict[yr] = is_stmt
                            bs_dict[yr] = bs_stmt
                            cf_dict[yr] = cf_stmt
                            xbrl_loaded = True
                            print(f"  [+] Year {yr}: Loaded directly from primary XBRL data (BS Balance Check: {bs_stmt.balance_check:0.2f})")
                            break
                    except Exception as e:
                        logger.warning(f"Failed to load XBRL for {ticker} {yr} from {z_path}: {e}")

            if not xbrl_loaded:
                # Check if next year's ZIP exists and can provide prior-year comparative data
                next_yr = yr + 1
                next_yr_dir = os.path.join(ticker_dir, str(next_yr))
                next_zip_candidates = [
                    os.path.join(next_yr_dir, "instance.zip"),
                    os.path.join(next_yr_dir, f"instance-{next_yr}.zip"),
                ]
                for next_z in next_zip_candidates:
                    if os.path.exists(next_z):
                        try:
                            facts_next, dei_next, _ = XBRLParser.load_instance(next_z)
                            if facts_next:
                                if archetype == "banking":
                                    is_stmt, bs_stmt, cf_stmt = XBRLParser.extract_banking_statements(facts_next, yr, dei=dei_next, period_target="prior")
                                else:
                                    is_stmt, bs_stmt, cf_stmt = XBRLParser.extract_normalized_statements(facts_next, yr, dei=dei_next, period_target="prior")
                                if bs_stmt.total_assets > 0:
                                    is_dict[yr] = is_stmt
                                    bs_dict[yr] = bs_stmt
                                    cf_dict[yr] = cf_stmt
                                    xbrl_loaded = True
                                    print(f"  [+] Year {yr}: Extracted from {next_yr} comparative XBRL data (BS Balance Check: {bs_stmt.balance_check:0.2f})")
                                    break
                        except Exception as e:
                            logger.debug(f"Failed prior-period comparative extraction from {next_z}: {e}")

            if not xbrl_loaded:
                print(f"  [*] Year {yr}: Falling back to Excel waterfall resolution...")
                if archetype == "banking":
                    is_stmt, bs_stmt, cf_stmt = normalizer.normalize_banking_year(
                        year=yr,
                        df_is=df_is,
                        df_bs=df_bs,
                        df_cf=df_cf,
                        general_info=info_dict
                    )
                else:
                    is_stmt, bs_stmt, cf_stmt = normalizer.normalize_year(
                        year=yr,
                        df_is=df_is,
                        df_bs=df_bs,
                        df_cf=df_cf,
                        general_info=info_dict
                    )
                is_dict[yr] = is_stmt
                bs_dict[yr] = bs_stmt
                cf_dict[yr] = cf_stmt

        # 4. Compute operational drivers
        if archetype == "banking":
            print("[+] Calculating historical banking drivers (NIM, CoF, LDR, CASA, BOPO/CIR, Credit Cost, ROA, ROE)...")
            drivers_by_year = BankingDriverCalculator.calculate_drivers(valid_years, is_dict, bs_dict, cf_dict)
            benchmarks = BankingDriverCalculator.build_summary_benchmarks(drivers_by_year)
        else:
            print("[+] Calculating historical forecasting drivers (DSO, DIO, DPO, margins, Capex)...")
            drivers_by_year = DriverCalculator.calculate_drivers(valid_years, is_dict, bs_dict, cf_dict)
            benchmarks = DriverCalculator.build_summary_benchmarks(drivers_by_year)

        # 5. Export 5-tab ready-to-forecast workbook
        ticker_dir = os.path.join(self.output_dir, ticker)
        output_name = f"{ticker}_ReadyToForecast_Financials_{year_slug}.xlsx"
        output_path = os.path.join(ticker_dir, output_name)

        print(f"[+] Exporting Ready-to-Forecast Excel model: {output_name}...")
        ReadyToForecastExporter.export(
            dest_path=output_path,
            ticker=ticker,
            years=valid_years,
            is_dict=is_dict,
            bs_dict=bs_dict,
            cf_dict=cf_dict,
            drivers_by_year=drivers_by_year,
            general_info=info_dict,
            archetype=archetype
        )

        print(f"[OK] Ready-to-Forecast model exported successfully to:\n     {os.path.abspath(output_path)}")

        return {
            "ticker": ticker,
            "status": "success",
            "ready_excel": output_path,
            "archetype": archetype,
            "years": valid_years,
            "is_dict": is_dict,
            "bs_dict": bs_dict,
            "cf_dict": cf_dict,
            "drivers_by_year": drivers_by_year,
            "benchmarks": benchmarks
        }
