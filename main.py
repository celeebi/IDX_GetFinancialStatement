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

    print("\n" + "=" * 72)
    print(f"      3-STATEMENT READY-TO-FORECAST FINANCIALS: {ticker}")
    print("      (All Amounts Normalized to Millions IDR / Juta Rupiah)")
    print("=" * 72)

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

    for k, is_pct, is_days in drv_keys:
        row = [k]
        for y in years:
            v = drivers_by_year.get(y).to_dict().get(k)
            if v is not None:
                row.append(f"{v * 100:.1f}%" if is_pct else (f"{v:.1f}" if is_days else f"{v:.2f}"))
            else:
                row.append("-")

        # 3-Year Median & 5-Year Average benchmarks
        med = benchmarks.get("3_Year_Median", {}).get(k)
        avg = benchmarks.get("5_Year_Average", {}).get(k)
        row.append(f"{med * 100:.1f}%" if (is_pct and med is not None) else (f"{med:.1f}" if (is_days and med is not None) else "-"))
        row.append(f"{avg * 100:.1f}%" if (is_pct and avg is not None) else (f"{avg:.1f}" if (is_days and avg is not None) else "-"))
        drv_rows.append(row)

    print("\n[HISTORICAL OPERATIONAL DRIVERS & RATIOS]")
    headers_drv = ["Driver / Ratio"] + [str(y) for y in years] + ["3-Yr Median", "5-Yr Average"]
    print(tabulate(drv_rows, headers=headers_drv, tablefmt="fancy_grid"))


def run_interactive():
    print_banner()
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

        # Ask years
        start_year_str = input("Start year [default 2020]: ").strip()
        start_year = int(start_year_str) if start_year_str.isdigit() else 2020

        end_year_str = input("End year [default 2024]: ").strip()
        end_year = int(end_year_str) if end_year_str.isdigit() else 2024

        scraper = IDXFinancialScraper(output_dir="downloads")

        if is_ready_model:
            res = scraper.build_ready_to_forecast(
                ticker=ticker,
                start_year=start_year,
                end_year=end_year
            )
            if res.get("status") == "success":
                display_ready_to_forecast_summary(res)
                print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}\n")
        else:
            res = scraper.scrape_ticker(
                ticker=ticker,
                start_year=start_year,
                end_year=end_year,
                period="audit",
                parse_and_export=True
            )
            if res.get("compiled_excel"):
                print(f"\n[OK] Raw compiled workbook saved to:\n     {os.path.abspath(res['compiled_excel'])}\n")


def main():
    parser = argparse.ArgumentParser(description="IDX Financial Statement Scraper & Ready-to-Forecast Engine")
    parser.add_argument("-t", "--ticker", type=str, help="Stock ticker code (e.g., TLKM, BBCA, ASII)")
    parser.add_argument("--start-year", type=int, default=2020, help="Start year (default: 2020)")
    parser.add_argument("--end-year", type=int, default=2024, help="End year (default: 2024)")
    parser.add_argument("-p", "--period", type=str, default="audit", choices=["audit", "tw1", "tw2", "tw3"], help="Period (default: audit)")
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

    if args.search:
        api = IDXApi()
        results = api.search_emiten(args.search)
        print(f"\n[+] Found {len(results)} matches for '{args.search}':")
        table_data = [[e["KodeEmiten"], e["NamaEmiten"]] for e in results]
        print(tabulate(table_data, headers=["Ticker", "Company Name"], tablefmt="simple"))
        return

    if args.ticker:
        print_banner()
        scraper = IDXFinancialScraper(output_dir=args.output_dir)

        if args.ready_to_forecast:
            res = scraper.build_ready_to_forecast(
                ticker=args.ticker,
                start_year=args.start_year,
                end_year=args.end_year
            )
            if res.get("status") == "success":
                display_ready_to_forecast_summary(res)
                print(f"\n[OK] Ready-to-Forecast workbook saved to:\n     {os.path.abspath(res['ready_excel'])}")
        else:
            res = scraper.scrape_ticker(
                ticker=args.ticker,
                start_year=args.start_year,
                end_year=args.end_year,
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
