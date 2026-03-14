#!/usr/bin/env python3
"""av — Alpha Vantage stock market CLI"""

import json
import os
import sys
import urllib.parse
import urllib.request

import click

BASE_URL = "https://www.alphavantage.co/query"


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


# ── Formatters ────────────────────────────────────────────────────────────────

def format_quote(data, fmt):
    q = data.get("Global Quote", {})
    if not q or not q.get("01. symbol"):
        raise click.ClickException("No quote data returned. Check the ticker symbol.")

    fields = {
        "Symbol":            q.get("01. symbol", ""),
        "Open":              q.get("02. open", ""),
        "High":              q.get("03. high", ""),
        "Low":               q.get("04. low", ""),
        "Price":             q.get("05. price", ""),
        "Volume":            q.get("06. volume", ""),
        "Latest Trading Day": q.get("07. latest trading day", ""),
        "Previous Close":    q.get("08. previous close", ""),
        "Change":            q.get("09. change", ""),
        "Change %":          q.get("10. change percent", ""),
    }

    if fmt == "json":
        click.echo(json.dumps(fields, indent=2))
        return

    lines = [
        f"# {fields['Symbol']} — Stock Quote",
        "",
        f"| {'Field':<17} | {'Value':<24} |",
        f"|{'-'*19}|{'-'*26}|",
    ]
    for k, v in fields.items():
        lines.append(f"| {k:<17} | {str(v):<24} |")
    click.echo("\n".join(lines))


def format_daily(data, fmt, limit):
    meta = data.get("Meta Data", {})
    series = data.get("Time Series (Daily)")
    if not series:
        raise click.ClickException("No time series data returned. Check the ticker symbol.")

    symbol = meta.get("2. Symbol", "")
    entries = list(series.items())[:limit]

    if fmt == "json":
        click.echo(json.dumps({"symbol": symbol, "data": dict(entries)}, indent=2))
        return

    rows = [
        f"| {date} | {v['1. open']} | {v['2. high']} | {v['3. low']} | {v['4. close']} | {v['5. volume']} |"
        for date, v in entries
    ]
    lines = [
        f"# {symbol} — Daily Time Series (last {len(entries)} days)",
        "",
        f"| {'Date':<10} | {'Open':<9} | {'High':<9} | {'Low':<9} | {'Close':<9} | {'Volume':<10} |",
        f"|{'-'*12}|{'-'*11}|{'-'*11}|{'-'*11}|{'-'*11}|{'-'*12}|",
        *rows,
    ]
    click.echo("\n".join(lines))


def format_overview(data, fmt):
    if not data.get("Symbol"):
        raise click.ClickException("No company overview returned. Check the ticker symbol.")

    field_keys = [
        "Symbol", "Name", "Description", "Exchange", "Currency", "Country",
        "Sector", "Industry", "MarketCapitalization", "EBITDA", "PERatio",
        "PEGRatio", "BookValue", "DividendPerShare", "DividendYield",
        "EPS", "52WeekHigh", "52WeekLow", "AnalystTargetPrice",
    ]
    subset = {k: data.get(k, "N/A") for k in field_keys}

    if fmt == "json":
        click.echo(json.dumps(subset, indent=2))
        return

    desc = subset["Description"]
    desc_line = (desc[:120] + "…") if len(desc) > 120 else desc
    table_keys = [k for k in field_keys if k != "Description"]

    lines = [
        f"# {subset['Symbol']} — {subset['Name']}",
        "",
        f"> {desc_line}",
        "",
        f"| {'Field':<22} | {'Value':<30} |",
        f"|{'-'*24}|{'-'*32}|",
        *[f"| {k:<22} | {str(subset[k]):<30} |" for k in table_keys],
    ]
    click.echo("\n".join(lines))


# ── Commands ──────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0")
def cli():
    """av — Alpha Vantage CLI: query stock data from the command line."""


@cli.command()
@click.argument("ticker")
@click.option("-f", "--format", "fmt", default="markdown",
              type=click.Choice(["markdown", "json"]), show_default=True,
              help="Output format.")
def quote(ticker, fmt):
    """Get a real-time stock quote."""
    data = fetch_av({"function": "GLOBAL_QUOTE", "symbol": ticker.upper()})
    format_quote(data, fmt)


@cli.command()
@click.argument("ticker")
@click.option("-f", "--format", "fmt", default="markdown",
              type=click.Choice(["markdown", "json"]), show_default=True,
              help="Output format.")
@click.option("-n", "--days", default=10, show_default=True,
              help="Number of trading days to show.")
def daily(ticker, fmt, days):
    """Get daily OHLCV time series."""
    data = fetch_av({"function": "TIME_SERIES_DAILY", "symbol": ticker.upper()})
    format_daily(data, fmt, days)


@cli.command()
@click.argument("ticker")
@click.option("-f", "--format", "fmt", default="markdown",
              type=click.Choice(["markdown", "json"]), show_default=True,
              help="Output format.")
def overview(ticker, fmt):
    """Get company overview and fundamentals."""
    data = fetch_av({"function": "OVERVIEW", "symbol": ticker.upper()})
    format_overview(data, fmt)


if __name__ == "__main__":
    cli()
