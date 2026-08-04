#!/usr/bin/env python3
"""
signal_engine.py - MINEXUS AI Signal Engine (yfinance-only, no rate limits)
Computes ALL indicators (RSI, MACD, EMA, Stochastic, Bollinger, Pinbar)
directly from real Yahoo Finance OHLCV data. No TradingView API calls = no 429 errors.
"""

import time
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, List, Optional

logger = logging.getLogger("MINEXUSSignal")

# ── All monitored pairs ──────────────────────────────────────────────────
ALL_PAIRS = [
    {"symbol": "EURUSD",     "yf": "EURUSD=X",  "name": "EUR/USD",       "type": "REAL"},
    {"symbol": "GBPUSD",     "yf": "GBPUSD=X",  "name": "GBP/USD",       "type": "REAL"},
    {"symbol": "USDJPY",     "yf": "USDJPY=X",  "name": "USD/JPY",       "type": "REAL"},
    {"symbol": "AUDUSD",     "yf": "AUDUSD=X",  "name": "AUD/USD",       "type": "REAL"},
    {"symbol": "USDCAD",     "yf": "USDCAD=X",  "name": "USD/CAD",       "type": "REAL"},
    {"symbol": "EURGBP",     "yf": "EURGBP=X",  "name": "EUR/GBP",       "type": "REAL"},
    {"symbol": "GBPJPY",     "yf": "GBPJPY=X",  "name": "GBP/JPY",       "type": "REAL"},
    {"symbol": "AUDJPY",     "yf": "AUDJPY=X",  "name": "AUD/JPY",       "type": "REAL"},
    {"symbol": "EURUSD_OTC", "yf": "EURUSD=X",  "name": "EUR/USD (OTC)", "type": "OTC"},
    {"symbol": "GBPUSD_OTC", "yf": "GBPUSD=X",  "name": "GBP/USD (OTC)", "type": "OTC"},
    {"symbol": "USDJPY_OTC", "yf": "USDJPY=X",  "name": "USD/JPY (OTC)", "type": "OTC"},
    {"symbol": "AUDUSD_OTC", "yf": "AUDUSD=X",  "name": "AUD/USD (OTC)", "type": "OTC"},
    {"symbol": "EURGBP_OTC", "yf": "EURGBP=X",  "name": "EUR/GBP (OTC)", "type": "OTC"},
    {"symbol": "GBPJPY_OTC", "yf": "GBPJPY=X",  "name": "GBP/JPY (OTC)", "type": "OTC"},
    {"symbol": "BTCUSD",     "yf": "BTC-USD",   "name": "BTC/USD",       "type": "CRYPTO"},
    {"symbol": "ETHUSD",     "yf": "ETH-USD",   "name": "ETH/USD",       "type": "CRYPTO"},
]

# Cache: avoid re-fetching same yf ticker within 60s
_ohlcv_cache: Dict[str, Dict] = {}
CACHE_TTL = 60


def _get_ohlcv(yf_ticker: str, period="2d", interval="5m") -> Optional[pd.DataFrame]:
    """Fetch OHLCV with 60-second cache to avoid hammering yfinance."""
    cache_key = f"{yf_ticker}_{interval}"
    now = time.time()
    if cache_key in _ohlcv_cache:
        entry = _ohlcv_cache[cache_key]
        if now - entry["ts"] < CACHE_TTL:
            return entry["df"]

    try:
        df = yf.download(yf_ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df is None or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open','High','Low','Close','Volume']].dropna().tail(80)
        _ohlcv_cache[cache_key] = {"df": df, "ts": now}
        return df
    except Exception as e:
        logger.warning(f"yfinance error ({yf_ticker}): {e}")
        return None


def _rsi(close: pd.Series, n=14) -> float:
    d = close.diff()
    g = d.where(d > 0, 0.0).ewm(alpha=1/n, adjust=False).mean()
    l = (-d.where(d < 0, 0.0)).ewm(alpha=1/n, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).fillna(50)
    return float(rsi.iloc[-1])


def _macd(close: pd.Series):
    ef = close.ewm(span=12, adjust=False).mean()
    es = close.ewm(span=26, adjust=False).mean()
    m  = ef - es
    s  = m.ewm(span=9, adjust=False).mean()
    return float(m.iloc[-1]), float(s.iloc[-1])


def _stoch(high, low, close, n=14):
    lo = low.rolling(n).min()
    hi = high.rolling(n).max()
    k  = 100 * (close - lo) / (hi - lo + 1e-10)
    d  = k.rolling(3).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])


def _ema(close: pd.Series, n: int) -> float:
    return float(close.ewm(span=n, adjust=False).mean().iloc[-1])


def _pinbar(o, h, l, c) -> str:
    """Detect last candle pinbar type."""
    body  = abs(c - o)
    rng   = h - l if h > l else 1e-10
    lo_wk = (min(o, c) - l) / rng
    hi_wk = (h - max(o, c)) / rng
    if lo_wk > 0.55 and c >= o:
        return "BULL"
    if hi_wk > 0.55 and c <= o:
        return "BEAR"
    return "NONE"


