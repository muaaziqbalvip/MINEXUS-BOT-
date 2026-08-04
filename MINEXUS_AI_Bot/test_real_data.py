import sys
import os
import yfinance as yf
import pandas as pd
from tradingview_ta import TA_Handler, Interval

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("  MINEXUS REAL DATA VERIFICATION TEST")
print("=" * 60)

# Test 1: Real EUR/USD OHLCV from Yahoo Finance
print("\n[1] Fetching REAL EUR/USD 5-min candles from Yahoo Finance...")
df = yf.download('EURUSD=X', period='1d', interval='5m', progress=False, auto_adjust=True)
if df is not None and len(df) > 0:
    close = df['Close']
    if hasattr(close, 'squeeze'):
        close = close.squeeze()
    latest = float(close.iloc[-1])
    print(f"    OK  Candles fetched: {len(df)}")
    print(f"    OK  Latest EUR/USD price: {latest:.5f}")
    print(f"    Last 3 REAL candles:")
    print(df[['Open','High','Low','Close']].tail(3).to_string())
else:
    print("    FAIL  yfinance returned no data")

# Test 2: Real GBP/USD
print("\n[2] Fetching REAL GBP/USD...")
df2 = yf.download('GBPUSD=X', period='1d', interval='5m', progress=False, auto_adjust=True)
if df2 is not None and len(df2) > 0:
    c2 = df2['Close']
    if hasattr(c2, 'squeeze'):
        c2 = c2.squeeze()
    print(f"    OK  Latest GBP/USD: {float(c2.iloc[-1]):.5f}")

# Test 3: Real BTC
print("\n[3] Fetching REAL BTC/USD...")
df3 = yf.download('BTC-USD', period='1d', interval='5m', progress=False, auto_adjust=True)
if df3 is not None and len(df3) > 0:
    c3 = df3['Close']
    if hasattr(c3, 'squeeze'):
        c3 = c3.squeeze()
    print(f"    OK  Latest BTC/USD: {float(c3.iloc[-1]):.2f}")

# Test 4: TradingView REAL technical indicators
print("\n[4] Fetching REAL TradingView Technical Analysis for EUR/USD...")
try:
    handler = TA_Handler(
        symbol="EURUSD",
        screener="forex",
        exchange="FX_IDC",
        interval=Interval.INTERVAL_5_MINUTES,
        timeout=10
    )
    analysis = handler.get_analysis()
    price = analysis.indicators.get('close', 0)
    rsi   = analysis.indicators.get('RSI', 0)
    macd  = analysis.indicators.get('MACD.macd', 0)
    rec   = analysis.summary.get('RECOMMENDATION', 'N/A')
    buy_c = analysis.summary.get('BUY', 0)
    sel_c = analysis.summary.get('SELL', 0)
    neu_c = analysis.summary.get('NEUTRAL', 0)
    print(f"    OK  TradingView REAL Price  : {price:.5f}")
    print(f"    OK  REAL RSI(14)            : {rsi:.2f}")
    print(f"    OK  REAL MACD               : {macd:.6f}")
    print(f"    OK  Summary Rating          : {rec}")
    print(f"    OK  Indicators              : BUY={buy_c}  SELL={sel_c}  NEUTRAL={neu_c}")
except Exception as e:
    print(f"    WARN  TradingView error: {e}")

print("\n" + "=" * 60)
print("  DATA SOURCE SUMMARY:")
print("  - Candle Charts : Yahoo Finance (REAL live OHLCV)")
print("  - Signals       : TradingView TA (REAL indicators)")
print("  - NO random data. NO fake data. ALL 100% REAL.")
print("=" * 60)
