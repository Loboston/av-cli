#!/usr/bin/env python3
"""av — Alpha Vantage CLI: stocks, forex, crypto, fundamentals & economics."""

import csv as csv_module
import io
import json
import os
import sys
import urllib.parse
import urllib.request

import click

BASE_URL = "https://www.alphavantage.co/query"
FORMAT_CHOICES = click.Choice(["markdown", "json", "csv"], case_sensitive=False)


# ── Core ───────────────────────────────────────────────────────────────────────

def get_api_key():
    key = os.environ.get("ALPHA_VANTAGE_KEY")
    if not key:
        click.echo("Error: ALPHA_VANTAGE_KEY environment variable is not set.", err=True)
        click.echo("Get a free key at https://www.alphavantage.co/support/#api-key", err=True)
        sys.exit(1)
    return key


def fetch_av(params):
    apikey = get_api_key()
    query = urllib.parse.urlencode({**params, "apikey": apikey})
    url = f"{BASE_URL}?{query}"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise click.ClickException(f"API request failed: {e}")

    if "Error Message" in data:
        raise click.ClickException(data["Error Message"])
    if "Note" in data:
        click.echo(f"Warning: {data['Note']}", err=True)
    if "Information" in data:
        click.echo(f"Warning: {data['Information']}", err=True)

    return data


def fetch_av_csv(params):
    """For endpoints that return raw CSV (e.g. LISTING_STATUS)."""
    apikey = get_api_key()
    query = urllib.parse.urlencode({**params, "apikey": apikey})
    url = f"{BASE_URL}?{query}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode()
    except Exception as e:
        raise click.ClickException(f"API request failed: {e}")


# ── Output helpers ─────────────────────────────────────────────────────────────

def emit_table(title, headers, rows, fmt):
    if fmt == "json":
        records = [dict(zip(headers, row)) for row in rows]
        click.echo(json.dumps({"title": title, "data": records}, indent=2))
        return
    if fmt == "csv":
        buf = io.StringIO()
        w = csv_module.writer(buf)
        w.writerow(headers)
        w.writerows(rows)
        click.echo(buf.getvalue().rstrip())
        return
    col_w = [
        max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    lines = [
        f"# {title}", "",
        "| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, col_w)) + " |",
        "|" + "|".join("-" * (w + 2) for w in col_w) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(v).ljust(w) for v, w in zip(row, col_w)) + " |")
    click.echo("\n".join(lines))


def emit_kv(title, fields, fmt, description=None):
    if fmt == "json":
        click.echo(json.dumps(fields, indent=2))
        return
    if fmt == "csv":
        buf = io.StringIO()
        w = csv_module.writer(buf)
        w.writerow(["Field", "Value"])
        for k, v in fields.items():
            w.writerow([k, v])
        click.echo(buf.getvalue().rstrip())
        return
    key_w = max(len(k) for k in fields)
    val_w = max(len(str(v)) for v in fields.values())
    lines = [f"# {title}", ""]
    if description:
        short = (description[:120] + "…") if len(description) > 120 else description
        lines += [f"> {short}", ""]
    lines += [
        f"| {'Field'.ljust(key_w)} | {'Value'.ljust(val_w)} |",
        f"|{'-'*(key_w+2)}|{'-'*(val_w+2)}|",
        *[f"| {str(k).ljust(key_w)} | {str(v).ljust(val_w)} |" for k, v in fields.items()],
    ]
    click.echo("\n".join(lines))


# ── Shared option factories ────────────────────────────────────────────────────

def fmt_opt(default="markdown"):
    return click.option("-f", "--format", "fmt", default=default,
                        type=FORMAT_CHOICES, show_default=True, help="Output format.")


def days_opt(default=10):
    return click.option("-n", "--days", default=default, show_default=True,
                        help="Number of periods to display.")


INTERVAL_CHOICE = click.Choice(
    ["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"]
)
SERIES_CHOICE = click.Choice(["close", "open", "high", "low"])


# ── CLI root ───────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("2.2.0")
def cli():
    """av — Alpha Vantage CLI: stocks, forex, crypto, fundamentals & economics."""


# ── STOCKS ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("ticker")
@fmt_opt()
def quote(ticker, fmt):
    """Real-time stock quote."""
    data = fetch_av({"function": "GLOBAL_QUOTE", "symbol": ticker.upper()})
    q = data.get("Global Quote", {})
    if not q or not q.get("01. symbol"):
        raise click.ClickException("No quote data. Check the ticker symbol.")
    fields = {
        "Symbol":             q.get("01. symbol", ""),
        "Open":               q.get("02. open", ""),
        "High":               q.get("03. high", ""),
        "Low":                q.get("04. low", ""),
        "Price":              q.get("05. price", ""),
        "Volume":             q.get("06. volume", ""),
        "Latest Trading Day": q.get("07. latest trading day", ""),
        "Previous Close":     q.get("08. previous close", ""),
        "Change":             q.get("09. change", ""),
        "Change %":           q.get("10. change percent", ""),
    }
    emit_kv(f"{fields['Symbol']} — Stock Quote", fields, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="5min",
              type=click.Choice(["1min", "5min", "15min", "30min", "60min"]),
              show_default=True, help="Bar interval.")
@days_opt(default=20)
def intraday(ticker, fmt, interval, days):
    """Intraday OHLCV time series."""
    data = fetch_av({"function": "TIME_SERIES_INTRADAY", "symbol": ticker.upper(),
                     "interval": interval, "outputsize": "compact"})
    series = data.get(f"Time Series ({interval})")
    if not series:
        raise click.ClickException("No intraday data returned. (Requires premium key)")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"], v["5. volume"]]
            for dt, v in entries]
    emit_table(f"{symbol} — Intraday {interval} (last {len(entries)})", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@days_opt(default=10)
def daily(ticker, fmt, days):
    """Daily OHLCV time series."""
    data = fetch_av({"function": "TIME_SERIES_DAILY", "symbol": ticker.upper()})
    series = data.get("Time Series (Daily)")
    if not series:
        raise click.ClickException("No daily data returned.")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Date", "Open", "High", "Low", "Close", "Volume"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"], v["5. volume"]]
            for dt, v in entries]
    emit_table(f"{symbol} — Daily (last {len(entries)} days)", headers, rows, fmt)


@cli.command("daily-adjusted")
@click.argument("ticker")
@fmt_opt()
@days_opt(default=10)
def daily_adjusted(ticker, fmt, days):
    """Daily adjusted OHLCV + split/dividend events. [premium]"""
    data = fetch_av({"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": ticker.upper()})
    series = data.get("Time Series (Daily)")
    if not series:
        raise click.ClickException("No data returned. (Requires premium key)")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume",
               "Dividend", "Split Coeff"]
    rows = [[dt, v.get("1. open",""), v.get("2. high",""), v.get("3. low",""),
             v.get("4. close",""), v.get("5. adjusted close",""), v.get("6. volume",""),
             v.get("7. dividend amount",""), v.get("8. split coefficient","")]
            for dt, v in entries]
    emit_table(f"{symbol} — Daily Adjusted (last {len(entries)} days)", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@days_opt(default=10)
def weekly(ticker, fmt, days):
    """Weekly OHLCV time series."""
    data = fetch_av({"function": "TIME_SERIES_WEEKLY", "symbol": ticker.upper()})
    series = data.get("Weekly Time Series")
    if not series:
        raise click.ClickException("No weekly data returned.")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Week", "Open", "High", "Low", "Close", "Volume"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"], v["5. volume"]]
            for dt, v in entries]
    emit_table(f"{symbol} — Weekly (last {len(entries)} weeks)", headers, rows, fmt)


