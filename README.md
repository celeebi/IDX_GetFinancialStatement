# IDX Financial Statement Scraper & Ready-to-Forecast Modeling Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

An automated financial statement scraper, sector-aware normalizer, and operational driver engine for **PT Bursa Efek Indonesia (Indonesia Stock Exchange / IDX - `idx.co.id`)**.

Built specifically for **equity research analysts, finance students, and investment modelers**, this tool eliminates hours of manual data entry from messy IDX filings and instantly delivers clean, standardized 3-statement financials and forecasting drivers.

---

## Why Use This Tool?

Building 3-statement financial models, DCF valuations, or equity research notes for Indonesian companies is traditionally painful:
- IDX publishes filings in inconsistent formats across different years.
- Excel layouts shift, line items disappear into disaggregated notes, and numbers are reported in varying units (Rupiah, Thousands, Millions, Billions).
- Financial institutions (banks, insurance, multifinance) follow completely different accounting structures than general corporates.

**This engine solves all of that in a single command.** Enter a stock ticker (e.g., `ASII`, `BBCA`, `TLKM`) and get an instant, normalized 3-statement financial model with pre-calculated operational drivers—both in your terminal and exported to a presentation-ready 5-tab Excel spreadsheet.

---

## Key Features for Financial Analysts

### 1. Instant 3 Financial Statements
Pulls and standardizes the complete financial triad:
- **Consolidated Income Statement**
- **Consolidated Balance Sheet**
- **Consolidated Cash Flow Statement**

All figures are automatically detected, normalized, and scaled to **Millions IDR (Juta Rupiah)** for clean, readable analysis.

### 2. Sector-Aware Modeling (Corporate vs. Banking)
Traditional corporate models (which focus on COGS, Gross Profit, and inventory turns) mathematically break down for financial institutions. The engine automatically detects the company's sector from filing metadata and applies the appropriate financial framework:

| Financial Dimension | Non-Financial Corporates (ASII, TLKM, ICBP, UNTR) | Financial Institutions & Banks (BBCA, BBRI, BMRI, BFIN) |
| :--- | :--- | :--- |
| **Primary Revenue** | Gross Sales & Revenue | Net Interest Income (NII) & Fee Income |
| **Cost Structure** | Cost of Goods Sold (COGS) & Operating Expenses | Interest Expense & Cost of Funds (CoF) |
| **Profitability Metrics**| Gross Profit, EBITDA, Operating Profit (EBIT) | Pre-Provision Operating Profit (PPOP), Net Income |
| **Operating Assets** | Trade Receivables, Inventories, Net PP&E | Earning Assets, Placements with BI, Gross & Net Loans |
| **Operating Liabilities**| Trade Payables, Short & Long-Term Debt | Customer Deposits (DPK: Giro, Tabungan, Deposito) |
| **Working Capital** | Working Capital Days (DSO, DIO, DPO) | Loan-to-Deposit Ratio (LDR), CASA Ratio (%) |
| **Risk & Quality** | Debt-to-EBITDA, Interest Coverage | Credit Cost / Provisioning Rate (CKPN %), CIR / BOPO |

### 3. Guaranteed Balance Sheet Integrity ($\Delta = \mathbf{0.00}$)
Never worry about out-of-balance models:
$$\text{Total Assets} - (\text{Total Liabilities} + \text{Total Equity}) == \mathbf{0.00}$$
For conventional banks with Islamic banking windows (e.g., BBCA, BMRI), `Dana Syirkah Temporer` is automatically reconciled, ensuring perfect accounting balance across all years.

### 4. Ready-to-Forecast Operational Drivers
To jumpstart your pro forma projections and DCF valuation without guesswork, the engine computes historical operational drivers for every period:
- **Corporate Drivers**: Revenue Growth (YoY), Gross Margin %, SG&A % Rev, Operating Margin %, Days Sales Outstanding (DSO), Days Inventory Outstanding (DIO), Days Payable Outstanding (DPO), Capex % of Revenue, D&A % of Net PP&E, Dividend Payout Ratio.
- **Banking Drivers**: Loan Growth (YoY), Deposit Growth (YoY), Net Interest Margin (NIM %), Cost of Funds (CoF %), Loan-to-Deposit Ratio (LDR %), CASA Ratio (%), Cost-to-Income / BOPO (CIR %), Credit Cost / Provisioning Rate (%), ROA %, ROE %, Equity-to-Assets %.
- **Statistical Baselines**: Automatically computes **3-Year Medians** and **Historical Averages** to serve as baseline inputs for your forecast assumptions.

### 5. Flexible Historical Horizons
Analyze whatever historical period your valuation requires:
- **Single Year**: Pull just 2023 (`--year 2023`).
- **Sub-Range**: Pull a 3-year period (`--years 2021-2023`).
- **Disjoint Selection**: Pull alternate or specific years (`--years 2018,2021,2024`).
- **Full Historical Archive**: Probe and extract every online filing published on IDX (`--all`).
- **Standard 5-Year Horizon**: Default 5-year analysis (`2020-2024`).

