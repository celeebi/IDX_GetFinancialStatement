"""
Year specification and historical availability utilities.
Parses user year expressions (single, range, lists, 'all') and
probes IDX for available historical filing years.
"""

import re
import datetime
import logging
from typing import List, Optional, Union, Any, Tuple, Dict

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


def period_sort_key(period_key: Union[int, str]) -> Tuple[int, int]:
    """
    Chronological sort key for period representations:
    - 2024 or "2024" -> (2024, 4)  (Annual / Q4)
    - "2025-Q1" / "2025_tw1" -> (2025, 1)
    - "2025-Q2" / "2025_tw2" -> (2025, 2)
    - "2025-Q3" / "2025_tw3" -> (2025, 3)
    - "2025-FY" / "2025" -> (2025, 4)
    """
    s = str(period_key).strip()
    m = re.match(r"^(\d{4})(?:[-_]?(?:q|tw)(\d))?", s, re.IGNORECASE)
    if m:
        year = int(m.group(1))
        q = int(m.group(2)) if m.group(2) else 4
        return (year, q)
    return (9999, 9)


def format_period_label(period_key: Union[int, str]) -> str:
    """
    Human-readable column header for financial statements:
    - 2024 -> "2024"
    - "2025-Q1" -> "2025-Q1 (3M)"
    - "2025-Q2" -> "2025-Q2 (6M)"
    - "2025-Q3" -> "2025-Q3 (9M)"
    """
    s = str(period_key).strip()
    m = re.match(r"^(\d{4})[-_]?(?:q|tw)(\d)", s, re.IGNORECASE)
    if m:
        yr = m.group(1)
        q = int(m.group(2))
        duration_map = {1: "3M", 2: "6M", 3: "9M", 4: "12M"}
        return f"{yr}-Q{q} ({duration_map.get(q, '')})"
    return s


def format_period_slug(periods: List[Any]) -> str:
    """
    Generate clean filename slug for mixed annual and interim periods:
    - [2020..2024, '2025-Q2'] -> "2020_2024_2025Q2"
    """
    if not periods:
        return "financials"
    sorted_p = sorted(periods, key=period_sort_key)
    annuals = [p for p in sorted_p if not re.search(r"[-_]?(?:q|tw)\d", str(p), re.I)]
    interims = [p for p in sorted_p if re.search(r"[-_]?(?:q|tw)\d", str(p), re.I)]

    base_slug = f"{annuals[0]}_{annuals[-1]}" if len(annuals) > 1 else str(annuals[0]) if annuals else ""
    if interims:
        latest_interim = re.sub(r"[-_]", "", str(interims[-1]))
        return f"{base_slug}_{latest_interim}" if base_slug else latest_interim
    return base_slug or "financials"


def is_annual_period(period_key: Union[int, str]) -> bool:
    """Return True if period is an annual fiscal year, False if quarterly/interim."""
    return not bool(re.search(r"[-_]?(?:q|tw)\d", str(period_key), re.IGNORECASE))


def resolve_latest_filing_horizon(
    api: Any,
    ticker: str,
    max_annual_years: int = 5
) -> Dict[str, Any]:
    """
    Dynamically discover the latest reporting horizon for a ticker on IDX (Case A / Dynamic Horizon):
    1. Probe the latest completed annual audited report (e.g. 2024 or 2025).
    2. Collect the last `max_annual_years` annual periods up to that latest annual year.
    3. Check if the unfinished fiscal year (e.g. 2025) has interim quarters published:
       - Probe tw3: if found, interim quarters are tw1, tw2, tw3.
       - Else probe tw2: if found, interim quarters are tw1, tw2.
       - Else probe tw1: if found, interim quarters are [tw1].
       - Else: no interim quarters.
    4. If the newest fiscal year already has an audited annual report published,
       it takes the last 5 completed annual years up to that year.
    """
    import os
    ticker_clean = ticker.strip().upper()
    current_year = datetime.datetime.now().year

    # 1. Probe for latest annual audited filing
    latest_annual = None
    for yr in range(current_year, current_year - 3, -1):
        try:
            res = api.get_financial_reports(year=yr, period="audit", kode_emiten=ticker_clean, page=1, page_size=2)
            if res.get("Results"):
                latest_annual = yr
                break
        except Exception as e:
            logger.debug(f"Error checking annual filing for {ticker_clean} {yr}: {e}")

    # Fallback if probing failed or offline: look in local downloads
    if not latest_annual:
        local_dir = os.path.join("downloads", ticker_clean)
        if os.path.exists(local_dir):
            for f in os.listdir(local_dir):
                if re.match(r"^\d{4}$", f):
                    y_int = int(f)
                    if not latest_annual or y_int > latest_annual:
                        latest_annual = y_int
        if not latest_annual:
            latest_annual = current_year - 1

    # Assemble historical annual years
    annual_years = list(range(latest_annual - max_annual_years + 1, latest_annual + 1))

    # 2. Check for interim quarters in latest_annual + 1
    interim_year = latest_annual + 1
    interim_quarters = []

    if interim_year <= current_year:
        tw3_found = False
        tw2_found = False
        tw1_found = False

        try:
            r3 = api.get_financial_reports(year=interim_year, period="tw3", kode_emiten=ticker_clean, page=1, page_size=2)
            tw3_found = bool(r3.get("Results"))
        except Exception:
            pass

        if not tw3_found:
            try:
                r2 = api.get_financial_reports(year=interim_year, period="tw2", kode_emiten=ticker_clean, page=1, page_size=2)
                tw2_found = bool(r2.get("Results"))
            except Exception:
                pass

        if not tw3_found and not tw2_found:
            try:
                r1 = api.get_financial_reports(year=interim_year, period="tw1", kode_emiten=ticker_clean, page=1, page_size=2)
                tw1_found = bool(r1.get("Results"))
            except Exception:
                pass

        # Check local folder cache as fallback
        local_cache_interim = os.path.join("downloads", ticker_clean)
        if os.path.exists(local_cache_interim):
            for d in os.listdir(local_cache_interim):
                if d == f"{interim_year}_tw3": tw3_found = True
                if d == f"{interim_year}_tw2": tw2_found = True
                if d == f"{interim_year}_tw1": tw1_found = True

        if tw3_found:
            interim_quarters = [
                {"period": "tw1", "label": f"{interim_year}-Q1 (3M)", "key": f"{interim_year}-Q1"},
                {"period": "tw2", "label": f"{interim_year}-Q2 (6M)", "key": f"{interim_year}-Q2"},
                {"period": "tw3", "label": f"{interim_year}-Q3 (9M)", "key": f"{interim_year}-Q3"},
            ]
        elif tw2_found:
            interim_quarters = [
                {"period": "tw1", "label": f"{interim_year}-Q1 (3M)", "key": f"{interim_year}-Q1"},
                {"period": "tw2", "label": f"{interim_year}-Q2 (6M)", "key": f"{interim_year}-Q2"},
            ]
        elif tw1_found:
            interim_quarters = [
                {"period": "tw1", "label": f"{interim_year}-Q1 (3M)", "key": f"{interim_year}-Q1"},
            ]

    all_periods = [str(y) for y in annual_years] + [q["key"] for q in interim_quarters]

    return {
        "ticker": ticker_clean,
        "latest_annual_year": latest_annual,
        "annual_years": annual_years,
        "interim_year": interim_year if interim_quarters else None,
        "interim_quarters": interim_quarters,
        "all_periods": all_periods
    }
