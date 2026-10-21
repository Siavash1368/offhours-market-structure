# data/

Gitignored. Rebuild everything with

    python -m offhours.pipeline --phase data    # downloads, cached in raw/; never re-downloads
    python -m offhours.pipeline --phase store   # Parquet tables in processed/ + DuckDB views

Set `OFFHOURS_DATA_DIR` (environment or `.env`) to keep the store elsewhere, for example a short
path on Windows where long repo paths hit the 260-character limit.

    raw/finra_ats/<tier>/<week>/<type>[_<MPID>].json.gz   FINRA weekly API responses
    raw/regsho/CNMSshvolYYYYMMDD.txt                      FINRA Reg SHO daily files
    raw/prices/<TICKER>.parquet                           Yahoo daily OHLCV (yfinance)
    raw/earnings/<TICKER>.parquet                         Yahoo earnings dates (yfinance)
    raw/symbols/                                          Nasdaq Trader symbol directories
    raw/sec/                                              SEC memo PDF and Form ATS-N filings
    processed/*.parquet, processed/offhours.duckdb        store built by store.py
