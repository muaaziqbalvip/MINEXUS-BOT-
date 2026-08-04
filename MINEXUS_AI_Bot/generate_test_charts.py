"""
generate_test_charts.py - Test MINEXUS real-data chart generation for all major pairs
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from chart_generator import generate_signal_chart, fetch_real_ohlcv
import os

TEST_SIGNALS = [
    {"symbol": "EURUSD",  "pair_name": "EUR/USD",   "pair_type": "REAL",   "action": "CALL", "confidence": 96.5, "timeframe": "1M",  "entry_price": 0.0, "reasons": ["TradingView BUY", "RSI Oversold", "MACD Bullish"]},
    {"symbol": "GBPUSD",  "pair_name": "GBP/USD",   "pair_type": "REAL",   "action": "PUT",  "confidence": 97.1, "timeframe": "5M",  "entry_price": 0.0, "reasons": ["Strong Sell", "RSI Overbought 72.3", "MACD Bearish"]},
    {"symbol": "BTCUSD",  "pair_name": "BTC/USD",   "pair_type": "CRYPTO", "action": "CALL", "confidence": 95.8, "timeframe": "15M", "entry_price": 0.0, "reasons": ["Strong Buy", "EMA alignment", "Pinbar Bullish"]},
]

os.makedirs("test_charts", exist_ok=True)

for sig in TEST_SIGNALS:
    # Get real entry price first
    df = fetch_real_ohlcv(sig["symbol"], sig["timeframe"])
    if df is not None and len(df) > 0:
        c = df["Close"]
        if hasattr(c, "squeeze"):
            c = c.squeeze()
        sig["entry_price"] = float(c.iloc[-1])
        print(f"Real entry price for {sig['pair_name']}: {sig['entry_price']:.5f}")

    print(f"Generating chart: {sig['pair_name']} {sig['action']} ({sig['confidence']}%)...")
    chart = generate_signal_chart(sig)

    if chart:
        fname = f"test_charts/{sig['symbol']}_{sig['action']}.png"
        with open(fname, 'wb') as f:
            f.write(chart)
        print(f"  Saved: {fname} ({len(chart)/1024:.1f} KB)")
    else:
        print(f"  FAIL: No chart generated for {sig['pair_name']}")

print("\nAll real-data charts generated in test_charts/ folder!")