@cli.command("weekly-adjusted")
@click.argument("ticker")
@fmt_opt()
@days_opt(default=10)
def weekly_adjusted(ticker, fmt, days):
    """Weekly adjusted OHLCV + dividend events."""
    data = fetch_av({"function": "TIME_SERIES_WEEKLY_ADJUSTED", "symbol": ticker.upper()})
    series = data.get("Weekly Adjusted Time Series")
    if not series:
        raise click.ClickException("No weekly adjusted data returned.")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Week", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividend"]
    rows = [[dt, v.get("1. open",""), v.get("2. high",""), v.get("3. low",""),
             v.get("4. close",""), v.get("5. adjusted close",""), v.get("6. volume",""),
             v.get("7. dividend amount","")]
            for dt, v in entries]
    emit_table(f"{symbol} — Weekly Adjusted (last {len(entries)} weeks)", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@days_opt(default=12)
def monthly(ticker, fmt, days):
    """Monthly OHLCV time series."""
    data = fetch_av({"function": "TIME_SERIES_MONTHLY", "symbol": ticker.upper()})
    series = data.get("Monthly Time Series")
    if not series:
        raise click.ClickException("No monthly data returned.")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Month", "Open", "High", "Low", "Close", "Volume"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"], v["5. volume"]]
            for dt, v in entries]
    emit_table(f"{symbol} — Monthly (last {len(entries)} months)", headers, rows, fmt)