def analyze_pair(pair: Dict, timeframe: str = "5M") -> Optional[Dict]:
    """
    Full indicator analysis from real yfinance OHLCV.
    Returns signal dict if confidence >= 95%, else None.
    """
    interval_map = {"1M": "5m", "5M": "15m", "15M": "30m", "1H": "1h"}
    period_map   = {"1M": "2d", "5M": "5d",  "15M": "10d",  "1H": "20d"}
    iv = interval_map.get(timeframe, "5m")
    pd_ = period_map.get(timeframe, "2d")

    df = _get_ohlcv(pair["yf"], period=pd_, interval=iv)
    if df is None or len(df) < 30:
        return None

    close = df["Close"].astype(float)
    high  = df["High"].astype(float)
    low   = df["Low"].astype(float)
    open_ = df["Open"].astype(float)

    # Compute REAL indicators
    rsi          = _rsi(close)
    macd, sig    = _macd(close)
    stoch_k, stoch_d = _stoch(high, low, close)
    ema20        = _ema(close, 20)
    ema50        = _ema(close, 50)
    price        = float(close.iloc[-1])
    pin          = _pinbar(float(open_.iloc[-1]), float(high.iloc[-1]),
                           float(low.iloc[-1]),  float(close.iloc[-1]))

    score_up, score_dn = 0.0, 0.0
    reasons_up, reasons_dn = [], []

    # ── 1. RSI (25 pts) ─────────────────────────────────────────────
    if rsi <= 28:
        score_up += 25; reasons_up.append(f"RSI Oversold ({rsi:.1f})")
    elif rsi <= 38:
        score_up += 14

    if rsi >= 72:
        score_dn += 25; reasons_dn.append(f"RSI Overbought ({rsi:.1f})")
    elif rsi >= 62:
        score_dn += 14

    # ── 2. MACD crossover (20 pts) ───────────────────────────────────
    if macd > sig and macd > 0:
        score_up += 20; reasons_up.append("MACD Bullish (above zero)")
    elif macd > sig:
        score_up += 10

    if macd < sig and macd < 0:
        score_dn += 20; reasons_dn.append("MACD Bearish (below zero)")
    elif macd < sig:
        score_dn += 10

    # ── 3. EMA trend alignment (20 pts) ─────────────────────────────
    if price > ema20 > ema50:
        score_up += 20; reasons_up.append("Price > EMA20 > EMA50 (Uptrend)")
    elif price > ema20:
        score_up += 10

    if price < ema20 < ema50:
        score_dn += 20; reasons_dn.append("Price < EMA20 < EMA50 (Downtrend)")
    elif price < ema20:
        score_dn += 10

    # ── 4. Stochastic hook (15 pts) ──────────────────────────────────
    if stoch_k < 22 and stoch_k > stoch_d:
        score_up += 15; reasons_up.append(f"Stochastic Oversold Hook ({stoch_k:.1f})")
    if stoch_k > 78 and stoch_k < stoch_d:
        score_dn += 15; reasons_dn.append(f"Stochastic Overbought Hook ({stoch_k:.1f})")

    # ── 5. Pinbar pattern (20 pts) ───────────────────────────────────
    if pin == "BULL":
        score_up += 20; reasons_up.append("Bullish Pinbar / Wick Rejection")
    if pin == "BEAR":
        score_dn += 20; reasons_dn.append("Bearish Shooting Star / Wick Rejection")

    # ── Determine direction ──────────────────────────────────────────
    if score_up > score_dn:
        action, conf, reasons = "CALL", min(98.5, score_up), reasons_up
        dir_emoji = "🚀 CALL (BUY)"
    else:
        action, conf, reasons = "PUT",  min(98.5, score_dn), reasons_dn
        dir_emoji = "🔻 PUT (SELL)"

    if conf < 95.0 or not reasons:
        return None

    return {
        "pair_name":    pair["name"],
        "symbol":       pair["symbol"],
        "pair_type":    pair["type"],
        "action":       action,
        "direction_emoji": dir_emoji,
        "confidence":   round(conf, 1),
        "timeframe":    timeframe,
        "entry_price":  price,
        "reasons":      reasons,
        "rsi":          round(rsi, 1),
        "timestamp":    time.time(),
    }


def scan_all_markets(timeframe: str = "5M") -> List[Dict]:
    """Scan all pairs. Returns list of 95%+ confidence signals."""
    signals = []
    for pair in ALL_PAIRS:
        try:
            sig = analyze_pair(pair, timeframe)
            if sig:
                signals.append(sig)
                logger.info(f"SIGNAL: {sig['pair_name']} {sig['action']} {sig['confidence']}%")
        except Exception as e:
            logger.warning(f"Error analyzing {pair['name']}: {e}")
    return signals


def analyze_single(symbol: str, timeframe: str = "5M") -> Optional[Dict]:
    """Analyze a single pair by symbol name. Used for on-demand /signal command."""
    pair = next((p for p in ALL_PAIRS if p["symbol"] == symbol), None)
    if not pair:
        return None
    # Force fresh data for on-demand requests — extract interval before f-string
    iv_map    = {"1M": "5m", "5M": "15m", "15M": "30m", "1H": "1h"}
    iv        = iv_map.get(timeframe, "5m")
    cache_key = f"{pair['yf']}_{iv}"
    _ohlcv_cache.pop(cache_key, None)
    return analyze_pair(pair, timeframe)
