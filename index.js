#!/usr/bin/env node
'use strict';

const { program } = require('commander');
const fetch = require('node-fetch');

const BASE_URL = 'https://www.alphavantage.co/query';

function getApiKey() {
  const key = process.env.ALPHA_VANTAGE_KEY;
  if (!key) {
    console.error('Error: ALPHA_VANTAGE_KEY environment variable is not set.');
    process.exit(1);
  }
  return key;
}

async function fetchAV(params) {
  const apikey = getApiKey();
  const url = new URL(BASE_URL);
  url.search = new URLSearchParams({ ...params, apikey }).toString();
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  const data = await res.json();
  if (data['Error Message']) throw new Error(data['Error Message']);
  if (data['Note']) console.warn('Warning:', data['Note']);
  return data;
}

// ── Formatters ──────────────────────────────────────────────────────────────

function formatQuote(data, format) {
  const q = data['Global Quote'];
  if (!q || !q['01. symbol']) throw new Error('No quote data returned. Check the ticker symbol.');

  const fields = {
    Symbol:          q['01. symbol'],
    Open:            q['02. open'],
    High:            q['03. high'],
    Low:             q['04. low'],
    Price:           q['05. price'],
    Volume:          q['06. volume'],
    'Latest Trading Day': q['07. latest trading day'],
    'Previous Close': q['08. previous close'],
    Change:          q['09. change'],
    'Change %':      q['10. change percent'],
  };

  if (format === 'json') return JSON.stringify(fields, null, 2);

  const sign = parseFloat(fields['Change']) >= 0 ? '+' : '';
  return [
    `# ${fields.Symbol} — Stock Quote`,
    '',
    `| Field             | Value                    |`,
    `|-------------------|--------------------------|`,
    ...Object.entries(fields).map(([k, v]) => `| ${k.padEnd(17)} | ${String(v).padEnd(24)} |`),
  ].join('\n');
}

function formatDaily(data, format, limit) {
  const meta = data['Meta Data'];
  const series = data['Time Series (Daily)'];
  if (!series) throw new Error('No time series data returned. Check the ticker symbol.');

  const entries = Object.entries(series).slice(0, limit);

  if (format === 'json') {
    return JSON.stringify({ symbol: meta['2. Symbol'], data: Object.fromEntries(entries) }, null, 2);
  }

  const rows = entries.map(([date, v]) =>
    `| ${date} | ${v['1. open']} | ${v['2. high']} | ${v['3. low']} | ${v['4. close']} | ${v['5. volume']} |`
  );

  return [
    `# ${meta['2. Symbol']} — Daily Time Series (last ${entries.length} days)`,
    '',
    `| Date       | Open      | High      | Low       | Close     | Volume     |`,
    `|------------|-----------|-----------|-----------|-----------|------------|`,
    ...rows,
  ].join('\n');
}

function formatOverview(data, format) {
  if (!data['Symbol']) throw new Error('No company overview returned. Check the ticker symbol.');

  const fields = [
    'Symbol', 'Name', 'Description', 'Exchange', 'Currency', 'Country',
    'Sector', 'Industry', 'MarketCapitalization', 'EBITDA', 'PERatio',
    'PEGRatio', 'BookValue', 'DividendPerShare', 'DividendYield',
    'EPS', '52WeekHigh', '52WeekLow', 'AnalystTargetPrice',
  ];

  const subset = Object.fromEntries(fields.map(k => [k, data[k] ?? 'N/A']));

  if (format === 'json') return JSON.stringify(subset, null, 2);

  const descriptionLine = subset['Description'].length > 120
    ? subset['Description'].slice(0, 120) + '…'
    : subset['Description'];

  const tableFields = fields.filter(k => k !== 'Description');

  return [
    `# ${subset['Symbol']} — ${subset['Name']}`,
    '',
    `> ${descriptionLine}`,
    '',
    `| Field                  | Value                          |`,
    `|------------------------|--------------------------------|`,
    ...tableFields.map(k => `| ${k.padEnd(22)} | ${String(subset[k]).padEnd(30)} |`),
  ].join('\n');
}

// ── Commands ─────────────────────────────────────────────────────────────────

program
  .name('av')
  .description('Alpha Vantage CLI — query stock data from the command line')
  .version('1.0.0');

program
  .command('quote <ticker>')
  .description('Get a real-time stock quote')
  .option('-f, --format <format>', 'output format: markdown or json', 'markdown')
  .action(async (ticker, opts) => {
    try {
      const data = await fetchAV({ function: 'GLOBAL_QUOTE', symbol: ticker.toUpperCase() });
      console.log(formatQuote(data, opts.format));
    } catch (err) {
      console.error('Error:', err.message);
      process.exit(1);
    }
  });

program
  .command('daily <ticker>')
  .description('Get daily OHLCV time series')
  .option('-f, --format <format>', 'output format: markdown or json', 'markdown')
  .option('-n, --days <number>', 'number of days to show', '10')
  .action(async (ticker, opts) => {
    try {
      const data = await fetchAV({ function: 'TIME_SERIES_DAILY', symbol: ticker.toUpperCase() });
      console.log(formatDaily(data, opts.format, parseInt(opts.days, 10)));
    } catch (err) {
      console.error('Error:', err.message);
      process.exit(1);
    }
  });

program
  .command('overview <ticker>')
  .description('Get company overview and fundamentals')
  .option('-f, --format <format>', 'output format: markdown or json', 'markdown')
  .action(async (ticker, opts) => {
    try {
      const data = await fetchAV({ function: 'OVERVIEW', symbol: ticker.toUpperCase() });
      console.log(formatOverview(data, opts.format));
    } catch (err) {
      console.error('Error:', err.message);
      process.exit(1);
    }
  });

program.parse(process.argv);
