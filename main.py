#!/usr/bin/env python3
"""
IDX Financial Statement Scraper & Ready-to-Forecast Modeling Engine CLI.
Easily scrape, normalize, and compile 5+ years of financial statements from the Indonesia Stock Exchange.
"""

import os
import sys
import argparse
from tabulate import tabulate
import pandas as pd

# Ensure utf-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from idx_scraper.client import IDXClient
from idx_scraper.api import IDXApi
from idx_scraper.scraper import IDXFinancialScraper
from idx_scraper.year_utils import parse_year_input, format_year_range_label


def print_banner():
    print("=" * 72)
    print("     IDX FINANCIAL STATEMENT & READY-TO-FORECAST MODELING ENGINE     ")
    print("           PT Bursa Efek Indonesia (idx.co.id) Automation            ")
    print("=" * 72)


def display_ready_to_forecast_summary(res: dict):
    """Print terminal summary of normalized 3-statement tables and forecasting drivers."""
    ticker = res.get("ticker", "").upper()
    years = res.get("years", [])
    is_dict = res.get("is_dict", {})
    bs_dict = res.get("bs_dict", {})
    drivers_by_year = res.get("drivers_by_year", {})
    benchmarks = res.get("benchmarks", {})
    archetype = res.get("archetype", "corporate")

    arch_title = "BANKING & FINANCIAL INSTITUTIONS" if archetype == "banking" else "CORPORATE 3-STATEMENT"
    print("\n" + "=" * 74)
    print(f"      {arch_title} READY-TO-FORECAST FINANCIALS: {ticker}")
    print("      (All Amounts Normalized to Millions IDR / Juta Rupiah)")
    print("=" * 74)

    if archetype == "banking":
        # 1. Banking Income Statement
        is_rows = []
        is_keys = [
            "Interest & Sharia Income", "Interest & Sharia Expense",
            "Net Interest Income (NII)", "Non-Interest & Fee Income",
            "Total Operating Income", "Operating Expenses (Opex)",
            "Pre-Provision Operating Profit (PPOP)", "Provision for Impairment (CKPN)",
            "Operating Profit", "Earnings Before Tax (EBT)", "Net Income"
        ]
        for k in is_keys:
            row = [k]
            for y in years:
                v = is_dict.get(y).to_dict().get(k, 0.0)
                row.append(f"{v:,.0f}" if v is not None else "-")
            is_rows.append(row)

        print("\n[NORMALIZED BANKING INCOME STATEMENT - Millions IDR]")
        headers_is = ["Metric"] + [str(y) for y in years]
        print(tabulate(is_rows, headers=headers_is, tablefmt="fancy_grid"))

        # 2. Banking Balance Sheet
        bs_rows = []
        bs_keys = [
            "Cash & Placements with BI & Banks", "Marketable Securities",
            "Gross Loans & Financing", "Allowance for Impairment (CKPN)",
            "Net Loans & Financing", "Total Earning Assets", "TOTAL ASSETS",
            "Total Customer Deposits (DPK)", "Deposits from Other Banks",
            "Borrowings & Debt Issued", "TOTAL LIABILITIES",
            "Temporary Syirkah Funds", "TOTAL EQUITY",
            "BALANCE CHECK (Assets - Liab&Eq)"
        ]
        for k in bs_keys:
            row = [k]
            for y in years:
                v = bs_dict.get(y).to_dict().get(k, 0.0)
                if "BALANCE CHECK" in k:
                    status = "OK (0.0)" if abs(v) < 0.05 else f"DIFF ({v:,.1f})"
                    row.append(status)
                else:
                    row.append(f"{v:,.0f}" if v is not None else "-")
            bs_rows.append(row)

        print("\n[NORMALIZED BANKING BALANCE SHEET - Millions IDR]")
        headers_bs = ["Metric"] + [str(y) for y in years]
        print(tabulate(bs_rows, headers=headers_bs, tablefmt="fancy_grid"))

        # 3. Banking Operational Ratios & Drivers
        drv_rows = []
        drv_keys = [
            "Loan Growth (YoY)",
            "Deposit Growth (YoY)",
            "Net Interest Margin (NIM %)",
            "Cost of Funds (CoF %)",
            "Loan-to-Deposit Ratio (LDR %)",
            "CASA Ratio (%)",
            "Cost-to-Income / BOPO (CIR %)",
            "Credit Cost / Provision Rate (%)",
            "Return on Assets (ROA %)",
            "Return on Equity (ROE %)",
            "Equity to Assets Ratio (%)",
            "Effective Tax Rate (%)",
            "Dividend Payout Ratio (%)",
        ]
        n_years = len(years)

        for k in drv_keys:
            row = [k]
            for y in years:
                v = drivers_by_year.get(y).to_dict().get(k)
                if v is not None:
                    row.append(f"{v * 100:.2f}%")
                else:
                    row.append("-")

            if n_years >= 3:
                med = benchmarks.get("3_Year_Median", {}).get(k)
                avg = benchmarks.get("Historical_Average", benchmarks.get("5_Year_Average", {})).get(k)
                row.append(f"{med * 100:.2f}%" if med is not None else "-")
                row.append(f"{avg * 100:.2f}%" if avg is not None else "-")
            elif n_years == 2:
                avg = benchmarks.get("Historical_Average", benchmarks.get("5_Year_Average", {})).get(k)
                row.append(f"{avg * 100:.2f}%" if avg is not None else "-")

            drv_rows.append(row)

        print("\n[HISTORICAL BANKING DRIVERS & FINANCIAL RATIOS]")
        if n_years >= 3:
            headers_drv = ["Banking Driver / Ratio"] + [str(y) for y in years] + ["3-Yr Median", "Average"]
        elif n_years == 2:
            headers_drv = ["Banking Driver / Ratio"] + [str(y) for y in years] + ["Average"]
        else:
            headers_drv = ["Banking Driver / Ratio", str(years[0])]

        print(tabulate(drv_rows, headers=headers_drv, tablefmt="fancy_grid"))

    else:
        # 1. Income Statement Highlights
        is_rows = []
        is_keys = [
            "Gross Revenue", "Cost of Goods Sold (COGS)", "Gross Profit",
            "SG&A / Operating Expenses", "EBITDA", "Operating Income (EBIT)",
            "Earnings Before Tax (EBT)", "Net Income"
        ]
        for k in is_keys:
            row = [k]
            for y in years:
                v = is_dict.get(y).to_dict().get(k, 0.0)
                row.append(f"{v:,.0f}" if v is not None else "-")
            is_rows.append(row)

        print("\n[NORMALIZED INCOME STATEMENT - Millions IDR]")
        headers_is = ["Metric"] + [str(y) for y in years]
        print(tabulate(is_rows, headers=headers_is, tablefmt="fancy_grid"))

        # 2. Balance Sheet Highlights
        bs_rows = []
        bs_keys = [
            "Cash & Cash Equivalents", "Accounts Receivable", "Inventories",
            "Total Current Assets", "Net PP&E", "TOTAL ASSETS",
            "Accounts Payable", "Short-Term Debt", "Total Current Liabilities",
            "Long-Term Debt", "TOTAL LIABILITIES", "TOTAL EQUITY",
            "BALANCE CHECK (Assets - Liab&Eq)"
        ]
        for k in bs_keys:
            row = [k]
            for y in years:
                v = bs_dict.get(y).to_dict().get(k, 0.0)
                if "BALANCE CHECK" in k:
                    status = "OK (0.0)" if abs(v) < 0.05 else f"DIFF ({v:,.1f})"
                    row.append(status)
                else:
                    row.append(f"{v:,.0f}" if v is not None else "-")
            bs_rows.append(row)

        print("\n[NORMALIZED BALANCE SHEET - Millions IDR]")
        headers_bs = ["Metric"] + [str(y) for y in years]
        print(tabulate(bs_rows, headers=headers_bs, tablefmt="fancy_grid"))

        # 3. Operational Forecasting Drivers
        drv_rows = []
        drv_keys = [
            ("Revenue Growth (YoY)", True, False),
            ("Gross Margin (%)", True, False),
            ("SG&A / Opex (% Rev)", True, False),
            ("Operating Margin (EBIT %)", True, False),
            ("Net Profit Margin (%)", True, False),
            ("Effective Tax Rate (%)", True, False),
            ("DSO - Days Sales Outstanding (Days)", False, True),
            ("DIO - Days Inventory Outstanding (Days)", False, True),
            ("DPO - Days Payable Outstanding (Days)", False, True),
            ("Capex (% of Revenue)", True, False),
            ("D&A (% of Net PP&E)", True, False),
            ("Dividend Payout Ratio (%)", True, False),
        ]

        n_years = len(years)

        for k, is_pct, is_days in drv_keys:
            row = [k]
            for y in years:
                v = drivers_by_year.get(y).to_dict().get(k)
                if v is not None:
                    row.append(f"{v * 100:.1f}%" if is_pct else (f"{v:.1f}" if is_days else f"{v:.2f}"))
                else:
                    row.append("-")

            # Benchmarks based on length
            if n_years >= 3:
                med = benchmarks.get("3_Year_Median", {}).get(k)
                avg = benchmarks.get("Historical_Average", benchmarks.get("5_Year_Average", {})).get(k)
                row.append(f"{med * 100:.1f}%" if (is_pct and med is not None) else (f"{med:.1f}" if (is_days and med is not None) else "-"))
                row.append(f"{avg * 100:.1f}%" if (is_pct and avg is not None) else (f"{avg:.1f}" if (is_days and avg is not None) else "-"))
            elif n_years == 2:
                avg = benchmarks.get("Historical_Average", benchmarks.get("5_Year_Average", {})).get(k)
                row.append(f"{avg * 100:.1f}%" if (is_pct and avg is not None) else (f"{avg:.1f}" if (is_days and avg is not None) else "-"))
            
            drv_rows.append(row)

        print("\n[HISTORICAL OPERATIONAL DRIVERS & RATIOS]")
        if n_years >= 3:
            headers_drv = ["Driver / Ratio"] + [str(y) for y in years] + ["3-Yr Median", "Average"]
        elif n_years == 2:
            headers_drv = ["Driver / Ratio"] + [str(y) for y in years] + ["Average"]
        else:
            headers_drv = ["Driver / Ratio", str(years[0])]

        print(tabulate(drv_rows, headers=headers_drv, tablefmt="fancy_grid"))


