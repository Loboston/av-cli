# av-cli

A Python CLI tool for the [Alpha Vantage](https://www.alphavantage.co/) financial data API. Returns clean **Markdown**, **JSON**, or **CSV** output — easy to read in a terminal or pipe into AI agents and workflows.

## Setup

### 1. Install dependencies

```bash
pip install click
```

### 2. Set your API key

Get a free key at https://www.alphavantage.co/support/#api-key, then export it:

```bash
export ALPHA_VANTAGE_KEY=your_key_here
```

Add it to your `~/.bashrc` or `~/.zshrc` to persist it.

### 3. Install globally as `av`

```bash
pip install -e .
```

After installing, use `av` from anywhere. Otherwise use `python av.py`.

---

## Output formats

Every command supports three output formats via `-f` / `--format`:

| Format | Description |
|---|---|
| `markdown` | Human-readable table (default) |
| `json` | Machine-readable, ideal for AI agents / scripting |
| `csv` | Pipe into spreadsheets or other tools |

```bash
av quote AAPL                     # markdown (default)
av quote AAPL -f json             # JSON
av daily MSFT -f csv              # CSV
```

---

## Commands

### Stocks

| Command | Description |
|---|---|
| `quote <ticker>` | Real-time stock quote |
| `intraday <ticker>` | Intraday OHLCV (`-i` for interval: 1/5/15/30/60min) `[premium]` |
| `daily <ticker>` | Daily OHLCV time series |
| `daily-adjusted <ticker>` | Daily adjusted close + split/dividend events `[premium]` |
| `weekly <ticker>` | Weekly OHLCV |
| `weekly-adjusted <ticker>` | Weekly adjusted close + dividends |
| `monthly <ticker>` | Monthly OHLCV |
| `monthly-adjusted <ticker>` | Monthly adjusted close + dividends |
| `search <query>` | Search for a ticker by keyword |
| `market-status` | Current open/closed status for global exchanges |
| `bulk-quotes <t1> <t2> ...` | Real-time quotes for up to 100 tickers `[premium]` |

### Fundamentals

| Command | Description |
|---|---|
| `overview <ticker>` | Company overview, valuation ratios, moving averages |
| `etf-profile <ticker>` | ETF profile and top holdings |
| `income <ticker>` | Annual income statement |
| `balance <ticker>` | Annual balance sheet |
| `cashflow <ticker>` | Annual cash flow statement |
| `earnings <ticker>` | Quarterly EPS with surprise/estimate |
| `earnings-estimates <ticker>` | Analyst EPS and revenue estimates |
| `earnings-calendar` | Upcoming earnings announcements |
| `earnings-transcript <ticker> <quarter>` | Earnings call transcript `[premium]` |
| `dividends <ticker>` | Historical and declared dividend distributions |
| `splits <ticker>` | Historical stock splits |
| `shares-outstanding <ticker>` | Quarterly shares outstanding (diluted + basic) |
| `ipo-calendar` | Upcoming IPOs |
| `listing-status` | Active or delisted US stocks/ETFs |

### Alpha Intelligence

| Command | Description |
|---|---|
| `news <ticker>` | Latest news articles with sentiment scores |
| `market-movers` | Top gainers, losers, and most active |
| `insider-transactions <ticker>` | Insider trades (Form 4 filings) |
| `institutional-holdings <ticker>` | Institutional ownership (13F filings) |

### Options

| Command | Description |
|---|---|
| `options <ticker>` | Real-time options chain (add `--greeks` for delta/gamma/IV) `[premium]` |
| `historical-options <ticker>` | Historical options chain with Greeks `[premium]` |

### Technical Indicators

All indicators accept `-i/--interval` (1min/5min/15min/30min/60min/daily/weekly/monthly) and most accept `-p/--period`.

**Moving averages:** `sma`, `ema`, `wma`, `dema`, `tema`, `trima`, `kama`, `mama`, `t3`, `vwap`

**Oscillators & momentum:** `rsi`, `macd`, `macdext`, `stoch`, `stochf`, `stochrsi`, `bbands`, `cci`, `cmo`, `roc`, `rocr`, `mom`, `bop`, `apo`, `ppo`, `trix`, `ultosc`, `willr`, `aroon`, `adx`, `adxr`, `dx`, `minus-di`, `plus-di`, `minus-dm`, `plus-dm`, `mfi`, `sar`

**Volatility & price:** `atr`, `natr`, `trange`, `midpoint`, `midprice`

**Volume:** `obv`, `ad`, `adosc`

**Hilbert Transform:** `ht-trendline`, `ht-sine`, `ht-trendmode`, `ht-dcperiod`, `ht-dcphase`, `ht-phasor`

### Forex

| Command | Description |
|---|---|
| `fx-rate <from> <to>` | Real-time exchange rate |
| `fx-intraday <from> <to>` | Intraday OHLC `[premium]` |
| `fx-daily <from> <to>` | Daily OHLC |
| `fx-weekly <from> <to>` | Weekly OHLC |
| `fx-monthly <from> <to>` | Monthly OHLC |

### Cryptocurrency

| Command | Description |
|---|---|
| `crypto-rate <coin> [market]` | Real-time exchange rate (default market: USD) |
| `crypto-intraday <coin> [market]` | Intraday OHLCV `[premium]` |
| `crypto-daily <coin> [market]` | Daily OHLCV |
| `crypto-weekly <coin> [market]` | Weekly OHLCV |
| `crypto-monthly <coin> [market]` | Monthly OHLCV |

### Economic Indicators

| Command | Description |
|---|---|
| `gdp` | US Real GDP (annual or quarterly) |
| `gdp-per-capita` | US Real GDP per capita |
| `cpi` | Consumer Price Index |
| `treasury` | Treasury yield (`--maturity` 3month to 30year) |
| `fed-rate` | Federal funds rate |
| `unemployment` | Unemployment rate |
| `inflation` | Inflation rate |
| `retail-sales` | Monthly retail sales |
| `durables` | Durable goods orders |
| `nonfarm-payroll` | Nonfarm payroll employment |

### Commodities

| Command | Description |
|---|---|
| `wti` | WTI crude oil (monthly) |
| `brent` | Brent crude oil (monthly) |
| `natgas` | Natural gas (monthly) |
| `copper` | Copper (monthly) |
| `aluminum` | Aluminum (monthly) |
| `wheat` | Wheat (monthly) |
| `corn` | Corn (monthly) |
| `cotton` | Cotton (monthly) |
| `sugar` | Sugar (monthly) |
| `coffee` | Coffee (monthly) |
| `all-commodities` | Global commodities index (monthly) |
| `metal-spot <GOLD\|XAU\|SILVER\|XAG>` | Live gold or silver spot price |
| `metal-history <symbol>` | Historical gold/silver prices (daily/weekly/monthly) |

---

## Example output

```
av quote AAPL
```
```
# AAPL — Stock Quote

| Field              | Value        |
|--------------------|--------------|
| Symbol             | AAPL         |
| Open               | 189.50       |
| High               | 191.20       |
| Low                | 188.80       |
| Price              | 190.45       |
| Volume             | 52341890     |
| Latest Trading Day | 2024-01-15   |
| Previous Close     | 188.10       |
| Change             | 2.35         |
| Change %           | 1.2499%      |
```

```
av daily AAPL --days 3
```
```
# AAPL — Daily (last 3 days)

| Date       | Open   | High   | Low    | Close  | Volume   |
|------------|--------|--------|--------|--------|----------|
| 2024-01-15 | 189.50 | 191.20 | 188.80 | 190.45 | 52341890 |
| 2024-01-12 | 186.00 | 189.30 | 185.50 | 188.10 | 48902341 |
| 2024-01-11 | 183.50 | 186.40 | 183.00 | 186.00 | 45123456 |
```

---

## Notes

- Free tier: **25 requests/day**, **5 requests/minute**. Commands marked `[premium]` require a paid key.
- Tickers are case-insensitive (`aapl` and `AAPL` both work).
- Use `--days` / `-n` on time series commands to limit the number of rows returned.
- Only runtime dependency is `click`; HTTP uses Python's built-in `urllib`.
- Run `av --help` or `av <command> --help` for full options on any command.
