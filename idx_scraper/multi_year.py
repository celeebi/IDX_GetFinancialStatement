"""
Multi-year financial statement compiler.
Combines annual financial statements across 5+ years into a single consolidated comparison table.
"""

from typing import List, Dict, Any, Optional
import re
import pandas as pd
import logging
from .year_utils import period_sort_key

logger = logging.getLogger("idx_scraper.multi_year")


def extract_year_from_column_header(header: str, report_year: Optional[int] = None) -> Optional[int]:
    """Extract a 4-digit year from a column header like '31 December 2023', '2023', or XBRL tags."""
    h_str = str(header).strip()
    m = re.search(r'\b(20\d{2})\b', h_str)
    if m:
        return int(m.group(1))

    # Check for XBRL context names if report_year is available
    if report_year:
        h_lower = h_str.lower()
        if "current" in h_lower:
            return report_year
        elif "prior" in h_lower:
            return report_year - 1

    return None


def merge_statement_tables(parsed_reports: List[Dict[str, Any]], statement_type: str = "balance_sheet") -> pd.DataFrame:
    """
    Merge a specific financial statement (balance_sheet, income_statement, cash_flow)
    across multiple years into a unified multi-year table.
    
    Returns DataFrame:
    Item_ID | Item_EN | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 ...
    """
    if not parsed_reports:
        return pd.DataFrame()

    # Collect all items and their yearly/period values
    master_items: Dict[str, Dict[str, Any]] = {}
    periods_found = set()

    for report in parsed_reports:
        report_year = report.get("year")
        period_key = report.get("period_key") or (str(report_year) if report_year else None)
        df: pd.DataFrame = report.get(statement_type, pd.DataFrame())
        if df.empty or "Item_ID" not in df.columns:
            continue

        value_cols = [c for c in df.columns if c not in ("Item_ID", "Item_EN")]

        for _, row in df.iterrows():
            item_id = str(row["Item_ID"]).strip()
            item_en = str(row.get("Item_EN", "")).strip()
            if not item_id:
                continue

            if item_id not in master_items:
                master_items[item_id] = {
                    "Item_ID": item_id,
                    "Item_EN": item_en,
                    "values_by_year": {}
                }
            elif item_en and not master_items[item_id]["Item_EN"]:
                master_items[item_id]["Item_EN"] = item_en

            for col in value_cols:
                val = row[col]
                # If report has explicit interim period key (e.g. 2025-Q2)
                if period_key and ("-q" in str(period_key).lower() or "_tw" in str(period_key).lower()):
                    p_target = period_key
                else:
                    yr = extract_year_from_column_header(col, report_year=report_year)
                    p_target = str(yr) if yr else None

                if p_target and pd.notna(val):
                    periods_found.add(p_target)
                    master_items[item_id]["values_by_year"][p_target] = val

    if not master_items:
        return pd.DataFrame()

    sorted_periods = sorted(list(periods_found), key=period_sort_key)
    rows = []
    for item_data in master_items.values():
        row_dict = {
            "Item_ID": item_data["Item_ID"],
            "Item_EN": item_data["Item_EN"]
        }
        for p in sorted_periods:
            row_dict[str(p)] = item_data["values_by_year"].get(p, None)
        rows.append(row_dict)

    result_df = pd.DataFrame(rows)
    return result_df
