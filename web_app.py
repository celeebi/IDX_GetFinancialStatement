#!/usr/bin/env python3
"""
IDX Financial Statement & Ready-to-Forecast Modeling Engine - Web Application.
FastAPI backend server providing interactive UI, live scraping, statement viewing,
and one-click Excel downloads.

Created by: abas YP74A
"""

import os
import sys
import shutil
import tempfile
import webbrowser
import threading
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from idx_scraper.api import IDXApi
from idx_scraper.scraper import IDXFinancialScraper
from idx_scraper.year_utils import format_period_label, period_sort_key

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = FastAPI(
    title="IDX Financial Statement & Modeling Engine Web UI",
    description="Interactive Financial Analysis & 3-Statement Modeling for Indonesia Stock Exchange. Created by: abas YP74A",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


class ScrapeRequest(BaseModel):
    ticker: str
    mode: Optional[str] = "latest_interim"  # "latest_interim" or "custom"
    years: Optional[List[int]] = None


def serialize_model_result(res: Dict[str, Any]) -> Dict[str, Any]:
    """Transform internal scraper result dictionary into a clean JSON response for the frontend."""
    ticker = res.get("ticker", "").upper()
    years = res.get("years", [])
    sorted_periods = sorted(years, key=period_sort_key)
    period_labels = [format_period_label(p) for p in sorted_periods]

    is_dict = res.get("is_dict", {})
    bs_dict = res.get("bs_dict", {})
    cf_dict = res.get("cf_dict", {})
    drivers_by_year = res.get("drivers_by_year", {})
    benchmarks = res.get("benchmarks", {})
    archetype = res.get("archetype", "corporate")
    ready_excel = res.get("ready_excel")

    # Extract Income Statement rows
    is_rows = []
    if is_dict:
        sample_is = next(iter(is_dict.values()))
        for k in sample_is.to_dict().keys():
            values = {}
            for p in sorted_periods:
                stmt = is_dict.get(p)
                values[str(p)] = stmt.to_dict().get(k) if stmt else None
            is_rows.append({"metric": k, "values": values})

    # Extract Balance Sheet rows
    bs_rows = []
    if bs_dict:
        sample_bs = next(iter(bs_dict.values()))
        for k in sample_bs.to_dict().keys():
            values = {}
            for p in sorted_periods:
                stmt = bs_dict.get(p)
                values[str(p)] = stmt.to_dict().get(k) if stmt else None
            bs_rows.append({"metric": k, "values": values})

    # Extract Cash Flow rows
    cf_rows = []
    if cf_dict:
        sample_cf = next(iter(cf_dict.values()))
        for k in sample_cf.to_dict().keys():
            values = {}
            for p in sorted_periods:
                stmt = cf_dict.get(p)
                values[str(p)] = stmt.to_dict().get(k) if stmt else None
            cf_rows.append({"metric": k, "values": values})

    # Extract Driver rows
    driver_rows = []
    if drivers_by_year:
        sample_drv = next(iter(drivers_by_year.values()))
        for k in sample_drv.to_dict().keys():
            values = {}
            for p in sorted_periods:
                drv = drivers_by_year.get(p)
                values[str(p)] = drv.to_dict().get(k) if drv else None
            driver_rows.append({"metric": k, "values": values})

    # Extract Company General Info
    gen_info = {}
    if res.get("general_info"):
        gen_info.update(res["general_info"])
    gen_info["Program Developer"] = "abas YP74A"
    gen_info["Archetype Model"] = "Banking & Financial Institutions" if archetype == "banking" else "Corporate Operating Model"

    company_name = gen_info.get("Nama entitas", gen_info.get("Entity Name", ticker))

    return {
        "status": "success",
        "ticker": ticker,
        "company_name": company_name,
        "archetype": archetype,
        "years": [str(p) for p in sorted_periods],
        "period_labels": period_labels,
        "statements": {
            "income_statement": is_rows,
            "balance_sheet": bs_rows,
            "cash_flow": cf_rows
        },
        "drivers": driver_rows,
        "benchmarks": benchmarks,
        "general_info": gen_info,
        "ready_excel_filename": os.path.basename(ready_excel) if ready_excel else None
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the single-page interactive dashboard."""
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend template not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "IDX Financial Modeling Engine", "author": "abas YP74A"}


@app.get("/api/emitens")
async def get_emitens():
    """Return active tickers and company names for the search autocomplete dropdown."""
    try:
        api = IDXApi()
        emitens = api.get_emitens()
        return [{"ticker": e["KodeEmiten"], "name": e["NamaEmiten"]} for e in emitens]
    except Exception as e:
        return []


@app.post("/api/scrape")
async def scrape_company(req: ScrapeRequest):
    """Run full scraping, normalization, and modeling for a given ticker."""
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Stock ticker is required.")

    scraper = IDXFinancialScraper(output_dir=DOWNLOADS_DIR)

    try:
        if req.mode == "custom" and req.years:
            res = scraper.build_ready_to_forecast(ticker=ticker, years=req.years)
        else:
            # Default: Dynamic Horizon Case A (5 Annual + Latest Interim Quarters)
            res = scraper.build_latest_ready_to_forecast(ticker=ticker)

        if not res or res.get("status") != "success":
            raise HTTPException(status_code=500, detail=res.get("message", f"Could not process filings for {ticker}"))

        return serialize_model_result(res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{ticker}")
async def download_excel(ticker: str):
    """Download the generated Ready-to-Forecast Excel workbook for the ticker."""
    ticker_clean = ticker.strip().upper()
    ticker_dir = os.path.join(DOWNLOADS_DIR, ticker_clean)
    if not os.path.exists(ticker_dir):
        raise HTTPException(status_code=404, detail=f"No data directory found for {ticker_clean}")

    # Look for the most recent ReadyToForecast Excel file
    excel_files = [
        os.path.join(ticker_dir, f) for f in os.listdir(ticker_dir)
        if "ReadyToForecast" in f and f.endswith(".xlsx") and not f.startswith("~$")
    ]

    if not excel_files:
        raise HTTPException(status_code=404, detail=f"No ReadyToForecast Excel model found for {ticker_clean}")

    excel_files.sort(key=os.path.getmtime, reverse=True)
    latest_file = excel_files[0]
    filename = os.path.basename(latest_file)

    return FileResponse(
        path=latest_file,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.post("/api/upload")
async def upload_offline_files(files: List[UploadFile] = File(...)):
    """Accept uploaded financial statement files (.xlsx or .zip), ingest offline, and return parsed model."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    temp_upload_dir = tempfile.mkdtemp(prefix="idx_web_upload_")
    try:
        saved_paths = []
        for file in files:
            safe_name = os.path.basename(file.filename)
            dest_path = os.path.join(temp_upload_dir, safe_name)
            with open(dest_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_paths.append(dest_path)

        scraper = IDXFinancialScraper(output_dir=DOWNLOADS_DIR)
        results = scraper.process_local_folder(temp_upload_dir)

        if not results:
            raise HTTPException(status_code=400, detail="Could not identify valid financial statements from uploaded files.")

        # Return the first successfully processed company
        first_success = next((r for r in results if r.get("status") == "success"), None)
        if not first_success:
            raise HTTPException(status_code=500, detail="Processing failed for uploaded statements.")

        return serialize_model_result(first_success)
    finally:
        shutil.rmtree(temp_upload_dir, ignore_errors=True)


def open_browser():
    """Open default web browser after server starts."""
    webbrowser.open_new_tab("http://127.0.0.1:8000")


def start_server():
    """Start web server and auto-open browser."""
    print("=" * 72)
    print("     IDX FINANCIAL STATEMENT & READY-TO-FORECAST MODELING ENGINE     ")
    print("                     Interactive Web Dashboard                       ")
    print("                       Created by: abas YP74A                         ")
    print("=" * 72)
    print("\n[+] Starting Web Server at: http://127.0.0.1:8000")
    print("[+] Opening your web browser automatically...")
    print("[+] Press Ctrl+C in this terminal to stop the server.\n")

    threading.Timer(1.2, open_browser).start()

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    start_server()
