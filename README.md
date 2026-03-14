# av-cli

A Python CLI tool for querying the [Alpha Vantage](https://www.alphavantage.co/) stock market API. Outputs clean **Markdown** tables or **JSON**.

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

### 3. (Optional) Install globally as `av`

```bash
pip install -e .
```

After installing, use `av` from anywhere. Otherwise use `python av.py`.

---

## Commands

### `quote <ticker>` — Real-time stock quote

```bash
av quote AAPL
av quote MSFT --format json
python av.py quote TSLA -f markdown
```

**Markdown output:**
```
# AAPL — Stock Quote

| Field             | Value                    |
|-------------------|--------------------------|
| Symbol            | AAPL                     |
| Open              | 189.50                   |
| High              | 191.20                   |
| Low               | 188.80                   |
| Price             | 190.45                   |
| Volume            | 52341890                 |
| Latest Trading Day| 2024-01-15               |
| Previous Close    | 188.10                   |
| Change            | 2.35                     |
| Change %          | 1.2499%                  |
```

---

### `daily <ticker>` — Daily OHLCV time series

```bash
av daily AAPL
av daily GOOGL --days 5
av daily NVDA --format json --days 30
```

Options:
- `-n, --days <number>` — number of trading days to display (default: `10`)
- `-f, --format <format>` — `markdown` or `json` (default: `markdown`)

**Markdown output:**
```
# AAPL — Daily Time Series (last 10 days)

| Date       | Open      | High      | Low       | Close     | Volume     |
|------------|-----------|-----------|-----------|-----------|------------|
| 2024-01-15 | 189.50    | 191.20    | 188.80    | 190.45    | 52341890   |
| 2024-01-12 | 186.00    | 189.30    | 185.50    | 188.10    | 48902341   |
...
```

---

### `overview <ticker>` — Company fundamentals

```bash
av overview AAPL
av overview AMZN --format json
```

**Markdown output:**
```
# AAPL — Apple Inc

> Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables…

| Field                  | Value                          |
|------------------------|--------------------------------|
| Exchange               | NASDAQ                         |
| Sector                 | TECHNOLOGY                     |
| MarketCapitalization   | 2950000000000                  |
| PERatio                | 29.5                           |
| EPS                    | 6.43                           |
| 52WeekHigh             | 199.62                         |
| 52WeekLow              | 124.17                         |
...
```

---

## Environment Variables

| Variable            | Description                        |
|---------------------|------------------------------------|
| `ALPHA_VANTAGE_KEY` | Your Alpha Vantage API key (required) |

---

## Notes

- The free Alpha Vantage tier allows **25 requests/day** and **5 requests/minute**.
- Tickers are case-insensitive (`aapl` and `AAPL` both work).
- `daily` returns full daily history; use `--days` to limit output rows.
- The only dependency is `click`; HTTP requests use Python's built-in `urllib`.