### 6. Professional 5-Tab Excel Financial Model
Generates a formatted workbook styled for financial presentation:
- `Historical_IS`: Consolidated Income Statement.
- `Historical_BS`: Consolidated Balance Sheet with balance check validation.
- `Historical_CF`: Consolidated Cash Flow Statement (Operating, Investing, Financing).
- `Forecasting_Drivers`: Historical ratios, working capital metrics, 3-Yr Medians & Averages.
- `General_Info`: Company profile, sector, presentation currency, and auditor opinions.

---

## Quick Start Guide

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/celeebi/IDX_GetFinancialStatement.git
cd IDX_GetFinancialStatement

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Interactive Mode
Run the tool without arguments for a guided prompt:
```bash
python main.py
```
Simply enter a stock ticker (e.g. `BBCA`, `ASII`, `TLKM`) and your desired year horizon (e.g. `2020-2024`, `2023`, or `all`).

---

## Practical CLI Usage Examples

### 1. Ready-to-Forecast Model (Recommended)
Generate the complete 3-statement model and forecasting drivers:

```bash
# Analyze Bank Central Asia (BBCA) over a 5-year horizon (2020-2024)
python main.py --ticker BBCA --years 2020-2024 --ready-to-forecast

# Analyze Astra International (ASII) for a 3-year sub-range
python main.py --ticker ASII --years 2021-2023 --ready-to-forecast

# Analyze Telkom Indonesia (TLKM) for a single specific year
python main.py --ticker TLKM --year 2023 --ready-to-forecast

# Pull all available historical years published on IDX
python main.py --ticker BBCA --all --ready-to-forecast
```

### 2. Search Listed Companies
Find tickers or verify company names across 960+ listed companies on IDX:
```bash
python main.py --search "bank"
python main.py --search "telekomunikasi"
python main.py --search "astra"
```

### 3. Raw Table Compilation Only
If you only need raw multi-year tables without normalization:
```bash
python main.py --ticker BBRI --years 2021-2023
```

---

## 5-Tab Excel Workbook Layout

When running `--ready-to-forecast`, the output file `{TICKER}_ReadyToForecast_Financials_{YEARS}.xlsx` contains:

| Tab Name | Contents & Purpose |
| :--- | :--- |
| **`Historical_IS`** | Clean multi-year Income Statement with bold subtotals (Gross Profit, EBITDA, EBIT, EBT, Net Income for Corporates; NII, Fee Income, Opex, PPOP, Net Income for Banks). |
| **`Historical_BS`** | Standardized Balance Sheet with an automated **Balance Check ($Assets - Liab - Eq = 0.00$)** highlighted in green. |
| **`Historical_CF`** | Cash Flow Statement: Operating Cash Flow (CFO), Capital Expenditures / Investing (CFI), Dividends Paid, Financing (CFF), and Ending Cash. |
| **`Forecasting_Drivers`** | Pre-calculated operational modeling drivers, margins, working capital efficiency days, and **3-Year Medians & Historical Averages**. |
| **`General_Info`** | Corporate metadata, sector classification, auditor name, and presentation currency. |

---

## Directory Structure

```
Project_scrapping/
├── main.py                                  # CLI and Interactive Entry Point
├── requirements.txt
├── README.md
├── idx_scraper/
│   ├── client.py                            # Rate-limited HTTP client with TLS fingerprinting
│   ├── api.py                               # Typed IDX REST API Endpoints
│   ├── scraper.py                           # High-level pipeline coordinator
│   ├── year_utils.py                        # Flexible year range parsing engine
│   ├── excel_parser.py                      # Multi-taxonomy sheet finder & Excel parser
│   ├── xbrl_parser.py                       # Canonical XBRL instance document parser
│   ├── multi_year.py                        # Multi-year table compiler
│   └── proforma/
│       ├── dispatcher.py                    # Sector & Archetype auto-detection
│       ├── schema.py                        # Corporate & Banking COA dataclasses
│       ├── normalizer.py                    # Multi-tier waterfall normalization engine
│       ├── drivers.py                       # Operational driver & benchmark calculator
│       └── export_ready.py                  # 5-tab ready-to-forecast Excel builder
└── downloads/
    └── {TICKER}/
        ├── {YEAR}/
        │   ├── FinancialStatement-{YEAR}-Tahunan-{TICKER}.xlsx
        │   └── instance.zip
        ├── {TICKER}_financial_statements_{YEARS}.xlsx       (Raw compiled tables)
        └── {TICKER}_ReadyToForecast_Financials_{YEARS}.xlsx (5-Tab Ready-to-Forecast Model)
```

---

## Under the Hood

For technical contributors and developers interested in the underlying pipeline:
- **Primary XBRL Ingestion**: The engine directly reads the raw `instance.xbrl` document from IDX's filing package. XBRL concepts carry fixed semantic tags (e.g. `SalesAndRevenue`, `TotalInterestAndShariaIncome`, `Assets`), completely bypassing Excel spacing changes, cell shifts, or UI language differences.
- **Anti-Bot Handling**: IDX's portal uses Cloudflare Turnstile protection. Requests are executed through `curl_cffi` using browser TLS fingerprint simulation (`impersonate="chrome131"`) and automatic retry backoff, ensuring uninterrupted data extraction.
- **Unit Normalization**: Detects filing scale metadata (`Satuan Penuh`, `Ribuan`, `Jutaan`, `Miliaran`) and converts all statements into a consistent **Millions IDR** denomination.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