def run_interactive():
    print_banner()
    print("Select Mode:")
    print("  [1] Auto-Fetch from IDX (Online - Enter Ticker & Years)")
    print("  [2] Process Local Folder (Offline - Drag & Drop Folder with .xlsx / .zip)")
    print("  [Q] Quit")
    mode_choice = input("\nChoice [1/2/Q, default: 1]: ").strip().lower()

    if mode_choice in ("q", "quit", "exit"):
        print("Exiting.")
        sys.exit(0)

    if mode_choice == "2":
        folder_input = input("\nEnter Folder Path (or drag and drop folder here): ").strip().strip('"').strip("'")
        if not folder_input:
            print("[-] Folder path cannot be empty.")
            return
        scraper = IDXFinancialScraper(output_dir="downloads")
        results = scraper.process_local_folder(folder_input)
        if results:
            for res in results:
                if res.get("status") == "success":
                    display_ready_to_forecast_summary(res)
                    print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}\n")
        else:
            print("[-] No financial statements could be processed from the specified path.")
        return

    api = IDXApi()

    while True:
        ticker_input = input("\nEnter Stock Ticker (e.g. BBCA, TLKM, ASII, BBRI) or 'list' / 'q' to quit: ").strip()
        if not ticker_input:
            continue
        if ticker_input.lower() in ("q", "quit", "exit"):
            print("Exiting.")
            sys.exit(0)

        if ticker_input.lower() == "list":
            emitens = api.get_emitens()
            print(f"\n[+] Total Active Emitens: {len(emitens)}")
            search_term = input("Filter by keyword (press Enter for first 20): ").strip()
            filtered = api.search_emiten(search_term) if search_term else emitens[:20]
            table_data = [[e["KodeEmiten"], e["NamaEmiten"]] for e in filtered[:25]]
            print(tabulate(table_data, headers=["Ticker", "Company Name"], tablefmt="simple"))
            continue

        ticker = ticker_input.upper()
        
        # Verify ticker exists
        matches = api.search_emiten(ticker)
        matched = next((m for m in matches if m["KodeEmiten"].upper() == ticker), None)
        if matched:
            print(f"[+] Found: {matched['KodeEmiten']} - {matched['NamaEmiten']}")
        else:
            print(f"[!] Warning: Ticker '{ticker}' not found in active emiten list, continuing anyway...")

        # Ask workflow
        print("\nSelect Output:")
        print("  [1] Generate 3-Statement Ready-to-Forecast Model (Recommended)")
        print("  [2] Raw Multi-Year Statement Compilation only")
        choice = input("Choice [1/2, default: 1]: ").strip()
        is_ready_model = (choice != "2")

        # Ask years with smart flexible syntax
        year_prompt = input("\nEnter Year or Range (e.g. 2023, 2020-2023, 2018-2024, or 'all') [default: 2020-2024]: ").strip()
        parsed_years = parse_year_input(year_prompt)

        if parsed_years == ["ALL"]:
            years_to_use = api.get_available_filing_years(ticker)
        elif parsed_years is not None:
            years_to_use = parsed_years
        else:
            years_to_use = [2020, 2021, 2022, 2023, 2024]

        scraper = IDXFinancialScraper(output_dir="downloads", client=api.client)

        if is_ready_model:
            res = scraper.build_ready_to_forecast(
                ticker=ticker,
                years=years_to_use
            )
            if res.get("status") == "success":
                display_ready_to_forecast_summary(res)
                print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}\n")
        else:
            res = scraper.scrape_ticker(
                ticker=ticker,
                years=years_to_use,
                period="audit",
                parse_and_export=True
            )
            if res.get("compiled_excel"):
                print(f"\n[OK] Raw compiled workbook saved to:\n     {os.path.abspath(res['compiled_excel'])}\n")


