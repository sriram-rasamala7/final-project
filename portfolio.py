import csv
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _load_nifty500_stocks():
    path = os.path.join(DATA_DIR, "nifty500_symbols.csv")
    if not os.path.exists(path):
        return []

    stocks = []
    with open(path, newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            symbol = (row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            name = (row.get("name") or symbol).strip()
            sector = (row.get("sector") or "Nifty 500").strip()
            stocks.append({"symbol": f"{symbol}.NS", "name": name, "sector": sector})
    return stocks

STOCK_UNIVERSE = {
    "Low": [
        {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "Consumer Defensive"},
        {"symbol": "ITC.NS", "name": "ITC", "sector": "Consumer Defensive"},
        {"symbol": "NESTLEIND.NS", "name": "Nestle India", "sector": "Consumer Defensive"},
        {"symbol": "BRITANNIA.NS", "name": "Britannia Industries", "sector": "Consumer Defensive"},
        {"symbol": "COLPAL.NS", "name": "Colgate Palmolive", "sector": "Consumer Defensive"},
        {"symbol": "DABUR.NS", "name": "Dabur India", "sector": "Consumer Defensive"},
        {"symbol": "MARICO.NS", "name": "Marico", "sector": "Consumer Defensive"},
        {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Pharma"},
        {"symbol": "CIPLA.NS", "name": "Cipla", "sector": "Pharma"},
        {"symbol": "DRREDDY.NS", "name": "Dr Reddy's Laboratories", "sector": "Pharma"},
        {"symbol": "POWERGRID.NS", "name": "Power Grid", "sector": "Utilities"},
        {"symbol": "NTPC.NS", "name": "NTPC", "sector": "Utilities"},
        {"symbol": "COALINDIA.NS", "name": "Coal India", "sector": "Energy"},
        {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
        {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
        {"symbol": "SBILIFE.NS", "name": "SBI Life Insurance", "sector": "Insurance"},
    ],
    "Medium": [
        {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Conglomerate"},
        {"symbol": "TCS.NS", "name": "TCS", "sector": "IT"},
        {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
        {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT"},
        {"symbol": "WIPRO.NS", "name": "Wipro", "sector": "IT"},
        {"symbol": "TECHM.NS", "name": "Tech Mahindra", "sector": "IT"},
        {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
        {"symbol": "LT.NS", "name": "Larsen and Toubro", "sector": "Capital Goods"},
        {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking"},
        {"symbol": "AXISBANK.NS", "name": "Axis Bank", "sector": "Banking"},
        {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Automobile"},
        {"symbol": "M&M.NS", "name": "Mahindra and Mahindra", "sector": "Automobile"},
        {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement"},
        {"symbol": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Consumer Cyclical"},
        {"symbol": "PIDILITIND.NS", "name": "Pidilite Industries", "sector": "Chemicals"},
        {"symbol": "APOLLOHOSP.NS", "name": "Apollo Hospitals", "sector": "Healthcare"},
    ],
    "High": [
        {"symbol": "TATAMOTORS.NS", "name": "Tata Motors", "sector": "Automobile"},
        {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Infrastructure"},
        {"symbol": "ADANIGREEN.NS", "name": "Adani Green Energy", "sector": "Renewable Energy"},
        {"symbol": "ZOMATO.NS", "name": "Zomato", "sector": "Internet"},
        {"symbol": "PAYTM.NS", "name": "One 97 Communications", "sector": "Fintech"},
        {"symbol": "NYKAA.NS", "name": "FSN E-Commerce Ventures", "sector": "E-Commerce"},
        {"symbol": "POLICYBZR.NS", "name": "PB Fintech", "sector": "Fintech"},
        {"symbol": "BEL.NS", "name": "Bharat Electronics", "sector": "Defence Electronics"},
        {"symbol": "HAL.NS", "name": "Hindustan Aeronautics", "sector": "Defence"},
        {"symbol": "TRENT.NS", "name": "Trent", "sector": "Retail"},
        {"symbol": "DIXON.NS", "name": "Dixon Technologies", "sector": "Electronics"},
        {"symbol": "IRCTC.NS", "name": "IRCTC", "sector": "Travel Tech"},
        {"symbol": "SUZLON.NS", "name": "Suzlon Energy", "sector": "Renewable Energy"},
        {"symbol": "TATAELXSI.NS", "name": "Tata Elxsi", "sector": "Technology"},
        {"symbol": "MAZDOCK.NS", "name": "Mazagon Dock Shipbuilders", "sector": "Defence"},
        {"symbol": "COCHINSHIP.NS", "name": "Cochin Shipyard", "sector": "Shipbuilding"},
    ],
}

def _dedupe_stock_universe_by_risk(stock_universe):
    seen_symbols = set()
    cleaned_universe = {}
    for profile in ("Low", "Medium", "High"):
        cleaned_stocks = []
        for stock in stock_universe.get(profile, []):
            symbol = stock["symbol"].upper()
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            cleaned_stocks.append(stock)
        cleaned_universe[profile] = cleaned_stocks
    return cleaned_universe


STOCK_UNIVERSE = _dedupe_stock_universe_by_risk(STOCK_UNIVERSE)

NIFTY_500_STOCKS = _load_nifty500_stocks()

STOCK_NAME_TO_SYMBOL = {}
for bucket in STOCK_UNIVERSE.values():
    for stock in bucket:
        STOCK_NAME_TO_SYMBOL[stock["name"].lower()] = stock["symbol"]
        STOCK_NAME_TO_SYMBOL[stock["symbol"].replace(".NS", "").lower()] = stock["symbol"]

for stock in NIFTY_500_STOCKS:
    base_symbol = stock["symbol"].replace(".NS", "")
    STOCK_NAME_TO_SYMBOL.setdefault(stock["name"].lower(), stock["symbol"])
    STOCK_NAME_TO_SYMBOL.setdefault(base_symbol.lower(), stock["symbol"])
    STOCK_NAME_TO_SYMBOL.setdefault(stock["symbol"].lower(), stock["symbol"])


def get_stock_options():
    stocks_by_symbol = {}
    for bucket in STOCK_UNIVERSE.values():
        for stock in bucket:
            stocks_by_symbol[stock["symbol"]] = stock
    for stock in NIFTY_500_STOCKS:
        stocks_by_symbol.setdefault(stock["symbol"], stock)
    return sorted(stocks_by_symbol.values(), key=lambda item: item["name"].lower())

TOP_SIP_FUNDS = [
    {
        "name": "Bandhan Small Cap Fund Direct Growth",
        "category": "Small Cap",
        "min_sip": 100,
        "risk": "Very High",
        "three_year_return": "32.24%",
        "five_year_return": "27.33%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Invesco India Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "min_sip": 500,
        "risk": "Very High",
        "three_year_return": "29.03%",
        "five_year_return": "25.28%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Edelweiss Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "min_sip": 100,
        "risk": "Very High",
        "three_year_return": "27.98%",
        "five_year_return": "26.17%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Motilal Oswal Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "min_sip": 500,
        "risk": "Very High",
        "three_year_return": "26.88%",
        "five_year_return": "28.54%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "HDFC Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "min_sip": 100,
        "risk": "Very High",
        "three_year_return": "26.55%",
        "five_year_return": "25.68%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Nippon India Growth Mid Cap Fund Direct Growth",
        "category": "Mid Cap",
        "min_sip": 100,
        "risk": "Very High",
        "three_year_return": "26.54%",
        "five_year_return": "25.28%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Motilal Oswal Large and Mid Cap Fund Direct Growth",
        "category": "Large & Mid Cap",
        "min_sip": 500,
        "risk": "High",
        "three_year_return": "26.44%",
        "five_year_return": "23.95%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Kotak Multicap Fund Direct Growth",
        "category": "Multicap",
        "min_sip": 100,
        "risk": "High",
        "three_year_return": "25.54%",
        "five_year_return": "-",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "Bandhan Large & Mid Cap Fund Direct Growth",
        "category": "Large & Mid Cap",
        "min_sip": 100,
        "risk": "High",
        "three_year_return": "25.34%",
        "five_year_return": "23.02%",
        "source": "Groww Best SIP Mutual Funds 2026",
    },
    {
        "name": "HDFC Flexi Cap Direct Plan Growth",
        "category": "Flexi Cap",
        "min_sip": 100,
        "risk": "Very High",
        "three_year_return": "20.91%",
        "five_year_return": "17.25%",
        "source": "Groww Fund Page, Mar 2026",
    },
]


def _load_csv(file_name):
    path = os.path.join(DATA_DIR, file_name)
    with open(path, newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def get_mutual_funds_by_risk(risk_profile):
    rows = _load_csv("mutual_funds.csv")
    return [row for row in rows if row["risk_profile"].lower() == risk_profile.lower()]


def get_top_sip_funds():
    return TOP_SIP_FUNDS


def score_ipo(ipo):
    risk_score = 0
    subscription_times = float(ipo.get("subscription_times", 0) or 0)
    pe_ratio = float(ipo.get("pe_ratio", 0) or 0)
    years_in_operation = float(ipo.get("years_in_operation", 0) or 0)
    promoter_holding_pct = float(ipo.get("promoter_holding_pct", 0) or 0)
    platform = str(ipo.get("platform", "")).upper()
    issue_type = str(ipo.get("issue_type", "")).upper()
    days_left = ipo.get("days_left", 0) or 0

    if subscription_times >= 30:
        risk_score += 25
    elif subscription_times >= 10:
        risk_score += 12

    if pe_ratio >= 70:
        risk_score += 25
    elif pe_ratio >= 35:
        risk_score += 10

    if str(ipo.get("profit_making", "")).lower() in {"false", "no", "0"}:
        risk_score += 20

    if 0 < years_in_operation < 5:
        risk_score += 15
    elif 0 < years_in_operation < 10:
        risk_score += 8

    if 0 < promoter_holding_pct < 45:
        risk_score += 10

    if "SME" in platform or "SME" in issue_type:
        risk_score += 18

    if isinstance(days_left, int) and days_left <= 1:
        risk_score += 8

    if risk_score >= 55:
        risk_level = "High"
    elif risk_score >= 30:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    ipo = dict(ipo)
    ipo["risk_score"] = risk_score
    ipo["risk_level"] = risk_level
    return ipo


def _normalize_text(value):
    return str(value or "").replace("Ã¢â€šÂ¹", "â‚¹").replace("\xa0", " ").strip()


def _is_currency_line(value):
    normalized = _normalize_text(value)
    return normalized.startswith("â‚¹") or normalized.lower().startswith("rs") or normalized.upper().startswith("INR")


def _parse_date(value):
    normalized = _normalize_text(value)
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def _safe_float(value, default=0.0):
    cleaned = re.sub(r"[^0-9.]", "", _normalize_text(value))
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _row_priority(row):
    source_priority = {"BSE": 4, "NSE": 4, "Upstox": 3, "Groww": 2}
    filled_fields = sum(1 for key in ("price_band", "subscription_times", "platform", "issue_type", "status") if row.get(key))
    return (source_priority.get(row.get("source", ""), 1), filled_fields, int(row.get("risk_score", 0)))


def _sort_date_key(row):
    end_date = _parse_date(row.get("end_date"))
    start_date = _parse_date(row.get("start_date"))
    return (end_date or datetime.max.date(), start_date or datetime.max.date(), row.get("name", ""))


def _parse_live_ipo_rows(html, source_name):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    today = datetime.today().date()
    results = []

    for table in tables:
        headers = [cell.get_text(" ", strip=True).lower() for cell in table.find_all("th")]
        if not headers:
            continue
        header_text = " ".join(headers)
        if "start date" not in header_text or "end date" not in header_text:
            continue

        body_rows = table.find_all("tr")
        for tr in body_rows:
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if len(cells) < 4:
                continue

            mapped = {}
            for index, header in enumerate(headers[: len(cells)]):
                value = cells[index]
                if "security name" in header or "company name" in header:
                    mapped["name"] = value
                elif "exchange platform" in header or header == "platform":
                    mapped["platform"] = value
                elif "start date" in header:
                    mapped["start_date"] = value
                elif "end date" in header:
                    mapped["end_date"] = value
                elif "offer price" in header or "price band" in header:
                    mapped["price_band"] = value
                elif "face value" in header:
                    mapped["face_value"] = value
                elif "type of issue" in header or "security type" in header:
                    mapped["issue_type"] = value
                elif "issue status" in header or header == "status":
                    mapped["status"] = value

            if not mapped.get("name") or not mapped.get("start_date") or not mapped.get("end_date"):
                continue

            issue_type = str(mapped.get("issue_type", "")).upper()
            platform = str(mapped.get("platform", "")).upper()
            issue_text = f"{issue_type} {platform}"
            is_ipo_like = ("IPO" in issue_text) or ("SME" in issue_text)
            if not is_ipo_like:
                continue

            start_date = _parse_date(mapped["start_date"])
            end_date = _parse_date(mapped["end_date"])
            if not start_date or not end_date:
                continue

            status = str(mapped.get("status", "")).lower()
            if not (start_date <= today <= end_date or status in {"live", "active", "open"}):
                continue

            mapped["source"] = source_name
            mapped["status"] = mapped.get("status") or "Live"
            mapped["days_left"] = (end_date - today).days
            results.append(mapped)

        if results:
            return results

    return []


def _fetch_live_bse_ipos():
    response = requests.get("https://www.bseindia.com/publicissue.html", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    response.raise_for_status()
    return _parse_live_ipo_rows(response.text, "BSE")


def _fetch_live_nse_ipos():
    response = requests.get(
        "https://www.nseindia.com/market-data/public-issues-initial-public-offering-ipo",
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
        timeout=15,
    )
    response.raise_for_status()
    return _parse_live_ipo_rows(response.text, "NSE")


def _fetch_groww_open_ipos():
    response = requests.get("https://groww.in/ipo/sme", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = soup.get_text("\n", strip=True)
    if "Open IPOs" not in page_text or "Upcoming IPOs" not in page_text:
        return []

    section = page_text.split("Open IPOs", 1)[1].split("Upcoming IPOs", 1)[0]
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    records = []

    pattern = re.compile(
        r"^(?P<name>.+?)\s+"
        r"(?P<issue_type>Mainboard|SME)\s+"
        r"(?P<start>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+"
        r"(?P<end>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s*"
        r"(?P<price_band>(?:â‚¹|Ã¢â€šÂ¹).+?)\s+"
        r"(?P<subscription>(?:--|[0-9.]+x))"
    )

    today = datetime.today().date()
    for line in lines:
        match = pattern.search(_normalize_text(line))
        if not match:
            continue

        start_date = _parse_date(match.group("start"))
        end_date = _parse_date(match.group("end"))
        if not start_date or not end_date:
            continue
        if not (start_date <= today <= end_date):
            continue

        issue_type = match.group("issue_type")
        records.append(
            {
                "name": match.group("name"),
                "issue_type": issue_type,
                "platform": "BSE SME" if issue_type == "SME" else "Mainboard",
                "start_date": start_date.strftime("%d-%b-%Y"),
                "end_date": end_date.strftime("%d-%b-%Y"),
                "price_band": _normalize_text(match.group("price_band")),
                "status": "Live",
                "source": "Groww",
                "days_left": (end_date - today).days,
            }
        )

    return records


def _parse_upstox_open_rows(html, source_name):
    soup = BeautifulSoup(html, "html.parser")
    lines = [_normalize_text(line) for line in soup.get_text("\n", strip=True).splitlines() if _normalize_text(line)]
    today = datetime.today().date()
    current_year = today.year
    records = []

    try:
        start_index = next(index for index, line in enumerate(lines) if line == "Name")
    except StopIteration:
        return []

    stop_markers = {
        "View more open IPOs",
        "## Upcoming IPOs",
        "## How to apply for IPOs on Upstox",
        "* * *",
    }
    payload_lines = []
    for line in lines[start_index + 1:]:
        if line in stop_markers:
            break
        payload_lines.append(line)

    index = 0
    date_pattern = re.compile(r"^(?P<start>\d{2}\s[A-Za-z]{3})\s-\s(?P<end>\d{2}\s[A-Za-z]{3})$")
    while index + 4 < len(payload_lines):
        row_line = payload_lines[index]
        date_line = payload_lines[index + 1]
        issue_size_line = payload_lines[index + 2]
        price_line = payload_lines[index + 3]
        subscription_line = payload_lines[index + 4]

        match = re.match(r"^(?P<name>.+? IPO)\s+(?P<platform>Mainboard|SME)(?:,\s*(?P<sector>.+))?$", row_line)
        date_match = date_pattern.match(date_line)

        if not match or not date_match or not _is_currency_line(issue_size_line) or not _is_currency_line(price_line):
            index += 1
            continue

        start_date = datetime.strptime(f"{date_match.group('start')} {current_year}", "%d %b %Y").date()
        end_date = datetime.strptime(f"{date_match.group('end')} {current_year}", "%d %b %Y").date()
        if not (start_date <= today <= end_date):
            index += 5
            continue

        platform = match.group("platform")
        sector = (match.group("sector") or "--").strip()
        subscription_value = subscription_line.replace("x", "").strip()
        records.append(
            {
                "name": match.group("name").replace(" IPO", "").strip(),
                "platform": platform,
                "issue_type": "SME IPO" if platform == "SME" else "Mainboard IPO",
                "sector": sector,
                "start_date": start_date.strftime("%d-%b-%Y"),
                "end_date": end_date.strftime("%d-%b-%Y"),
                "issue_size": _normalize_text(issue_size_line),
                "price_band": _normalize_text(price_line),
                "subscription_times": _safe_float(subscription_value),
                "status": "Live",
                "source": source_name,
                "days_left": (end_date - today).days,
            }
        )
        index += 5

    return records


def _fetch_upstox_current_ipos():
    response = requests.get("https://upstox.com/ipo/current-ipo/", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    response.raise_for_status()
    return _parse_upstox_open_rows(response.text, "Upstox")


def _fetch_upstox_sme_ipos():
    response = requests.get("https://upstox.com/ipo/sme/", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    response.raise_for_status()
    return _parse_upstox_open_rows(response.text, "Upstox")


def get_ipo_analysis():
    """Fetch live IPO/GMP rows from public IPO tracker pages.

    GMP is unofficial grey-market data, so the function keeps source names and
    fails softly when a site blocks scraping or changes its HTML.
    """
    sources = [
        {"name": "IPOTrackers", "url": "https://ipotrackers.com/ipo-gmp/"},
        {"name": "IPOGrey", "url": "https://ipogrey.com/ipo-gmp/"},
        {"name": "Live IPO GMP", "url": "https://liveipogmp.com/"},
        {"name": "IPOSathi", "url": "https://www.iposathi.com/ipo/open"},
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    }

    def clean(value):
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        value = value.replace("\u20b9", "Rs. ").replace("\ufffd", "-")
        return value or "Not available"

    def pick(row, *keywords):
        for key, value in row.items():
            header = key.lower()
            if any(keyword in header for keyword in keywords):
                return clean(value)
        return "Not available"

    def parse_date(value):
        text = clean(value).replace("Sept", "Sep")
        text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.I)
        formats = ("%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y")
        for candidate in re.findall(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{1,2}-[A-Za-z]{3,9}-\d{4}", text):
            for fmt in formats:
                try:
                    return datetime.strptime(candidate, fmt).date()
                except ValueError:
                    continue
        return None

    def ipo_category(name, issue_type, status):
        text = f"{name} {issue_type} {status}".lower()
        if "sme" in text:
            return "SME"
        return "Mainboard"
    def parse_rows(source):
        response = requests.get(source["url"], headers=headers, timeout=4)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        soup = BeautifulSoup(response.text, "html.parser")
        records = []

        for table in soup.select("table"):
            header_cells = table.select("thead th")
            if not header_cells:
                first_row = table.find("tr")
                header_cells = first_row.find_all(["th", "td"]) if first_row else []
            headers_text = [clean(cell.get_text(" ")) for cell in header_cells]
            if len(headers_text) < 2:
                continue

            for tr in table.select("tbody tr") or table.select("tr")[1:]:
                cells = [clean(cell.get_text(" ")) for cell in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                row = dict(zip(headers_text, cells))
                name = pick(row, "ipo name", "company", "ipo")
                if name == "Not available" or len(name) < 3:
                    continue

                status = pick(row, "status")
                issue_type = pick(row, "type", "segment", "platform")
                record = {
                    "name": name.replace(" IPO IPO", " IPO"),
                    "status": status,
                    "issue_type": issue_type,
                    "apply_date": pick(row, "open", "ipo date"),
                    "open_date": pick(row, "open", "ipo date"),
                    "close_date": pick(row, "close"),
                    "price_band": pick(row, "price band", "issue price", "price"),
                    "gmp": pick(row, "gmp"),
                    "gmp_pct": pick(row, "gmp %", "gain", "estimated", "est"),
                    "estimated_listing_price": pick(row, "listing price", "est listing", "estimated listing"),
                    "lot_size": pick(row, "lot"),
                    "subscription": pick(row, "subscription", "subscribed"),
                    "source": source["name"],
                    "source_url": source["url"],
                    "category": ipo_category(name, issue_type, status),
                    "updated_at": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                }

                close_date = parse_date(record["close_date"])
                open_date = parse_date(record["open_date"])
                today = datetime.now().date()
                searchable = " ".join(record.values()).lower()
                is_current = close_date is not None and close_date >= today
                is_upcoming = open_date is not None and open_date >= today
                has_live_status = any(word in searchable for word in ("open", "live", "upcoming", "today"))
                if (is_current or is_upcoming or has_live_status) and not (close_date is not None and close_date < today):
                    records.append(record)
        return records

    def normalized_name_key(name):
        name = re.sub(r"\b(ipo|limited|ltd|private|pvt|india)\b", "", str(name).lower())
        return re.sub(r"[^a-z0-9]", "", name)[:80]
    merged_rows = {}
    for source in sources:
        try:
            for row in parse_rows(source):
                key = normalized_name_key(row["name"])
                if not key:
                    continue
                existing = merged_rows.get(key)
                if not existing or existing.get("gmp") in ("Not available", "--", "-"):
                    merged_rows[key] = row
        except Exception:
            continue

    def priority(row):
        text = f"{row.get('status', '')} {row.get('open_date', '')}".lower()
        if "open" in text or "live" in text:
            return 0
        if "upcoming" in text or "today" in text:
            return 1
        return 2

    return sorted(merged_rows.values(), key=lambda row: (priority(row), row.get("close_date", "")))

def get_portfolio_suggestion(risk_profile, investment_amount):
    if investment_amount <= 0:
        raise ValueError("Investment amount should be greater than 0.")

    risk_profile = risk_profile.title()
    allocation_map = {
        "Low": {"equity": 30, "debt": 45, "gold": 15, "liquid": 10},
        "Medium": {"equity": 55, "debt": 25, "gold": 10, "liquid": 10},
        "High": {"equity": 75, "debt": 10, "gold": 10, "liquid": 5},
    }
    allocation_pct = allocation_map.get(risk_profile, allocation_map["Medium"])
    allocation_inr = {key: round((value / 100) * investment_amount, 2) for key, value in allocation_pct.items()}

    return {
        "risk_profile": risk_profile,
        "investment_amount": round(investment_amount, 2),
        "allocation_pct": allocation_pct,
        "allocation_inr": allocation_inr,
        "recommended_funds": get_mutual_funds_by_risk(risk_profile),
        "recommended_stocks": STOCK_UNIVERSE.get(risk_profile, STOCK_UNIVERSE["Medium"]),
    }







