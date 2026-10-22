# IDX Financial Statement Scraper & Ready-to-Forecast Pro Forma Data Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

An automated, high-fidelity financial statement scraper, taxonomy normalizer, and operational driver engine for **PT Bursa Efek Indonesia (Indonesia Stock Exchange / IDX - `idx.co.id`)**.

It scrapes **5+ historical years (e.g. 2020–2024+)** of audited annual filings, overcomes Cloudflare Turnstile anti-bot protections, resolves complex Indonesian accounting taxonomies across different sectors, and exports an unspeculative, modeling-ready 5-tab Excel spreadsheet normalized to **Millions IDR (Juta Rupiah)** with a mathematically balanced Balance Sheet ($\text{Assets} = \text{Liabilities} + \text{Equity}$).

---

## Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │             IDX Primary REST API              │
                      │     /primary/ListedCompany/GetFinancialReport │
                      └───────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │ Standardized Excel File │                     │    XBRL Instance Zip    │
         │ FinancialStatement.xlsx │                     │       instance.zip      │
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │                                               │
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │ 4-Tier Waterfall Parser │                     │    XBRL Direct Parser   │
         │   (excel_parser.py)     │                     │     (xbrl_parser.py)    │
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                              ┌───────────────────────────────┐
                              │   FinancialNormalizer Engine  │
                              │ • Scale to Millions IDR       │
                              │ • Mathematical Balance Check  │
                              │ • Dana Syirkah Temporer       │
                              └───────────────┬───────────────┘
                                              ▼
                              ┌───────────────────────────────┐
                              │    DriverCalculator Engine    │
                              │ • DSO, DIO, DPO Days          │
                              │ • Gross, Opex, Net Margins    │
                              │ • Capex % Rev, D&A % PP&E     │
                              │ • 3-Yr Median & 5-Yr Average  │
                              └───────────────┬───────────────┘
                                              ▼
                              ┌───────────────────────────────┐
                              │    5-Tab Ready-to-Forecast    │
                              │     Excel Model (.xlsx)       │
                              └───────────────────────────────┘
```

---

## Key Features & Accounting Problem Solved

### 1. Cloudflare Turnstile / Managed Challenge Bypass
Standard scrapers (`requests`, `urllib`, `aiohttp`) trigger HTTP 403 Forbidden due to Cloudflare Turnstile bot detection on IDX's portal. This tool utilizes `curl_cffi` with browser TLS fingerprinting (JA3) and HTTP/2 spoofing (`impersonate="chrome131"`), achieving seamless HTTP 200 responses.

### 2. Dual-Source Ingestion Architecture
- **Primary Engine (`XBRLParser`)**: Ingests the official raw XBRL instance (`instance.xbrl` inside `instance.zip`). Elements carry canonical taxonomy concepts (e.g., `SalesAndRevenue`, `TradeReceivablesNet`, `Assets`) regardless of Excel spacing or UI language toggles, and report in Full IDR (eliminating multi-year scale discrepancies).
- **Fallback Engine (`FinancialNormalizer`)**: A robust 4-tier waterfall parser that inspects multi-taxonomy Excel sheets (`1210000`, `1321000`, `3210000`, `4220000`), resolving parent summary rows, child account aggregations, and rounding metadata.

### 3. Conglomerate Disaggregation Fix (e.g. ASII)
In conglomerates like Astra International (ASII), Excel summary rows for Revenue were left blank due to segment disaggregation. Direct XBRL ingestion accesses the unfragmented macro tag `<idx-cor:SalesAndRevenue contextRef="CurrentYearDuration">`, capturing full revenue across all 5 years without gaps.

### 4. Sharia Windows & Islamic Banking (`Dana Syirkah Temporer`)
Conventional banks with Sharia windows (BBCA, BMRI) report `Dana Syirkah Temporer` between Liabilities and Equity ($Assets = Liabilities + Syirkah + Equity$). Syirkah funds are automatically consolidated into Total Liabilities, guaranteeing that:
$$\text{Balance Check} = \text{Total Assets} - (\text{Total Liabilities} + \text{Total Equity}) == \mathbf{0.00}$$

### 5. Infrastructure & Telecom By-Nature Accounting (e.g. TLKM)
Companies that report expenses by nature (interconnection, network operations, personnel) rather than by function do not break out COGS. The engine dynamically computes Operating Income (EBIT) and EBITDA from nature-based operating expenses and D&A.

### 6. Historical Operational Driver Computation
To build your own pro forma model without speculative projections, the tool computes standard operational drivers for every historical year, including:
- **Working Capital Efficiency**: Days Sales Outstanding (DSO), Days Inventory Outstanding (DIO), Days Payable Outstanding (DPO).
- **Profitability Margins**: Gross Margin, SG&A / Opex % Rev, EBITDA Margin, Operating Margin, Net Margin, Effective Tax Rate.
- **Fixed Capital & Dividends**: Capex % of Revenue, D&A % of Net PP&E, Dividend Payout Ratio.
- **Statistical Benchmarks**: **3-Year Medians** and **5-Year Averages** for baseline forecasting inputs.

---

## Directory Structure

```
Project_scrapping/
├── requirements.txt
├── README.md
├── main.py                                  # CLI and Interactive Entry Point
├── idx_scraper/
│   ├── __init__.py
│   ├── client.py                            # TLS-spoofed HTTP Client with rate-limiting
│   ├── api.py                               # Typed IDX REST API Endpoints
│   ├── excel_parser.py                      # Multi-taxonomy sheet finder & Excel parser
│   ├── xbrl_parser.py                       # Canonical XBRL instance document parser
│   ├── multi_year.py                        # Multi-year table compiler
│   ├── scraper.py                           # High-level pipeline coordinator
│   └── proforma/
│       ├── __init__.py
│       ├── schema.py                        # Dataclasses (IS, BS, CF, Drivers)
│       ├── normalizer.py                    # 4-tier waterfall resolution engine
│       ├── drivers.py                       # Operational drivers & benchmark statistics
│       └── export_ready.py                  # 5-tab Excel workbook exporter
└── downloads/
    └── {TICKER}/
        ├── {YEAR}/
        │   ├── FinancialStatement-{YEAR}-Tahunan-{TICKER}.xlsx
        │   └── instance.zip
        ├── {TICKER}_financial_statements_{START}_{END}.xlsx       (Raw compiled tables)
        └── {TICKER}_ReadyToForecast_Financials_{START}_{END}.xlsx (5-Tab Ready-to-Forecast Model)