def main():
    parser = argparse.ArgumentParser(description="IDX Financial Statement Scraper & Ready-to-Forecast Engine")
    parser.add_argument("-t", "--ticker", type=str, help="Stock ticker code (e.g., TLKM, BBCA, ASII)")
    parser.add_argument("-y", "--year", type=int, help="Extract a single specific year (e.g. 2023)")
    parser.add_argument("--years", type=str, help="Year specification: single (2023), range (2020-2023), list (2020,2022,2024), or 'all'")
    parser.add_argument("--all", action="store_true", help="Probe and extract all available historical filing years on IDX")
    parser.add_argument("--start-year", type=int, default=None, help="Start year (optional)")
    parser.add_argument("--end-year", type=int, default=None, help="End year (optional)")
    parser.add_argument("-p", "--period", type=str, default="audit", choices=["audit", "tw1", "tw2", "tw3"], help="Period (default: audit)")
    parser.add_argument("--input-dir", "--dir", "-d", dest="input_dir", type=str, help="Process financial statements from a local directory (offline mode)")
    parser.add_argument("-f", "--file", type=str, help="Process a single financial statement file (.xlsx or .zip)")
    parser.add_argument("-o", "--output-dir", type=str, default="downloads", help="Directory to save downloads")
    parser.add_argument("--ready-to-forecast", "--proforma", action="store_true", help="Generate clean 5-tab ready-to-forecast model")
    parser.add_argument("--list", action="store_true", help="List all available stock tickers")
    parser.add_argument("--search", type=str, help="Search company name or ticker")

    args = parser.parse_args()

    if args.list:
        api = IDXApi()
        emitens = api.get_emitens()
        print(f"\n[+] Total Active Emitens: {len(emitens)}")
        table_data = [[e["KodeEmiten"], e["NamaEmiten"]] for e in emitens]
        print(tabulate(table_data, headers=["Ticker", "Company Name"], tablefmt="simple"))
        return

    if args.input_dir or args.file:
        target_path = args.input_dir or args.file
        print_banner()
        print(f"\n[+] Offline Mode: Ingesting local files from:\n    {os.path.abspath(target_path)}")
        scraper = IDXFinancialScraper(output_dir=args.output_dir)
        results = scraper.process_local_folder(target_path)
        if results:
            for res in results:
                if res.get("status") == "success":
                    display_ready_to_forecast_summary(res)
                    print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}\n")
        else:
            print("[-] No financial statements could be processed from the specified path.")
        return

    if args.search:
        api = IDXApi()
        results = api.search_emiten(args.search)
        print(f"\n[+] Found {len(results)} matches for '{args.search}':")
        table_data = [[e["KodeEmiten"], e["NamaEmiten"]] for e in results]
        print(tabulate(table_data, headers=["Ticker", "Company Name"], tablefmt="simple"))
        return

    if args.ticker:
        print_banner()
        api = IDXApi()
        scraper = IDXFinancialScraper(output_dir=args.output_dir, client=api.client)

        # Resolve requested years
        years_to_use = None
        if args.all:
            years_to_use = api.get_available_filing_years(args.ticker)
        elif args.year:
            years_to_use = [args.year]
        elif args.years:
            parsed = parse_year_input(args.years)
            if parsed == ["ALL"]:
                years_to_use = api.get_available_filing_years(args.ticker)
            elif parsed:
                years_to_use = parsed
        elif args.start_year is not None and args.end_year is not None:
            years_to_use = list(range(min(args.start_year, args.end_year), max(args.start_year, args.end_year) + 1))
        elif args.start_year is not None:
            years_to_use = [args.start_year]
        else:
            # Default to standard 5 years if no year arguments specified
            years_to_use = [2020, 2021, 2022, 2023, 2024]

        if not years_to_use:
            print(f"[-] No valid years could be resolved for {args.ticker}.")
            return

        if args.ready_to_forecast:
            res = scraper.build_ready_to_forecast(
                ticker=args.ticker,
                years=years_to_use
            )
            if res.get("status") == "success":
                display_ready_to_forecast_summary(res)
                print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}")
        else:
            res = scraper.scrape_ticker(
                ticker=args.ticker,
                years=years_to_use,
                period=args.period,
                parse_and_export=True
            )
            if res.get("compiled_excel"):
                print(f"\n[OK] Raw consolidated workbook saved to:\n     {os.path.abspath(res['compiled_excel'])}")
        return

    # No arguments passed -> Launch interactive mode
    run_interactive()


if __name__ == "__main__":
    main()
