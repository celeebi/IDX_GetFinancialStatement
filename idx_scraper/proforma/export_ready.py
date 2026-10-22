"""
Excel Export Engine for Ready-to-Forecast Financials.
Generates a beautifully formatted, multi-tab Excel workbook:
- Historical_IS
- Historical_BS (with Balance Check)
- Historical_CF
- Forecasting_Drivers (with 3-Year Medians & 5-Year Averages)
- General_Info
"""

import os
import logging
from typing import Dict, Any, List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .schema import (
    NormalizedIS, NormalizedBS, NormalizedCF, OperationalDrivers,
    BankingIS, BankingBS, BankingCF, BankingDrivers
)
from .drivers import DriverCalculator, BankingDriverCalculator

logger = logging.getLogger("idx_scraper.proforma.export_ready")


class ReadyToForecastExporter:
    """Exports normalized statements and historical drivers into an Excel workbook."""

    # Styling presets
    NAVY_HEADER = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    ACCENT_FILL = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    HIGHLIGHT_FILL = PatternFill(start_color="EBF1DE", end_color="EBF1DE", fill_type="solid")
    ALERT_GREEN = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    ALERT_RED = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    FONT_BOLD = Font(name="Calibri", size=10, bold=True)
    FONT_NORMAL = Font(name="Calibri", size=10)
    FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="1F497D")
    FONT_SUBTITLE = Font(name="Calibri", size=10, italic=True, color="595959")

    BORDER_THIN = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )
    BORDER_DOUBLE_BOTTOM = Border(
        top=Side(style="thin", color="595959"),
        bottom=Side(style="double", color="1F497D")
    )

    @classmethod
    def export(
        cls,
        dest_path: str,
        ticker: str,
        years: List[int],
        is_dict: Dict[int, Any],
        bs_dict: Dict[int, Any],
        cf_dict: Dict[int, Any],
        drivers_by_year: Dict[int, Any],
        general_info: Dict[str, str] = {},
        archetype: str = "corporate"
    ):
        """Build and save the 5-tab ready-to-forecast workbook for Corporate or Banking archetype."""
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        wb = openpyxl.Workbook()

        sorted_years = sorted(years)
        if archetype == "banking":
            benchmarks = BankingDriverCalculator.build_summary_benchmarks(drivers_by_year)
        else:
            benchmarks = DriverCalculator.build_summary_benchmarks(drivers_by_year)

        n_years = len(sorted_years)
        time_desc = "Annual Financial Statement" if n_years == 1 else f"{n_years}-Year Historical Statements"
        stmt_subtitle = f"Normalized {time_desc} (Amounts in Millions IDR / Juta Rupiah)"

        # 1. Income Statement Tab
        ws_is = wb.active
        ws_is.title = "Historical_IS"
        if archetype == "banking":
            cls._build_statement_sheet(
                ws=ws_is,
                title=f"{ticker.upper()} - CONSOLIDATED BANKING INCOME STATEMENT",
                subtitle=stmt_subtitle,
                years=sorted_years,
                data_dict={y: is_dict[y].to_dict() for y in sorted_years},
                bold_items=[
                    "Net Interest Income (NII)", "Total Operating Income", "Pre-Provision Operating Profit (PPOP)",
                    "Operating Profit", "Earnings Before Tax (EBT)", "Net Income", "Net Income (Parent Entity)"
                ],
                accent_items=["Net Interest Income (NII)", "Total Operating Income", "Pre-Provision Operating Profit (PPOP)", "Net Income"]
            )
        else:
            cls._build_statement_sheet(
                ws=ws_is,
                title=f"{ticker.upper()} - CONSOLIDATED INCOME STATEMENT",
                subtitle=stmt_subtitle,
                years=sorted_years,
                data_dict={y: is_dict[y].to_dict() for y in sorted_years},
                bold_items=[
                    "Gross Revenue", "Gross Profit", "EBITDA", "Operating Income (EBIT)",
                    "Earnings Before Tax (EBT)", "Net Income", "Net Income (Parent Entity)"
                ],
                accent_items=["Gross Profit", "Operating Income (EBIT)", "Net Income"]
            )

        # 2. Balance Sheet Tab
        ws_bs = wb.create_sheet(title="Historical_BS")
        if archetype == "banking":
            cls._build_statement_sheet(
                ws=ws_bs,
                title=f"{ticker.upper()} - CONSOLIDATED BANKING BALANCE SHEET",
                subtitle=stmt_subtitle,
                years=sorted_years,
                data_dict={y: bs_dict[y].to_dict() for y in sorted_years},
                bold_items=[
                    "Net Loans & Financing", "Total Earning Assets", "TOTAL ASSETS",
                    "Total Customer Deposits (DPK)", "TOTAL LIABILITIES", "TOTAL EQUITY",
                    "TOTAL LIABILITIES, SYIRKAH & EQUITY", "BALANCE CHECK (Assets - Liab&Eq)"
                ],
                accent_items=["Total Earning Assets", "TOTAL ASSETS", "Total Customer Deposits (DPK)", "TOTAL LIABILITIES", "TOTAL EQUITY"]
            )
        else:
            cls._build_statement_sheet(
                ws=ws_bs,
                title=f"{ticker.upper()} - CONSOLIDATED BALANCE SHEET",
                subtitle=stmt_subtitle,
                years=sorted_years,
                data_dict={y: bs_dict[y].to_dict() for y in sorted_years},
                bold_items=[
                    "Total Current Assets", "TOTAL ASSETS", "Total Current Liabilities",
                    "TOTAL LIABILITIES", "TOTAL EQUITY", "TOTAL LIABILITIES & EQUITY",
                    "BALANCE CHECK (Assets - Liab&Eq)"
                ],
                accent_items=["TOTAL ASSETS", "TOTAL LIABILITIES", "TOTAL EQUITY", "TOTAL LIABILITIES & EQUITY"]
            )

        # 3. Cash Flow Tab
        ws_cf = wb.create_sheet(title="Historical_CF")
        cls._build_statement_sheet(
            ws=ws_cf,
            title=f"{ticker.upper()} - CONSOLIDATED CASH FLOW STATEMENT",
            subtitle=stmt_subtitle,
            years=sorted_years,
            data_dict={y: cf_dict[y].to_dict() for y in sorted_years},
            bold_items=[
                "Operating Cash Flow (CFO)", "Investing Cash Flow (CFI)",
                "Financing Cash Flow (CFF)", "Net Change in Cash", "Ending Cash"
            ],
            accent_items=["Operating Cash Flow (CFO)", "Ending Cash"]
        )

        # 4. Drivers Tab
        ws_drv = wb.create_sheet(title="Forecasting_Drivers")
        drv_title = f"{ticker.upper()} - HISTORICAL BANKING DRIVERS & FINANCIAL RATIOS" if archetype == "banking" else f"{ticker.upper()} - HISTORICAL OPERATIONAL DRIVERS & RATIOS"
        drv_subtitle = "Calculated Banking Drivers (NIM %, CoF %, LDR %, CASA %, BOPO/CIR %, Credit Cost %, ROA %, ROE %)" if archetype == "banking" else "Calculated Modeling Drivers, Margins, Working Capital Days & Historical Benchmarks"
        cls._build_drivers_sheet(
            ws=ws_drv,
            title=drv_title,
            subtitle=drv_subtitle,
            years=sorted_years,
            drivers_by_year=drivers_by_year,
            benchmarks=benchmarks
        )

        # 5. General Info Tab
        ws_info = wb.create_sheet(title="General_Info")
        cls._build_info_sheet(ws_info, ticker, general_info)

        wb.save(dest_path)
        logger.info(f"Saved ready-to-forecast workbook to: {dest_path}")

    @classmethod
    def _build_statement_sheet(
        cls,
        ws,
        title: str,
        subtitle: str,
        years: List[int],
        data_dict: Dict[int, Dict[str, float]],
        bold_items: List[str] = [],
        accent_items: List[str] = []
    ):
        """Construct standard financial statement layout."""
        ws.views.sheetView[0].showGridLines = True

        # Titles
        ws["A1"] = title
        ws["A1"].font = cls.FONT_TITLE
        ws["A2"] = subtitle
        ws["A2"].font = cls.FONT_SUBTITLE

        # Header Row
        header_row = 4
        ws.cell(row=header_row, column=1, value="Line Item").font = cls.FONT_HEADER
        ws.cell(row=header_row, column=1).fill = cls.NAVY_HEADER
        ws.cell(row=header_row, column=1).alignment = Alignment(horizontal="left", vertical="center")

        for col_idx, yr in enumerate(years, start=2):
            c = ws.cell(row=header_row, column=col_idx, value=yr)
            c.font = cls.FONT_HEADER
            c.fill = cls.NAVY_HEADER
            c.alignment = Alignment(horizontal="right", vertical="center")

        # Line items
        first_yr = years[0]
        items = list(data_dict[first_yr].keys())

        current_row = 5
        for item in items:
            is_bold = item in bold_items
            is_accent = item in accent_items
            is_check = "BALANCE CHECK" in item

            # Label cell
            lbl_cell = ws.cell(row=current_row, column=1, value=item)
            lbl_cell.font = cls.FONT_BOLD if is_bold else cls.FONT_NORMAL
            lbl_cell.border = cls.BORDER_THIN

            if is_accent:
                lbl_cell.fill = cls.ACCENT_FILL
            elif is_check:
                lbl_cell.fill = cls.HIGHLIGHT_FILL

            # Value cells
            for col_idx, yr in enumerate(years, start=2):
                val = data_dict[yr].get(item, 0.0)
                v_cell = ws.cell(row=current_row, column=col_idx, value=val)
                v_cell.font = cls.FONT_BOLD if is_bold else cls.FONT_NORMAL
                v_cell.number_format = "#,##0;(#,##0);\"-\""
                v_cell.border = cls.BORDER_THIN
                v_cell.alignment = Alignment(horizontal="right")

                if is_accent:
                    v_cell.fill = cls.ACCENT_FILL
                elif is_check:
                    # If check is 0.00 -> green highlight
                    if abs(val) < 0.05:
                        v_cell.fill = cls.ALERT_GREEN
                    else:
                        v_cell.fill = cls.ALERT_RED

            current_row += 1

        # Column widths
        ws.column_dimensions["A"].width = 42
        for col_idx in range(2, len(years) + 2):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 18

    @classmethod
    def _build_drivers_sheet(
        cls,
        ws,
        title: str,
        subtitle: str,
        years: List[int],
        drivers_by_year: Dict[int, OperationalDrivers],
        benchmarks: Dict[str, Dict[str, Optional[float]]]
    ):
        """Construct operational drivers sheet with 3-year median and 5-year average columns."""
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = title
        ws["A1"].font = cls.FONT_TITLE
        ws["A2"] = subtitle
        ws["A2"].font = cls.FONT_SUBTITLE

        # Header Row
        header_row = 4
        n_years = len(years)

        if n_years == 1:
            benchmark_cols = []
        elif n_years == 2:
            benchmark_cols = [("Historical Average", "Historical_Average", cls.ACCENT_FILL)]
        else:
            benchmark_cols = [
                ("3-Yr Median", "3_Year_Median", cls.HIGHLIGHT_FILL),
                ("Historical Average", "Historical_Average", cls.ACCENT_FILL)
            ]

        headers = ["Operational Driver / Ratio"] + [str(y) for y in years] + [b[0] for b in benchmark_cols]

        for col_idx, h_text in enumerate(headers, start=1):
            c = ws.cell(row=header_row, column=col_idx, value=h_text)
            c.font = cls.FONT_HEADER
            c.fill = cls.NAVY_HEADER
            c.alignment = Alignment(horizontal="left" if col_idx == 1 else "right", vertical="center")

        driver_keys = list(next(iter(drivers_by_year.values())).to_dict().keys()) if drivers_by_year else list(OperationalDrivers().to_dict().keys())
        current_row = 5

        for k in driver_keys:
            is_pct = ("(%)" in k or "(% Rev)" in k or "(% Debt)" in k or "(% Cash)" in k or 
                      "NIM" in k or "CoF" in k or "LDR" in k or "CIR" in k or "ROA" in k or "ROE" in k or "Ratio" in k or "Rate" in k or "Growth" in k)
            is_days = "(Days)" in k

            # Label
            lbl = ws.cell(row=current_row, column=1, value=k)
            lbl.font = cls.FONT_BOLD if (is_days or "Growth" in k or "Margin" in k or "NIM" in k or "LDR" in k or "ROA" in k or "ROE" in k or "BOPO" in k) else cls.FONT_NORMAL
            lbl.border = cls.BORDER_THIN

            # Yearly values
            for col_idx, yr in enumerate(years, start=2):
                val = drivers_by_year[yr].to_dict().get(k)
                c = ws.cell(row=current_row, column=col_idx, value=val if val is not None else "")
                c.font = cls.FONT_NORMAL
                c.border = cls.BORDER_THIN
                c.alignment = Alignment(horizontal="right")

                if val is not None:
                    if is_pct:
                        c.number_format = "0.0%"
                    elif is_days:
                        c.number_format = "0.0"
                    else:
                        c.number_format = "0.00"

            # Benchmark columns (if any)
            for b_idx, (b_title, b_key, b_fill) in enumerate(benchmark_cols):
                b_val = benchmarks.get(b_key, {}).get(k)
                bench_cell = ws.cell(row=current_row, column=len(years) + 2 + b_idx, value=b_val if b_val is not None else "")
                bench_cell.font = cls.FONT_BOLD if "Median" in b_title else cls.FONT_NORMAL
                bench_cell.fill = b_fill
                bench_cell.border = cls.BORDER_THIN
                bench_cell.alignment = Alignment(horizontal="right")

                if b_val is not None:
                    bench_cell.number_format = "0.0%" if is_pct else ("0.0" if is_days else "0.00")

            current_row += 1

        # Adjust column widths
        ws.column_dimensions["A"].width = 44
        for col_idx in range(2, len(headers) + 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 16

    @classmethod
    def _build_info_sheet(cls, ws, ticker: str, general_info: Dict[str, str]):
        """Construct company general info and accounting profile sheet."""
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = f"{ticker.upper()} - COMPANY & ACCOUNTING PROFILE"
        ws["A1"].font = cls.FONT_TITLE
        ws["A2"] = "Metadata and corporate classification extracted from IDX filing"
        ws["A2"].font = cls.FONT_SUBTITLE

        ws.cell(row=4, column=1, value="Attribute / Profile Field").font = cls.FONT_HEADER
        ws.cell(row=4, column=1).fill = cls.NAVY_HEADER
        ws.cell(row=4, column=2, value="Details / Value").font = cls.FONT_HEADER
        ws.cell(row=4, column=2).fill = cls.NAVY_HEADER

        default_info = {
            "Stock Ticker": ticker.upper(),
            "Data Unit Scale": "Millions IDR (Juta Rupiah)",
            "Ready-to-Forecast Model Status": "Normalised & Reconciled",
        }
        combined = {**default_info, **general_info}

        current_row = 5
        for k, v in combined.items():
            c1 = ws.cell(row=current_row, column=1, value=str(k))
            c1.font = cls.FONT_BOLD
            c1.border = cls.BORDER_THIN

            c2 = ws.cell(row=current_row, column=2, value=str(v) if v is not None else "")
            c2.font = cls.FONT_NORMAL
            c2.border = cls.BORDER_THIN
            current_row += 1

        ws.column_dimensions["A"].width = 38
        ws.column_dimensions["B"].width = 50
