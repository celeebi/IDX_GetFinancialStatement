"""
Year specification and historical availability utilities.
Parses user year expressions (single, range, lists, 'all') and
probes IDX for available historical filing years.
"""

import re
import datetime
import logging
from typing import List, Optional, Union, Any

logger = logging.getLogger("idx_scraper.year_utils")


def parse_year_input(spec: Optional[str]) -> Optional[List[int]]:
    """
    Parse a user-supplied year specification string into a sorted list of integer years.
    Returns:
        List[int] if specific years are specified.
        ['ALL'] if user requested all available historical years.
        None if empty or invalid (caller should use default).
    
    Supported formats:
        - "2023"                -> [2023]
        - "2020-2023"           -> [2020, 2021, 2022, 2023]
        - "2020 - 2024"         -> [2020, 2021, 2022, 2023, 2024]
        - "2019, 2021, 2023"    -> [2019, 2021, 2023]
        - "all" / "max"         -> ['ALL']
    """
    if spec is None:
        return None

    spec_clean = str(spec).strip().lower()
    if not spec_clean:
        return None

    # Check for 'all' / 'max' keywords
    if spec_clean in ("all", "max", "full", "everything"):
        return ["ALL"]  # Sentinel for auto-probing all years

    # Check for range: "2020-2023" or "2020 - 2023" or "2020 to 2023"
    range_match = re.match(r"^(\d{4})\s*(?:[-–—]|to)\s*(\d{4})$", spec_clean)
    if range_match:
        y1, y2 = int(range_match.group(1)), int(range_match.group(2))
        start_y = min(y1, y2)
        end_y = max(y1, y2)
        return list(range(start_y, end_y + 1))

    # Check for single year: "2023"
    if spec_clean.isdigit() and len(spec_clean) == 4:
        return [int(spec_clean)]

    # Check for delimiter-separated list: "2019, 2021, 2023" or "2019 2021 2023"
    parts = re.split(r"[,;\s]+", spec_clean)
    years = []
    for p in parts:
        if p.isdigit() and len(p) == 4:
            years.append(int(p))

    if years:
        return sorted(list(set(years)))

    return None


def format_year_range_slug(years: List[int]) -> str:
    """
    Generate a clean URL/filename slug for a list of years.
    - [2023]                        -> "2023"
    - [2020, 2021, 2022, 2023]       -> "2020_2023"
    - [2019, 2021, 2023]             -> "2019_2021_2023"
    """
    if not years:
        return "financials"

    sorted_years = sorted(years)
    if len(sorted_years) == 1:
        return str(sorted_years[0])

    # Check if contiguous range
    is_contiguous = (sorted_years[-1] - sorted_years[0] + 1) == len(sorted_years)
    if is_contiguous:
        return f"{sorted_years[0]}_{sorted_years[-1]}"

    # Non-contiguous
    return "_".join(str(y) for y in sorted_years)


def format_year_range_label(years: List[int]) -> str:
    """
    Generate a human-readable display label for a list of years.
    - [2023]                  -> "Year 2023"
    - [2020, 2021, 2022, 2023]-> "2020 - 2023 (4 Years)"
    - [2019, 2021, 2023]       -> "2019, 2021, 2023 (3 Selected Years)"
    """
    if not years:
        return ""
    sorted_years = sorted(years)
    if len(sorted_years) == 1:
        return f"Year {sorted_years[0]}"

    is_contiguous = (sorted_years[-1] - sorted_years[0] + 1) == len(sorted_years)
    if is_contiguous:
        return f"{sorted_years[0]} - {sorted_years[-1]} ({len(sorted_years)} Years)"

    return f"{', '.join(str(y) for y in sorted_years)} ({len(sorted_years)} Selected Years)"


def probe_available_filing_years(
    api: Any,
    ticker: str,
    min_year: int = 2015,
    max_year: Optional[int] = None
) -> List[int]:
    """
    Probe IDX primary REST API to identify all historical annual filings
    published for a given emiten.
    """
    ticker_clean = ticker.strip().upper()
    current_year = datetime.datetime.now().year
    if max_year is None:
        max_year = current_year

    print(f"[+] Probing IDX online database for all available filings of {ticker_clean} ({min_year} - {max_year})...")
    found_years = []

    for yr in range(max_year, min_year - 1, -1):
        try:
            res = api.get_financial_reports(year=yr, period="audit", kode_emiten=ticker_clean, page=1, page_size=2)
            results = res.get("Results", [])
            if results:
                found_years.append(yr)
            else:
                # If we've already found some recent filings and hit 3 consecutive empty years, we can stop probing
                if len(found_years) >= 2 and yr < 2019:
                    break
        except Exception as e:
            logger.debug(f"Probing error for {ticker_clean} {yr}: {e}")

    found_years.sort()
    if found_years:
        print(f"[+] Found {len(found_years)} online filing years for {ticker_clean}: {found_years}")
    else:
        print(f"[-] No annual filings found online for {ticker_clean}.")

    return found_years