@cli.command("monthly-adjusted")
@click.argument("ticker")
@fmt_opt()
@days_opt(default=12)
def monthly_adjusted(ticker, fmt, days):
    """Monthly adjusted OHLCV + dividend events."""
    data = fetch_av({"function": "TIME_SERIES_MONTHLY_ADJUSTED", "symbol": ticker.upper()})
    series = data.get("Monthly Adjusted Time Series")
    if not series:
        raise click.ClickException("No monthly adjusted data returned.")
    symbol = data.get("Meta Data", {}).get("2. Symbol", ticker.upper())
    entries = list(series.items())[:days]
    headers = ["Month", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividend"]
    rows = [[dt, v.get("1. open",""), v.get("2. high",""), v.get("3. low",""),
             v.get("4. close",""), v.get("5. adjusted close",""), v.get("6. volume",""),
             v.get("7. dividend amount","")]
            for dt, v in entries]
    emit_table(f"{symbol} — Monthly Adjusted (last {len(entries)} months)", headers, rows, fmt)


@cli.command()
@click.argument("query")
@fmt_opt()
def search(query, fmt):
    """Search for a ticker symbol by keyword."""
    data = fetch_av({"function": "SYMBOL_SEARCH", "keywords": query})
    matches = data.get("bestMatches", [])
    if not matches:
        raise click.ClickException("No matches found.")
    headers = ["Symbol", "Name", "Type", "Region", "Currency", "Match Score"]
    rows = [[m.get("1. symbol",""), m.get("2. name",""), m.get("3. type",""),
             m.get("4. region",""), m.get("8. currency",""), m.get("9. matchScore","")]
            for m in matches]
    emit_table(f'Search: "{query}"', headers, rows, fmt)


@cli.command("market-status")
@fmt_opt()
def market_status(fmt):
    """Current open/closed status for major global exchanges."""
    data = fetch_av({"function": "MARKET_STATUS"})
    markets = data.get("markets", [])
    if not markets:
        raise click.ClickException("No market status data returned.")
    headers = ["Market Type", "Region", "Primary Exchanges", "Local Open", "Local Close", "Status", "Notes"]
    rows = [[m.get("market_type",""), m.get("region",""), m.get("primary_exchanges",""),
             m.get("local_open",""), m.get("local_close",""), m.get("current_status",""),
             m.get("notes","")]
            for m in markets]
    emit_table("Global Market Status", headers, rows, fmt)


@cli.command("bulk-quotes")
@click.argument("tickers", nargs=-1, required=True)
@fmt_opt()
def bulk_quotes(tickers, fmt):
    """Realtime quotes for multiple tickers (up to 100). [premium]"""
    symbols = ",".join(t.upper() for t in tickers)
    data = fetch_av({"function": "REALTIME_BULK_QUOTES", "symbol": symbols})
    quotes = data.get("data", [])
    if not quotes:
        raise click.ClickException("No data returned. (Requires premium key)")
    headers = ["symbol", "open", "high", "low", "price", "volume",
               "latest trading day", "previous close", "change", "change percent"]
    rows = [[q.get(h, "") for h in headers] for q in quotes]
    emit_table("Bulk Quotes", headers, rows, fmt)


# ── FUNDAMENTALS ──────────────────────────────────────────────────────────────

@cli.command()
@click.argument("ticker")
@fmt_opt()
def overview(ticker, fmt):
    """Company overview and fundamentals."""
    data = fetch_av({"function": "OVERVIEW", "symbol": ticker.upper()})
    if not data.get("Symbol"):
        raise click.ClickException("No company overview returned. Check the ticker symbol.")
    keys = [
        "Symbol", "Name", "Exchange", "Currency", "Country",
        "Sector", "Industry", "MarketCapitalization", "EBITDA", "PERatio",
        "PEGRatio", "BookValue", "DividendPerShare", "DividendYield",
        "EPS", "RevenuePerShareTTM", "ProfitMargin", "OperatingMarginTTM",
        "ReturnOnEquityTTM", "Beta", "52WeekHigh", "52WeekLow",
        "50DayMovingAverage", "200DayMovingAverage", "AnalystTargetPrice",
        "SharesOutstanding",
    ]
    fields = {k: data.get(k, "N/A") for k in keys}
    emit_kv(f"{fields['Symbol']} — {fields['Name']}", fields, fmt,
            description=data.get("Description", ""))


@cli.command("etf-profile")
@click.argument("ticker")
@fmt_opt()
def etf_profile(ticker, fmt):
    """ETF profile and top holdings."""
    data = fetch_av({"function": "ETF_PROFILE", "symbol": ticker.upper()})
    if not data.get("net_assets"):
        raise click.ClickException("No ETF profile data returned. Check the ticker symbol.")
    # Top-level fields
    top_keys = ["net_assets", "net_expense_ratio", "portfolio_turnover",
                "dividend_yield", "inception_date", "leveraged"]
    fields = {k: data.get(k, "N/A") for k in top_keys}
    emit_kv(f"{ticker.upper()} — ETF Profile", fields, fmt)
    # Holdings
    holdings = data.get("holdings", [])[:20]
    if holdings:
        click.echo("")
        headers = ["symbol", "description", "weight"]
        rows = [[h.get("symbol",""), h.get("description",""), h.get("weight","")]
                for h in holdings]
        emit_table(f"{ticker.upper()} — Top Holdings", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--limit", default=10, show_default=True)
def dividends(ticker, fmt, limit):
    """Historical dividend payouts."""
    data = fetch_av({"function": "DIVIDENDS", "symbol": ticker.upper()})
    items = data.get("data", [])[:limit]
    if not items:
        raise click.ClickException("No dividend data returned.")
    headers = ["ex_dividend_date", "declaration_date", "record_date",
               "payment_date", "amount"]
    rows = [[i.get(h, "") for h in headers] for i in items]
    emit_table(f"{ticker.upper()} — Dividends", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--limit", default=10, show_default=True)
def splits(ticker, fmt, limit):
    """Historical stock splits."""
    data = fetch_av({"function": "SPLITS", "symbol": ticker.upper()})
    items = data.get("data", [])[:limit]
    if not items:
        raise click.ClickException("No split data returned.")
    headers = ["effective_date", "split_factor"]
    rows = [[i.get(h, "") for h in headers] for i in items]
    emit_table(f"{ticker.upper()} — Stock Splits", headers, rows, fmt)


@cli.command("shares-outstanding")
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--limit", default=10, show_default=True)
def shares_outstanding(ticker, fmt, limit):
    """Historical shares outstanding."""
    data = fetch_av({"function": "SHARES_OUTSTANDING", "symbol": ticker.upper()})
    items = data.get("data", [])[:limit]
    if not items:
        raise click.ClickException("No shares outstanding data returned.")
    headers = ["date", "commonSharesOutstanding"]
    rows = [[i.get(h, "") for h in headers] for i in items]
    emit_table(f"{ticker.upper()} — Shares Outstanding", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--periods", default=4, show_default=True)
def income(ticker, fmt, periods):
    """Annual income statement."""
    data = fetch_av({"function": "INCOME_STATEMENT", "symbol": ticker.upper()})
    reports = data.get("annualReports", [])[:periods]
    if not reports:
        raise click.ClickException("No income statement data returned.")
    headers = ["fiscalDateEnding", "totalRevenue", "grossProfit", "operatingIncome",
               "netIncome", "ebitda", "eps", "researchAndDevelopment"]
    rows = [[r.get(h, "N/A") for h in headers] for r in reports]
    emit_table(f"{ticker.upper()} — Income Statement (Annual)", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--periods", default=4, show_default=True)
def balance(ticker, fmt, periods):
    """Annual balance sheet."""
    data = fetch_av({"function": "BALANCE_SHEET", "symbol": ticker.upper()})
    reports = data.get("annualReports", [])[:periods]
    if not reports:
        raise click.ClickException("No balance sheet data returned.")
    headers = ["fiscalDateEnding", "totalAssets", "totalLiabilities",
               "totalShareholderEquity", "cashAndCashEquivalentsAtCarryingValue",
               "longTermDebt", "shortTermDebt", "commonStockSharesOutstanding"]
    rows = [[r.get(h, "N/A") for h in headers] for r in reports]
    emit_table(f"{ticker.upper()} — Balance Sheet (Annual)", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--periods", default=4, show_default=True)
def cashflow(ticker, fmt, periods):
    """Annual cash flow statement."""
    data = fetch_av({"function": "CASH_FLOW", "symbol": ticker.upper()})
    reports = data.get("annualReports", [])[:periods]
    if not reports:
        raise click.ClickException("No cash flow data returned.")
    headers = ["fiscalDateEnding", "operatingCashflow", "capitalExpenditures",
               "cashflowFromInvestment", "cashflowFromFinancing",
               "dividendPayout", "freeCashFlow"]
    rows = [[r.get(h, "N/A") for h in headers] for r in reports]
    emit_table(f"{ticker.upper()} — Cash Flow (Annual)", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--periods", default=8, show_default=True)
def earnings(ticker, fmt, periods):
    """Quarterly EPS earnings with surprise."""
    data = fetch_av({"function": "EARNINGS", "symbol": ticker.upper()})
    reports = data.get("quarterlyEarnings", [])[:periods]
    if not reports:
        raise click.ClickException("No earnings data returned.")
    headers = ["fiscalDateEnding", "reportedDate", "reportedEPS",
               "estimatedEPS", "surprise", "surprisePercentage"]
    rows = [[r.get(h, "N/A") for h in headers] for r in reports]
    emit_table(f"{ticker.upper()} — Quarterly Earnings", headers, rows, fmt)


@cli.command("earnings-estimates")
@click.argument("ticker")
@fmt_opt()
def earnings_estimates(ticker, fmt):
    """Analyst earnings estimates."""
    data = fetch_av({"function": "EARNINGS_ESTIMATES", "symbol": ticker.upper()})
    estimates = data.get("quarterlyEstimates") or data.get("annualEstimates") or []
    if not estimates:
        raise click.ClickException("No earnings estimates returned.")
    headers = list(estimates[0].keys())
    rows = [[r.get(h, "") for h in headers] for r in estimates[:8]]
    emit_table(f"{ticker.upper()} — Earnings Estimates", headers, rows, fmt)


@cli.command("earnings-calendar")
@fmt_opt()
@click.option("--horizon", default="3month",
              type=click.Choice(["3month", "6month", "12month"]), show_default=True)
def earnings_calendar(fmt, horizon):
    """Upcoming earnings announcements (returns CSV from API)."""
    raw = fetch_av_csv({"function": "EARNINGS_CALENDAR", "horizon": horizon})
    reader = csv_module.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        raise click.ClickException("No earnings calendar data returned.")
    headers, data_rows = rows[0], rows[1:21]
    if fmt == "csv":
        click.echo(raw)
        return
    if fmt == "json":
        click.echo(json.dumps([dict(zip(headers, r)) for r in data_rows], indent=2))
        return
    emit_table(f"Earnings Calendar ({horizon})", headers, data_rows, fmt)


@cli.command("ipo-calendar")
@fmt_opt()
def ipo_calendar(fmt):
    """Upcoming IPOs."""
    raw = fetch_av_csv({"function": "IPO_CALENDAR"})
    reader = csv_module.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        raise click.ClickException("No IPO calendar data returned.")
    headers, data_rows = rows[0], rows[1:21]
    if fmt == "csv":
        click.echo(raw)
        return
    if fmt == "json":
        click.echo(json.dumps([dict(zip(headers, r)) for r in data_rows], indent=2))
        return
    emit_table("IPO Calendar", headers, data_rows, fmt)


@cli.command("listing-status")
@fmt_opt()
@click.option("--state", default="active",
              type=click.Choice(["active", "delisted"]), show_default=True)
def listing_status(fmt, state):
    """Active or delisted US stocks/ETFs."""
    raw = fetch_av_csv({"function": "LISTING_STATUS", "state": state})
    reader = csv_module.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        raise click.ClickException("No listing data returned.")
    headers, data_rows = rows[0], rows[1:21]
    if fmt == "csv":
        click.echo(raw[:10000])
        return
    if fmt == "json":
        click.echo(json.dumps([dict(zip(headers, r)) for r in data_rows], indent=2))
        return
    emit_table(f"{state.capitalize()} Listings (sample of 20)", headers, data_rows, fmt)


# ── ALPHA INTELLIGENCE ────────────────────────────────────────────────────────

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-n", "--limit", default=10, show_default=True)
def news(ticker, fmt, limit):
    """Latest news and sentiment for a ticker."""
    data = fetch_av({"function": "NEWS_SENTIMENT", "tickers": ticker.upper(), "limit": limit})
    items = data.get("feed", [])
    if not items:
        raise click.ClickException("No news data returned.")
    if fmt == "json":
        click.echo(json.dumps(items[:limit], indent=2))
        return
    if fmt == "csv":
        buf = io.StringIO()
        w = csv_module.writer(buf)
        w.writerow(["Title", "Source", "Published", "Sentiment", "URL"])
        for item in items[:limit]:
            w.writerow([item.get("title",""), item.get("source",""),
                        item.get("time_published",""),
                        item.get("overall_sentiment_label",""), item.get("url","")])
        click.echo(buf.getvalue().rstrip())
        return
    lines = [f"# {ticker.upper()} — News & Sentiment", ""]
    for item in items[:limit]:
        lines += [
            f"### {item.get('title','')}",
            f"_{item.get('source','')}_ · {item.get('time_published','')[:8]}"
            f" · **{item.get('overall_sentiment_label','')}**",
            f"<{item.get('url','')}>",
            "",
        ]
    click.echo("\n".join(lines))


@cli.command("earnings-transcript")
@click.argument("ticker")
@click.argument("quarter", metavar="QUARTER (e.g. 2024Q1)")
@fmt_opt()
def earnings_transcript(ticker, quarter, fmt):
    """Earnings call transcript with sentiment. [premium]"""
    data = fetch_av({"function": "EARNINGS_CALL_TRANSCRIPT",
                     "symbol": ticker.upper(), "quarter": quarter})
    if not data.get("transcript"):
        raise click.ClickException("No transcript returned. (Requires premium key)")
    if fmt == "json":
        click.echo(json.dumps(data, indent=2))
        return
    if fmt == "csv":
        buf = io.StringIO()
        w = csv_module.writer(buf)
        w.writerow(["speaker", "content"])
        for entry in data.get("transcript", []):
            w.writerow([entry.get("speaker",""), entry.get("content","")])
        click.echo(buf.getvalue().rstrip())
        return
    lines = [f"# {ticker.upper()} {quarter} — Earnings Call Transcript", ""]
    for entry in data.get("transcript", []):
        lines += [f"**{entry.get('speaker','')}**", entry.get("content",""), ""]
    click.echo("\n".join(lines))


@cli.command("market-movers")
@fmt_opt()
def market_movers(fmt):
    """Top gainers, losers, and most active stocks."""
    data = fetch_av({"function": "TOP_GAINERS_LOSERS"})
    if fmt == "json":
        click.echo(json.dumps(data, indent=2))
        return
    headers = ["ticker", "price", "change_amount", "change_percentage", "volume"]
    for section, label in [("top_gainers", "Top Gainers"), ("top_losers", "Top Losers"),
                            ("most_actively_traded", "Most Active")]:
        items = data.get(section, [])
        if not items:
            continue
        rows = [[i.get(h, "") for h in headers] for i in items[:10]]
        emit_table(label, headers, rows, fmt)
        click.echo("")


@cli.command("insider-transactions")
@click.argument("ticker")
@fmt_opt()
def insider_transactions(ticker, fmt):
    """Insider transactions (Form 4 filings)."""
    data = fetch_av({"function": "INSIDER_TRANSACTIONS", "symbol": ticker.upper()})
    items = data.get("data", [])
    if not items:
        raise click.ClickException("No insider transaction data returned.")
    if fmt == "json":
        click.echo(json.dumps(items[:20], indent=2))
        return
    headers = list(items[0].keys())
    rows = [[item.get(h, "") for h in headers] for item in items[:20]]
    emit_table(f"{ticker.upper()} — Insider Transactions", headers, rows, fmt)


@cli.command("institutional-holdings")
@click.argument("ticker")
@fmt_opt()
def institutional_holdings(ticker, fmt):
    """Institutional holdings (13F filings)."""
    data = fetch_av({"function": "INSTITUTIONAL_HOLDINGS", "symbol": ticker.upper()})
    # Response may be nested; try common keys
    items = data.get("data") or data.get("holdings") or []
    if not items:
        raise click.ClickException("No institutional holdings data returned.")
    if fmt == "json":
        click.echo(json.dumps(items[:20], indent=2))
        return
    headers = list(items[0].keys())
    rows = [[item.get(h, "") for h in headers] for item in items[:20]]
    emit_table(f"{ticker.upper()} — Institutional Holdings", headers, rows, fmt)


# ── TECHNICAL INDICATORS ──────────────────────────────────────────────────────

def _indicator(function, ticker, fmt, period, interval, series_type):
    params = {"function": function, "symbol": ticker.upper(),
              "interval": interval, "time_period": period, "series_type": series_type}
    data = fetch_av(params)
    key = f"Technical Analysis: {function}"
    series = data.get(key)
    if not series:
        raise click.ClickException(f"No {function} data returned.")
    entries = list(series.items())[:20]
    sub_keys = list(entries[0][1].keys()) if entries else []
    headers = ["Datetime"] + sub_keys
    rows = [[dt] + [v.get(k, "") for k in sub_keys] for dt, v in entries]
    emit_table(f"{ticker.upper()} — {function} ({period})", headers, rows, fmt)


def _indicator_no_period(function, ticker, fmt, interval, series_type):
    params = {"function": function, "symbol": ticker.upper(),
              "interval": interval, "series_type": series_type}
    data = fetch_av(params)
    key = f"Technical Analysis: {function}"
    series = data.get(key)
    if not series:
        raise click.ClickException(f"No {function} data returned.")
    entries = list(series.items())[:20]
    sub_keys = list(entries[0][1].keys()) if entries else []
    headers = ["Datetime"] + sub_keys
    rows = [[dt] + [v.get(k, "") for k in sub_keys] for dt, v in entries]
    emit_table(f"{ticker.upper()} — {function}", headers, rows, fmt)


def _indicator_price_volume(function, ticker, fmt, period, interval):
    """For indicators that don't use series_type (e.g. MFI, ATR, ADX)."""
    params = {"function": function, "symbol": ticker.upper(),
              "interval": interval, "time_period": period}
    data = fetch_av(params)
    key = f"Technical Analysis: {function}"
    series = data.get(key)
    if not series:
        raise click.ClickException(f"No {function} data returned.")
    entries = list(series.items())[:20]
    sub_keys = list(entries[0][1].keys()) if entries else []
    headers = ["Datetime"] + sub_keys
    rows = [[dt] + [v.get(k, "") for k in sub_keys] for dt, v in entries]
    emit_table(f"{ticker.upper()} — {function} ({period})", headers, rows, fmt)


# Moving averages

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def sma(ticker, fmt, period, interval, series):
    """Simple Moving Average."""
    _indicator("SMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ema(ticker, fmt, period, interval, series):
    """Exponential Moving Average."""
    _indicator("EMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def wma(ticker, fmt, period, interval, series):
    """Weighted Moving Average."""
    _indicator("WMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def dema(ticker, fmt, period, interval, series):
    """Double Exponential Moving Average."""
    _indicator("DEMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def tema(ticker, fmt, period, interval, series):
    """Triple Exponential Moving Average."""
    _indicator("TEMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def kama(ticker, fmt, period, interval, series):
    """Kaufman Adaptive Moving Average."""
    _indicator("KAMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def mama(ticker, fmt, interval, series):
    """MESA Adaptive Moving Average."""
    _indicator_no_period("MAMA", ticker, fmt, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def vwap(ticker, fmt, interval):
    """Volume Weighted Average Price. (intraday intervals only)"""
    data = fetch_av({"function": "VWAP", "symbol": ticker.upper(), "interval": interval})
    series = data.get("Technical Analysis: VWAP")
    if not series:
        raise click.ClickException("No VWAP data returned. Use an intraday interval (1min–60min).")
    entries = list(series.items())[:20]
    emit_table(f"{ticker.upper()} — VWAP",
               ["Datetime", "VWAP"], [[dt, v.get("VWAP","")] for dt, v in entries], fmt)


# Oscillators & momentum

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def rsi(ticker, fmt, period, interval, series):
    """Relative Strength Index."""
    _indicator("RSI", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def macd(ticker, fmt, interval, series):
    """MACD indicator."""
    data = fetch_av({"function": "MACD", "symbol": ticker.upper(),
                     "interval": interval, "series_type": series})
    s = data.get("Technical Analysis: MACD")
    if not s:
        raise click.ClickException("No MACD data returned.")
    entries = list(s.items())[:20]
    headers = ["Datetime", "MACD", "MACD_Signal", "MACD_Hist"]
    rows = [[dt, v.get("MACD",""), v.get("MACD_Signal",""), v.get("MACD_Hist","")]
            for dt, v in entries]
    emit_table(f"{ticker.upper()} — MACD", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def bbands(ticker, fmt, period, interval, series):
    """Bollinger Bands."""
    _indicator("BBANDS", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def stoch(ticker, fmt, interval):
    """Stochastic oscillator."""
    data = fetch_av({"function": "STOCH", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: STOCH")
    if not s:
        raise click.ClickException("No STOCH data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Stochastic",
               ["Datetime", "SlowK", "SlowD"],
               [[dt, v.get("SlowK",""), v.get("SlowD","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def adx(ticker, fmt, period, interval):
    """Average Directional Index."""
    _indicator_price_volume("ADX", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def cci(ticker, fmt, period, interval):
    """Commodity Channel Index."""
    _indicator_price_volume("CCI", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def aroon(ticker, fmt, period, interval):
    """Aroon indicator."""
    _indicator_price_volume("AROON", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def mfi(ticker, fmt, period, interval):
    """Money Flow Index."""
    _indicator_price_volume("MFI", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def roc(ticker, fmt, period, interval, series):
    """Rate of Change."""
    _indicator("ROC", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def willr(ticker, fmt, period, interval, series):
    """Williams %R."""
    _indicator("WILLR", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def cmo(ticker, fmt, period, interval, series):
    """Chande Momentum Oscillator."""
    _indicator("CMO", ticker, fmt, period, interval, series)


# Volatility & volume

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def atr(ticker, fmt, period, interval):
    """Average True Range."""
    _indicator_price_volume("ATR", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def sar(ticker, fmt, interval):
    """Parabolic SAR."""
    data = fetch_av({"function": "SAR", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: SAR")
    if not s:
        raise click.ClickException("No SAR data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — SAR",
               ["Datetime", "SAR"], [[dt, v.get("SAR","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def obv(ticker, fmt, interval):
    """On-Balance Volume."""
    data = fetch_av({"function": "OBV", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: OBV")
    if not s:
        raise click.ClickException("No OBV data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — OBV",
               ["Datetime", "OBV"], [[dt, v.get("OBV","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def ad(ticker, fmt, interval):
    """Chaikin A/D Line."""
    data = fetch_av({"function": "AD", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: Chaikin A/D")
    if not s:
        raise click.ClickException("No A/D data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Chaikin A/D",
               ["Datetime", "Chaikin A/D"],
               [[dt, v.get("Chaikin A/D","")] for dt, v in entries], fmt)


# Remaining moving averages

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=20, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def trima(ticker, fmt, period, interval, series):
    """Triangular Moving Average."""
    _indicator("TRIMA", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=5, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def t3(ticker, fmt, period, interval, series):
    """Triple Exponential Moving Average (T3)."""
    _indicator("T3", ticker, fmt, period, interval, series)


# Extended oscillators & momentum

@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
@click.option("--fast-period", default=12, show_default=True)
@click.option("--slow-period", default=26, show_default=True)
@click.option("--signal-period", default=9, show_default=True)
@click.option("--fast-matype", default=0, show_default=True, help="MA type (0=SMA…8=T3)")
@click.option("--slow-matype", default=0, show_default=True)
@click.option("--signal-matype", default=0, show_default=True)
def macdext(ticker, fmt, interval, series, fast_period, slow_period, signal_period,
            fast_matype, slow_matype, signal_matype):
    """MACD with configurable MA types."""
    data = fetch_av({"function": "MACDEXT", "symbol": ticker.upper(), "interval": interval,
                     "series_type": series, "fastperiod": fast_period,
                     "slowperiod": slow_period, "signalperiod": signal_period,
                     "fastmatype": fast_matype, "slowmatype": slow_matype,
                     "signalmatype": signal_matype})
    s = data.get("Technical Analysis: MACDEXT")
    if not s:
        raise click.ClickException("No MACDEXT data returned.")
    entries = list(s.items())[:20]
    headers = ["Datetime", "MACD", "MACD_Signal", "MACD_Hist"]
    rows = [[dt, v.get("MACD",""), v.get("MACD_Signal",""), v.get("MACD_Hist","")]
            for dt, v in entries]
    emit_table(f"{ticker.upper()} — MACDEXT", headers, rows, fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--fastk-period", default=5, show_default=True)
@click.option("--fastd-period", default=3, show_default=True)
@click.option("--fastd-matype", default=0, show_default=True, help="MA type (0=SMA…8=T3)")
def stochf(ticker, fmt, interval, fastk_period, fastd_period, fastd_matype):
    """Fast Stochastic oscillator."""
    data = fetch_av({"function": "STOCHF", "symbol": ticker.upper(), "interval": interval,
                     "fastkperiod": fastk_period, "fastdperiod": fastd_period,
                     "fastdmatype": fastd_matype})
    s = data.get("Technical Analysis: STOCHF")
    if not s:
        raise click.ClickException("No STOCHF data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Stochastic Fast",
               ["Datetime", "FastK", "FastD"],
               [[dt, v.get("FastK",""), v.get("FastD","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
@click.option("--fastk-period", default=5, show_default=True)
@click.option("--fastd-period", default=3, show_default=True)
@click.option("--fastd-matype", default=0, show_default=True, help="MA type (0=SMA…8=T3)")
def stochrsi(ticker, fmt, period, interval, series, fastk_period, fastd_period, fastd_matype):
    """Stochastic RSI."""
    data = fetch_av({"function": "STOCHRSI", "symbol": ticker.upper(), "interval": interval,
                     "time_period": period, "series_type": series,
                     "fastkperiod": fastk_period, "fastdperiod": fastd_period,
                     "fastdmatype": fastd_matype})
    s = data.get("Technical Analysis: STOCHRSI")
    if not s:
        raise click.ClickException("No STOCHRSI data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Stochastic RSI ({period})",
               ["Datetime", "FastK", "FastD"],
               [[dt, v.get("FastK",""), v.get("FastD","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def apo(ticker, fmt, period, interval, series):
    """Absolute Price Oscillator."""
    _indicator("APO", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ppo(ticker, fmt, period, interval, series):
    """Percentage Price Oscillator."""
    _indicator("PPO", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=10, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def mom(ticker, fmt, period, interval, series):
    """Momentum."""
    _indicator("MOM", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def bop(ticker, fmt, interval):
    """Balance of Power."""
    data = fetch_av({"function": "BOP", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: BOP")
    if not s:
        raise click.ClickException("No BOP data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Balance of Power",
               ["Datetime", "BOP"], [[dt, v.get("BOP","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=10, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def rocr(ticker, fmt, period, interval, series):
    """Rate of Change Ratio."""
    _indicator("ROCR", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def trix(ticker, fmt, period, interval, series):
    """1-day Rate of Change of a Triple Smooth EMA."""
    _indicator("TRIX", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--period1", default=7, show_default=True, help="First time period.")
@click.option("--period2", default=14, show_default=True, help="Second time period.")
@click.option("--period3", default=28, show_default=True, help="Third time period.")
def ultosc(ticker, fmt, interval, period1, period2, period3):
    """Ultimate Oscillator (three time periods)."""
    data = fetch_av({"function": "ULTOSC", "symbol": ticker.upper(), "interval": interval,
                     "timeperiod1": period1, "timeperiod2": period2, "timeperiod3": period3})
    s = data.get("Technical Analysis: ULTOSC")
    if not s:
        raise click.ClickException("No ULTOSC data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Ultimate Oscillator ({period1}/{period2}/{period3})",
               ["Datetime", "ULTOSC"], [[dt, v.get("ULTOSC","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def adxr(ticker, fmt, period, interval):
    """Average Directional Movement Rating."""
    _indicator_price_volume("ADXR", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def dx(ticker, fmt, period, interval):
    """Directional Movement Index."""
    _indicator_price_volume("DX", ticker, fmt, period, interval)


@cli.command("minus-di")
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def minus_di(ticker, fmt, period, interval):
    """Minus Directional Indicator."""
    _indicator_price_volume("MINUS_DI", ticker, fmt, period, interval)


@cli.command("plus-di")
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def plus_di(ticker, fmt, period, interval):
    """Plus Directional Indicator."""
    _indicator_price_volume("PLUS_DI", ticker, fmt, period, interval)


@cli.command("minus-dm")
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def minus_dm(ticker, fmt, period, interval):
    """Minus Directional Movement."""
    _indicator_price_volume("MINUS_DM", ticker, fmt, period, interval)


@cli.command("plus-dm")
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def plus_dm(ticker, fmt, period, interval):
    """Plus Directional Movement."""
    _indicator_price_volume("PLUS_DM", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def midpoint(ticker, fmt, period, interval, series):
    """Midpoint over period."""
    _indicator("MIDPOINT", ticker, fmt, period, interval, series)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def midprice(ticker, fmt, period, interval):
    """Midpoint Price over period."""
    _indicator_price_volume("MIDPRICE", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def trange(ticker, fmt, interval):
    """True Range."""
    data = fetch_av({"function": "TRANGE", "symbol": ticker.upper(), "interval": interval})
    s = data.get("Technical Analysis: TRANGE")
    if not s:
        raise click.ClickException("No TRANGE data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — True Range",
               ["Datetime", "TRANGE"], [[dt, v.get("TRANGE","")] for dt, v in entries], fmt)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-p", "--period", default=14, show_default=True)
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
def natr(ticker, fmt, period, interval):
    """Normalized Average True Range."""
    _indicator_price_volume("NATR", ticker, fmt, period, interval)


@cli.command()
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--fast-period", default=3, show_default=True)
@click.option("--slow-period", default=10, show_default=True)
def adosc(ticker, fmt, interval, fast_period, slow_period):
    """Chaikin A/D Oscillator."""
    data = fetch_av({"function": "ADOSC", "symbol": ticker.upper(), "interval": interval,
                     "fastperiod": fast_period, "slowperiod": slow_period})
    s = data.get("Technical Analysis: ADOSC")
    if not s:
        raise click.ClickException("No ADOSC data returned.")
    entries = list(s.items())[:20]
    emit_table(f"{ticker.upper()} — Chaikin A/D Oscillator",
               ["Datetime", "ADOSC"], [[dt, v.get("ADOSC","")] for dt, v in entries], fmt)


# Hilbert Transform

def _ht(function, ticker, fmt, interval, series_type):
    data = fetch_av({"function": function, "symbol": ticker.upper(),
                     "interval": interval, "series_type": series_type})
    key = f"Technical Analysis: {function}"
    s = data.get(key)
    if not s:
        raise click.ClickException(f"No {function} data returned.")
    entries = list(s.items())[:20]
    sub_keys = list(entries[0][1].keys()) if entries else []
    headers = ["Datetime"] + sub_keys
    rows = [[dt] + [v.get(k,"") for k in sub_keys] for dt, v in entries]
    emit_table(f"{ticker.upper()} — {function}", headers, rows, fmt)


@cli.command("ht-trendline")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_trendline(ticker, fmt, interval, series):
    """Hilbert Transform – Instantaneous Trendline."""
    _ht("HT_TRENDLINE", ticker, fmt, interval, series)


@cli.command("ht-sine")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_sine(ticker, fmt, interval, series):
    """Hilbert Transform – SineWave."""
    _ht("HT_SINE", ticker, fmt, interval, series)


@cli.command("ht-trendmode")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_trendmode(ticker, fmt, interval, series):
    """Hilbert Transform – Trend vs Cycle Mode."""
    _ht("HT_TRENDMODE", ticker, fmt, interval, series)


@cli.command("ht-dcperiod")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_dcperiod(ticker, fmt, interval, series):
    """Hilbert Transform – Dominant Cycle Period."""
    _ht("HT_DCPERIOD", ticker, fmt, interval, series)


@cli.command("ht-dcphase")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_dcphase(ticker, fmt, interval, series):
    """Hilbert Transform – Dominant Cycle Phase."""
    _ht("HT_DCPHASE", ticker, fmt, interval, series)


@cli.command("ht-phasor")
@click.argument("ticker")
@fmt_opt()
@click.option("-i", "--interval", default="daily", type=INTERVAL_CHOICE, show_default=True)
@click.option("--series", default="close", type=SERIES_CHOICE, show_default=True)
def ht_phasor(ticker, fmt, interval, series):
    """Hilbert Transform – Phasor Components."""
    _ht("HT_PHASOR", ticker, fmt, interval, series)


# ── OPTIONS ───────────────────────────────────────────────────────────────────

@cli.command("options")
@click.argument("ticker")
@fmt_opt()
@click.option("--greeks", is_flag=True, default=False, help="Include Greeks and IV.")
@click.option("--contract", default=None, help="Specific contract ID.")
def options(ticker, fmt, greeks, contract):
    """Real-time options chain. [premium]"""
    params = {"function": "REALTIME_OPTIONS", "symbol": ticker.upper()}
    if greeks:
        params["require_greeks"] = "true"
    if contract:
        params["contract"] = contract
    data = fetch_av(params)
    chain = data.get("data", [])
    if not chain:
        raise click.ClickException("No options data returned. (Requires premium key)")
    if fmt == "json":
        click.echo(json.dumps(chain[:20], indent=2))
        return
    # Build table from first record's keys
    headers = list(chain[0].keys())
    rows = [[item.get(h, "") for h in headers] for item in chain[:20]]
    emit_table(f"{ticker.upper()} — Options Chain (sample of 20)", headers, rows, fmt)


@cli.command("historical-options")
@click.argument("ticker")
@fmt_opt()
@click.option("--date", default=None, help="Date YYYY-MM-DD (defaults to last session).")
def historical_options(ticker, fmt, date):
    """Historical options chain with Greeks and IV. [premium]"""
    params = {"function": "HISTORICAL_OPTIONS", "symbol": ticker.upper()}
    if date:
        params["date"] = date
    data = fetch_av(params)
    chain = data.get("data", [])
    if not chain:
        raise click.ClickException("No historical options data returned. (Requires premium key)")
    if fmt == "json":
        click.echo(json.dumps(chain[:20], indent=2))
        return
    headers = list(chain[0].keys())
    rows = [[item.get(h, "") for h in headers] for item in chain[:20]]
    label = f"{ticker.upper()} — Historical Options"
    if date:
        label += f" ({date})"
    emit_table(label + " (sample of 20)", headers, rows, fmt)


# ── FOREX ──────────────────────────────────────────────────────────────────────

@cli.command("fx-rate")
@click.argument("from_currency")
@click.argument("to_currency")
@fmt_opt()
def fx_rate(from_currency, to_currency, fmt):
    """Real-time currency exchange rate."""
    data = fetch_av({"function": "CURRENCY_EXCHANGE_RATE",
                     "from_currency": from_currency.upper(),
                     "to_currency": to_currency.upper()})
    r = data.get("Realtime Currency Exchange Rate", {})
    if not r:
        raise click.ClickException("No exchange rate data returned.")
    fields = {
        "From":           r.get("1. From_Currency Code", ""),
        "From Name":      r.get("2. From_Currency Name", ""),
        "To":             r.get("3. To_Currency Code", ""),
        "To Name":        r.get("4. To_Currency Name", ""),
        "Exchange Rate":  r.get("5. Exchange Rate", ""),
        "Last Refreshed": r.get("6. Last Refreshed", ""),
        "Time Zone":      r.get("7. Time Zone", ""),
        "Bid Price":      r.get("8. Bid Price", ""),
        "Ask Price":      r.get("9. Ask Price", ""),
    }
    emit_kv(f"{from_currency.upper()}/{to_currency.upper()} — Exchange Rate", fields, fmt)


@cli.command("fx-intraday")
@click.argument("from_currency")
@click.argument("to_currency")
@fmt_opt()
@click.option("-i", "--interval", default="5min",
              type=click.Choice(["1min","5min","15min","30min","60min"]), show_default=True)
@days_opt(default=20)
def fx_intraday(from_currency, to_currency, fmt, interval, days):
    """Intraday forex OHLC time series. [premium]"""
    data = fetch_av({"function": "FX_INTRADAY",
                     "from_symbol": from_currency.upper(),
                     "to_symbol": to_currency.upper(),
                     "interval": interval, "outputsize": "compact"})
    series = data.get(f"Time Series FX ({interval})")
    if not series:
        raise click.ClickException("No data returned. (Requires premium key)")
    entries = list(series.items())[:days]
    headers = ["Datetime", "Open", "High", "Low", "Close"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"]]
            for dt, v in entries]
    emit_table(f"{from_currency.upper()}/{to_currency.upper()} — Intraday FX {interval}",
               headers, rows, fmt)


@cli.command("fx-daily")
@click.argument("from_currency")
@click.argument("to_currency")
@fmt_opt()
@days_opt(default=10)
def fx_daily(from_currency, to_currency, fmt, days):
    """Daily forex OHLC time series."""
    data = fetch_av({"function": "FX_DAILY",
                     "from_symbol": from_currency.upper(),
                     "to_symbol": to_currency.upper()})
    series = data.get("Time Series FX (Daily)")
    if not series:
        raise click.ClickException("No forex daily data returned.")
    entries = list(series.items())[:days]
    headers = ["Date", "Open", "High", "Low", "Close"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"]]
            for dt, v in entries]
    emit_table(f"{from_currency.upper()}/{to_currency.upper()} — Daily FX", headers, rows, fmt)


@cli.command("fx-weekly")
@click.argument("from_currency")
@click.argument("to_currency")
@fmt_opt()
@days_opt(default=10)
def fx_weekly(from_currency, to_currency, fmt, days):
    """Weekly forex OHLC time series."""
    data = fetch_av({"function": "FX_WEEKLY",
                     "from_symbol": from_currency.upper(),
                     "to_symbol": to_currency.upper()})
    series = data.get("Time Series FX (Weekly)")
    if not series:
        raise click.ClickException("No forex weekly data returned.")
    entries = list(series.items())[:days]
    headers = ["Week", "Open", "High", "Low", "Close"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"]]
            for dt, v in entries]
    emit_table(f"{from_currency.upper()}/{to_currency.upper()} — Weekly FX", headers, rows, fmt)


@cli.command("fx-monthly")
@click.argument("from_currency")
@click.argument("to_currency")
@fmt_opt()
@days_opt(default=12)
def fx_monthly(from_currency, to_currency, fmt, days):
    """Monthly forex OHLC time series."""
    data = fetch_av({"function": "FX_MONTHLY",
                     "from_symbol": from_currency.upper(),
                     "to_symbol": to_currency.upper()})
    series = data.get("Time Series FX (Monthly)")
    if not series:
        raise click.ClickException("No forex monthly data returned.")
    entries = list(series.items())[:days]
    headers = ["Month", "Open", "High", "Low", "Close"]
    rows = [[dt, v["1. open"], v["2. high"], v["3. low"], v["4. close"]]
            for dt, v in entries]
    emit_table(f"{from_currency.upper()}/{to_currency.upper()} — Monthly FX", headers, rows, fmt)


# ── CRYPTO ─────────────────────────────────────────────────────────────────────

@cli.command("crypto-rate")
@click.argument("coin")
@click.argument("market", default="USD")
@fmt_opt()
def crypto_rate(coin, market, fmt):
    """Real-time cryptocurrency exchange rate."""
    data = fetch_av({"function": "CURRENCY_EXCHANGE_RATE",
                     "from_currency": coin.upper(),
                     "to_currency": market.upper()})
    r = data.get("Realtime Currency Exchange Rate", {})
    if not r:
        raise click.ClickException("No crypto rate data returned.")
    fields = {
        "Coin":           r.get("1. From_Currency Code", ""),
        "Coin Name":      r.get("2. From_Currency Name", ""),
        "Market":         r.get("3. To_Currency Code", ""),
        "Exchange Rate":  r.get("5. Exchange Rate", ""),
        "Last Refreshed": r.get("6. Last Refreshed", ""),
        "Bid Price":      r.get("8. Bid Price", ""),
        "Ask Price":      r.get("9. Ask Price", ""),
    }
    emit_kv(f"{coin.upper()}/{market.upper()} — Crypto Rate", fields, fmt)


@cli.command("crypto-intraday")
@click.argument("coin")
@click.argument("market", default="USD")
@fmt_opt()
@click.option("-i", "--interval", default="5min",
              type=click.Choice(["1min","5min","15min","30min","60min"]), show_default=True)
@days_opt(default=20)
def crypto_intraday(coin, market, fmt, interval, days):
    """Intraday cryptocurrency OHLCV series. [premium]"""
    data = fetch_av({"function": "CRYPTO_INTRADAY", "symbol": coin.upper(),
                     "market": market.upper(), "interval": interval, "outputsize": "compact"})
    series = data.get(f"Time Series Crypto ({interval})")
    if not series:
        raise click.ClickException("No data returned. (Requires premium key)")
    entries = list(series.items())[:days]
    headers = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
    rows = [[dt, v.get("1. open",""), v.get("2. high",""), v.get("3. low",""),
             v.get("4. close",""), v.get("5. volume","")]
            for dt, v in entries]
    emit_table(f"{coin.upper()}/{market.upper()} — Intraday Crypto {interval}",
               headers, rows, fmt)


@cli.command("crypto-daily")
@click.argument("coin")
@click.argument("market", default="USD")
@fmt_opt()
@days_opt(default=10)
def crypto_daily(coin, market, fmt, days):
    """Daily cryptocurrency OHLCV series."""
    data = fetch_av({"function": "CURRENCY_DAILY",
                     "symbol": coin.upper(), "market": market.upper()})
    series = data.get("Time Series (Digital Currency Daily)")
    if not series:
        raise click.ClickException("No crypto daily data returned.")
    m = market.upper()
    entries = list(series.items())[:days]
    headers = ["Date", f"Open ({m})", f"High ({m})", f"Low ({m})", f"Close ({m})", "Volume"]
    rows = [
        [dt, v.get(f"1a. open ({m})",""), v.get(f"2a. high ({m})",""),
         v.get(f"3a. low ({m})",""), v.get(f"4a. close ({m})",""), v.get("5. volume","")]
        for dt, v in entries
    ]
    emit_table(f"{coin.upper()}/{m} — Daily Crypto", headers, rows, fmt)


@cli.command("crypto-weekly")
@click.argument("coin")
@click.argument("market", default="USD")
@fmt_opt()
@days_opt(default=10)
def crypto_weekly(coin, market, fmt, days):
    """Weekly cryptocurrency OHLCV series."""
    data = fetch_av({"function": "CURRENCY_WEEKLY",
                     "symbol": coin.upper(), "market": market.upper()})
    series = data.get("Time Series (Digital Currency Weekly)")
    if not series:
        raise click.ClickException("No crypto weekly data returned.")
    m = market.upper()
    entries = list(series.items())[:days]
    headers = ["Week", f"Open ({m})", f"High ({m})", f"Low ({m})", f"Close ({m})", "Volume"]
    rows = [
        [dt, v.get(f"1a. open ({m})",""), v.get(f"2a. high ({m})",""),
         v.get(f"3a. low ({m})",""), v.get(f"4a. close ({m})",""), v.get("5. volume","")]
        for dt, v in entries
    ]
    emit_table(f"{coin.upper()}/{m} — Weekly Crypto", headers, rows, fmt)


@cli.command("crypto-monthly")
@click.argument("coin")
@click.argument("market", default="USD")
@fmt_opt()
@days_opt(default=12)
def crypto_monthly(coin, market, fmt, days):
    """Monthly cryptocurrency OHLCV series."""
    data = fetch_av({"function": "CURRENCY_MONTHLY",
                     "symbol": coin.upper(), "market": market.upper()})
    series = data.get("Time Series (Digital Currency Monthly)")
    if not series:
        raise click.ClickException("No crypto monthly data returned.")
    m = market.upper()
    entries = list(series.items())[:days]
    headers = ["Month", f"Open ({m})", f"High ({m})", f"Low ({m})", f"Close ({m})", "Volume"]
    rows = [
        [dt, v.get(f"1a. open ({m})",""), v.get(f"2a. high ({m})",""),
         v.get(f"3a. low ({m})",""), v.get(f"4a. close ({m})",""), v.get("5. volume","")]
        for dt, v in entries
    ]
    emit_table(f"{coin.upper()}/{m} — Monthly Crypto", headers, rows, fmt)


# ── ECONOMIC INDICATORS ────────────────────────────────────────────────────────

def _econ(function, title, fmt, interval=None):
    params = {"function": function}
    if interval:
        params["interval"] = interval
    data = fetch_av(params)
    series = data.get("data")
    if not series:
        raise click.ClickException(f"No data returned for {function}.")
    rows = [[e.get("date",""), e.get("value","")] for e in series[:20]]
    emit_table(title, ["Date", "Value"], rows, fmt)


@cli.command()
@fmt_opt()
@click.option("--interval", default="annual",
              type=click.Choice(["annual", "quarterly"]), show_default=True)
def gdp(fmt, interval):
    """US Real GDP."""
    _econ("REAL_GDP", f"US Real GDP ({interval})", fmt, interval)


@cli.command("gdp-per-capita")
@fmt_opt()
def gdp_per_capita(fmt):
    """US Real GDP per capita (annual)."""
    _econ("REAL_GDP_PER_CAPITA", "US Real GDP per Capita (annual)", fmt)


@cli.command()
@fmt_opt()
@click.option("--interval", default="monthly",
              type=click.Choice(["monthly", "semiannual"]), show_default=True)
def cpi(fmt, interval):
    """US Consumer Price Index."""
    _econ("CPI", f"US CPI ({interval})", fmt, interval)


@cli.command()
@fmt_opt()
@click.option("--maturity", default="10year",
              type=click.Choice(["3month","2year","5year","7year","10year","30year"]),
              show_default=True)
def treasury(fmt, maturity):
    """US Treasury yield."""
    data = fetch_av({"function": "TREASURY_YIELD", "interval": "monthly", "maturity": maturity})
    rows = [[e.get("date",""), e.get("value","")] for e in data.get("data",[])[:20]]
    emit_table(f"US Treasury Yield — {maturity}", ["Date", "Yield %"], rows, fmt)


@cli.command("fed-rate")
@fmt_opt()
def fed_rate(fmt):
    """US Federal funds rate."""
    _econ("FEDERAL_FUNDS_RATE", "US Federal Funds Rate (monthly)", fmt, "monthly")


@cli.command()
@fmt_opt()
def unemployment(fmt):
    """US unemployment rate."""
    _econ("UNEMPLOYMENT", "US Unemployment Rate (monthly)", fmt)


@cli.command()
@fmt_opt()
def inflation(fmt):
    """US inflation rate (annual)."""
    _econ("INFLATION", "US Inflation Rate (annual)", fmt)


@cli.command("retail-sales")
@fmt_opt()
def retail_sales(fmt):
    """US monthly retail sales."""
    _econ("RETAIL_SALES", "US Retail Sales (monthly)", fmt)


@cli.command()
@fmt_opt()
def durables(fmt):
    """US durable goods orders."""
    _econ("DURABLE_GOODS_ORDERS", "US Durable Goods Orders (monthly)", fmt)


@cli.command("nonfarm-payroll")
@fmt_opt()
def nonfarm_payroll(fmt):
    """US nonfarm payroll employment."""
    _econ("NONFARM_PAYROLL", "US Nonfarm Payroll (monthly)", fmt)


# ── COMMODITIES ────────────────────────────────────────────────────────────────

def _commodity(function, title, fmt):
    data = fetch_av({"function": function, "interval": "monthly"})
    rows = [[e.get("date",""), e.get("value","")] for e in data.get("data",[])[:20]]
    emit_table(title, ["Date", "Price (USD)"], rows, fmt)


@cli.command()
@fmt_opt()
def wti(fmt):
    """WTI crude oil price (monthly)."""
    _commodity("WTI", "WTI Crude Oil — Monthly", fmt)


@cli.command()
@fmt_opt()
def brent(fmt):
    """Brent crude oil price (monthly)."""
    _commodity("BRENT", "Brent Crude Oil — Monthly", fmt)


@cli.command()
@fmt_opt()
def natgas(fmt):
    """Natural gas price (monthly)."""
    _commodity("NATURAL_GAS", "Natural Gas — Monthly", fmt)


@cli.command()
@fmt_opt()
def copper(fmt):
    """Copper price (monthly)."""
    _commodity("COPPER", "Copper — Monthly", fmt)


@cli.command()
@fmt_opt()
def aluminum(fmt):
    """Aluminum price (monthly)."""
    _commodity("ALUMINUM", "Aluminum — Monthly", fmt)


@cli.command()
@fmt_opt()
def wheat(fmt):
    """Wheat price (monthly)."""
    _commodity("WHEAT", "Wheat — Monthly", fmt)


@cli.command()
@fmt_opt()
def corn(fmt):
    """Corn price (monthly)."""
    _commodity("CORN", "Corn — Monthly", fmt)


@cli.command()
@fmt_opt()
def cotton(fmt):
    """Cotton price (monthly)."""
    _commodity("COTTON", "Cotton — Monthly", fmt)


@cli.command()
@fmt_opt()
def sugar(fmt):
    """Sugar price (monthly)."""
    _commodity("SUGAR", "Sugar — Monthly", fmt)


@cli.command()
@fmt_opt()
def coffee(fmt):
    """Coffee price (monthly)."""
    _commodity("COFFEE", "Coffee — Monthly", fmt)


@cli.command("all-commodities")
@fmt_opt()
def all_commodities(fmt):
    """Global commodities index (monthly)."""
    _commodity("ALL_COMMODITIES", "Global Commodities Index — Monthly", fmt)


@cli.command("metal-spot")
@click.argument("metal", type=click.Choice(["GOLD", "XAU", "SILVER", "XAG"],
                                            case_sensitive=False))
@fmt_opt()
def metal_spot(metal, fmt):
    """Live gold or silver spot price."""
    data = fetch_av({"function": "GOLD_SILVER_SPOT", "symbol": metal.upper()})
    if not data:
        raise click.ClickException("No spot price data returned.")
    if fmt == "json":
        click.echo(json.dumps(data, indent=2))
        return
    # Flatten whatever fields come back
    if isinstance(data, dict):
        flat = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
        emit_kv(f"{metal.upper()} — Live Spot Price", flat, fmt)
    else:
        click.echo(str(data))


@cli.command("metal-history")
@click.argument("metal", type=click.Choice(["GOLD", "XAU", "SILVER", "XAG"],
                                            case_sensitive=False))
@fmt_opt()
@click.option("--interval", default="daily",
              type=click.Choice(["daily", "weekly", "monthly"]), show_default=True)
@days_opt(default=20)
def metal_history(metal, fmt, interval, days):
    """Historical gold or silver prices (daily/weekly/monthly)."""
    data = fetch_av({"function": "GOLD_SILVER_HISTORY",
                     "symbol": metal.upper(), "interval": interval})
    # Find the time series key
    series = None
    for key, val in data.items():
        if isinstance(val, dict) and key != "Meta Data":
            series = val
            break
    if not series:
        raise click.ClickException("No historical data returned.")
    entries = list(series.items())[:days]
    # Detect available columns from first entry
    if entries:
        sub_keys = list(entries[0][1].keys()) if isinstance(entries[0][1], dict) else ["value"]
        headers = ["Date"] + sub_keys
        rows = [[dt] + ([v.get(k, "") for k in sub_keys] if isinstance(v, dict) else [v])
                for dt, v in entries]
    else:
        headers, rows = ["Date", "Value"], []
    emit_table(f"{metal.upper()} — {interval.capitalize()} History", headers, rows, fmt)


if __name__ == "__main__":
    cli()