```

---

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/celeebi/IDX_GetFinancialStatement.git
   cd IDX_GetFinancialStatement
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage Guide

### 1. Ready-to-Forecast Financial Model (Recommended)
Extracts financial statements for any time horizon, computes operational drivers, and exports a 5-tab Excel workbook:

```bash
# 1. Single Year Extraction (e.g. 2023 only)
python main.py --ticker ASII --year 2023 --ready-to-forecast

# 2. Custom Sub-Range (e.g. 3 years: 2021-2023)
python main.py --ticker TLKM --years 2021-2023 --ready-to-forecast

# 3. Disjoint / Non-Contiguous Selection (e.g. alternate years)
python main.py --ticker ASII --years 2020,2022,2024 --ready-to-forecast

# 4. All Available Historical Data (Automatic Discovery on IDX)
python main.py --ticker BBCA --all --ready-to-forecast

# 5. Standard 5-Year Horizon (2020-2024)
python main.py --ticker BBCA --years 2020-2024 --ready-to-forecast
```

### 2. Interactive Terminal Mode
Run without arguments to launch the interactive prompt with smart year parsing:
```bash
python main.py
```
At the prompt, you can enter any year expression:
- `2023` $\to$ pulls only 2023
- `2020-2023` $\to$ pulls 2020 through 2023
- `2019, 2021, 2023` $\to$ pulls specific years
- `all` $\to$ auto-probes and extracts all published years
- Pressing `Enter` $\to$ defaults to standard `2020-2024`

### 3. Search Listed Companies
Find tickers or verify company names across 960+ listed companies on IDX:
```bash
python main.py --search bank
python main.py --search telekomunikasi
python main.py --search "astra"
```

### 4. Raw Multi-Year Table Compilation Only
Downloads standardized Excel filings and compiles side-by-side comparative tables without normalization:
```bash
python main.py --ticker BBRI --start-year 2020 --end-year 2024
```

---

## Verified Multi-Sector Benchmarks (2020–2024)

### 1. Astra International Tbk (`ASII`) — Conglomerate
- **Revenue (Millions IDR)**:
  - `2020`: 175,046,000 M (175.0T)
  - `2021`: 233,485,000 M (233.5T)
  - `2022`: 301,379,000 M (301.4T)
  - `2023`: 316,565,000 M (316.6T)
  - `2024`: 330,920,000 M (330.9T)
- **Gross Margin**: 22.0% $\to$ 21.9% $\to$ 23.3% $\to$ 23.2% $\to$ 22.2% (**3-Yr Median: 23.2%**)
- **Working Capital Days**: DSO 32.2 days | DIO 50.5 days | DPO 59.4 days
- **Capex (% of Revenue)**: 2.4% (2020) $\to$ 4.4% (2024) (**5-Yr Avg: 3.7%**)
- **Balance Sheet Check**: **0.00 across all 5 years (2020–2024)**

### 2. Telkom Indonesia Tbk (`TLKM`) — Telecom & Infrastructure
- **Revenue (Millions IDR)**:
  - `2020`: 136,462,000 M (136.5T)
  - `2021`: 143,210,000 M (143.2T)
  - `2022`: 147,306,000 M (147.3T)
  - `2023`: 149,216,000 M (149.2T)
  - `2024`: 149,967,000 M (150.0T)
- **Operating Margin (EBIT %)**: 31.6% $\to$ 30.7% $\to$ 31.0% $\to$ 30.1% $\to$ 28.3% (**3-Yr Median: 30.1%**)
- **Capex (% of Revenue)**: 21.7% $\to$ 20.7% $\to$ 23.9% $\to$ 22.5% $\to$ 17.3% (**5-Yr Avg: 21.2%**)
- **D&A (% of Net PP&E)**: 18.0% $\to$ 19.3% $\to$ 19.2% $\to$ 18.1% $\to$ 15.7% (**3-Yr Median: 18.1%**)
- **Dividend Payout Ratio**: 77.9% $\to$ 88.0% $\to$ 90.2% $\to$ 82.0% $\to$ 80.6% (**3-Yr Median: 82.0%**)
- **Balance Sheet Check**: **0.00 across all 5 years (2020–2024)**

### 3. Bank Central Asia Tbk (`BBCA`) — Banking & Sharia Window
- **Interest & Sharia Income (Millions IDR)**:
  - `2020`: 65,403,161 M (65.4T)
  - `2021`: 65,626,976 M (65.6T)
  - `2022`: 72,241,191 M (72.2T)
  - `2023`: 87,397,774 M (87.4T)
  - `2024`: 94,796,454 M (94.8T)
- **Net Income**: 27.1T (2020) $\to$ 54.9T (2024)
- **Balance Sheet (2024)**:
  - Assets: 1,449,301,328 M
  - Liabilities: 1,177,403,108 M
  - Dana Syirkah Temporer: 9,063,133 M
  - Equity: 262,835,087 M
  - **Equation**: $1,449,301,328 - (1,177,403,108 + 9,063,133 + 262,835,087) = \mathbf{0.00}$
- **Balance Sheet Check**: **0.00 across all 5 years (2020–2024)**

---

## 5-Tab Excel Workbook Structure

When using `--ready-to-forecast`, the output file `{TICKER}_ReadyToForecast_Financials_2020_2024.xlsx` contains:

| Tab Name | Purpose & Contents |
| :--- | :--- |
| **`Historical_IS`** | Clean multi-year Income Statement: Revenue, COGS, Gross Profit, SG&A / Opex, EBITDA, D&A, EBIT, Net Finance, EBT, Tax, and Net Income. |
| **`Historical_BS`** | Standardized Balance Sheet: Working Capital, Cash, PP&E, Debt, Equity, and **Balance Check ($Assets - Liab - Eq = 0.00$)**. |
| **`Historical_CF`** | Cash Flow Statement: Operating Cash Flow (CFO), Capex (CFI), Dividends, Net Debt changes, Beginning and Ending Cash. |
| **`Forecasting_Drivers`** | Historical operating drivers ($\text{DSO}, \text{DIO}, \text{DPO}$, Margins, Capex intensity, D&A % PP&E, Dividend Payout) + **3-Year Medians & 5-Year Averages**. |
| **`General_Info`** | Entity metadata, sector, subsector, presentation currency, auditor opinions, and Key Audit Matters. |

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
