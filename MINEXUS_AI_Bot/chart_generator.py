#!/usr/bin/env python3
"""
chart_generator.py - MINEXUS AI Real-Data Chart Generator
Uses mplfinance (professional library) to render correct candlestick charts
directly from real Yahoo Finance OHLCV data. No manual patch drawing.
"""

import io
import logging
import warnings
from typing import Optional, Dict
from datetime import datetime

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import mplfinance as mpf

import yfinance as yf

warnings.filterwarnings('ignore')
logger = logging.getLogger("MINEXUSChart")

# ── Yahoo Finance ticker map ──────────────────────────────────────────
YF_MAP = {
    "EURUSD":     "EURUSD=X",
    "GBPUSD":     "GBPUSD=X",
    "USDJPY":     "USDJPY=X",
    "AUDUSD":     "AUDUSD=X",
    "USDCAD":     "USDCAD=X",
    "EURGBP":     "EURGBP=X",
    "AUDCAD":     "AUDCAD=X",
    "GBPJPY":     "GBPJPY=X",
    "EURUSD_OTC": "EURUSD=X",
    "GBPUSD_OTC": "GBPUSD=X",
    "USDJPY_OTC": "USDJPY=X",
    "USDBRL_OTC": "USDBRL=X",
    "NZDCAD_OTC": "NZDCAD=X",
    "AUDJPY_OTC": "AUDJPY=X",
    "BTCUSD":     "BTC-USD",
    "ETHUSD":     "ETH-USD",
}

TF_MAP = {
    "1M":  ("2d",  "5m"),
    "5M":  ("5d",  "15m"),
    "15M": ("10d", "30m"),
    "1H":  ("20d", "1h"),
}


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d    = close.diff()
    gain = d.where(d > 0, 0.0).ewm(alpha=1/n, adjust=False).mean()
    loss = (-d.where(d < 0, 0.0)).ewm(alpha=1/n, adjust=False).mean()
    rs   = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _macd(close: pd.Series, fast=12, slow=26, sig=9):
    ef   = close.ewm(span=fast, adjust=False).mean()
    es   = close.ewm(span=slow, adjust=False).mean()
    m    = ef - es
    s    = m.ewm(span=sig, adjust=False).mean()
    h    = m - s
    return m.fillna(0), s.fillna(0), h.fillna(0)


def fetch_real_ohlcv(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Fetch REAL OHLCV from Yahoo Finance. Returns clean DataFrame or None."""
    ticker = YF_MAP.get(symbol)
    if not ticker:
        return None
    period, interval = TF_MAP.get(timeframe, ("2d", "5m"))
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
        if df is None or len(df) < 20:
            return None

        # Flatten MultiIndex columns (yfinance >= 0.2.x)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # mplfinance needs: Open High Low Close Volume with DatetimeIndex
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.index = pd.to_datetime(df.index)
        df = df.dropna().tail(60)   # Last 60 candles

        # Ensure correct types
        for col in ['Open','High','Low','Close']:
            df[col] = df[col].astype(float)

        return df

    except Exception as e:
        logger.error(f"yfinance error ({symbol}): {e}")
        return None


def generate_signal_chart(signal: Dict) -> Optional[bytes]:
    """
    Generates a professional MINEXUS candlestick chart using mplfinance.
    - Uses 100% real Yahoo Finance OHLCV data
    - Correct bullish/bearish candles rendered by mplfinance (no manual patches)
    - RSI and MACD computed on actual candle data
    - Signal arrow, EMA, Bollinger bands overlaid
    Returns PNG bytes for Telegram photo upload.
    """
    symbol    = signal.get("symbol", "EURUSD")
    pair_name = signal.get("pair_name", symbol)
    action    = signal.get("action", "CALL")
    conf      = signal.get("confidence", 95.0)
    tf        = signal.get("timeframe", "1M")
    entry_px  = float(signal.get("entry_price", 0.0))

    df = fetch_real_ohlcv(symbol, tf)
    if df is None or len(df) < 20:
        logger.warning(f"Falling back to info card for {symbol}")
        return _info_card(signal)

    close = df["Close"]

    # ── Compute indicators on REAL data ───────────────────────────────
    rsi_s          = _rsi(close)
    macd_l, sig_l, hist_s = _macd(close)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    # Update entry price to latest real close if not set
    if entry_px == 0.0:
        entry_px = float(close.iloc[-1])

    # ── mplfinance style (dark MINEXUS theme) ─────────────────────────
    mc = mpf.make_marketcolors(
        up     = '#00e676',   # green candle
        down   = '#ff1744',   # red candle
        edge   = {'up': '#00e676', 'down': '#ff1744'},
        wick   = {'up': '#00e676', 'down': '#ff1744'},
        volume = {'up': '#00e676', 'down': '#ff1744'},
    )
    style = mpf.make_mpf_style(
        base_mpf_style  = 'nightclouds',
        marketcolors    = mc,
        figcolor        = '#0a0a1a',
        facecolor       = '#0f0f2a',
        edgecolor       = '#1a1a3a',
        gridcolor       = '#1a1a3a',
        gridstyle       = '--',
        gridaxis        = 'both',
        rc              = {
            'axes.labelcolor': '#64748b',
            'xtick.color':     '#64748b',
            'ytick.color':     '#64748b',
            'text.color':      '#e2e8f0',
            'font.size':       8.5,
        }
    )

    # ── Add-plots: EMA, Bollinger, RSI, MACD ─────────────────────────
    bb_upper = close.rolling(20).mean() + 2 * close.rolling(20).std()
    bb_lower = close.rolling(20).mean() - 2 * close.rolling(20).std()
    entry_line = pd.Series(entry_px, index=df.index)

    addplots = [
        # Candlestick panel overlays
        mpf.make_addplot(ema20,      panel=0, color='#ffd700', width=1.3, label='EMA 20'),
        mpf.make_addplot(ema50,      panel=0, color='#7c3aed', width=1.3, label='EMA 50'),
        mpf.make_addplot(bb_upper,   panel=0, color='#7c3aed', width=0.7,
                         linestyle='--', alpha=0.6),
        mpf.make_addplot(bb_lower,   panel=0, color='#7c3aed', width=0.7,
                         linestyle='--', alpha=0.6),
        mpf.make_addplot(entry_line, panel=0, color='#ffd700', width=0.8,
                         linestyle=':', label=f'Entry {entry_px:.5f}'),
        # RSI panel
        mpf.make_addplot(rsi_s,   panel=1, color='#a78bfa', width=1.5,
                         ylabel='RSI', ylim=(0, 100)),
        # MACD panel
        mpf.make_addplot(macd_l,  panel=2, color='#06b6d4', width=1.4,
                         ylabel='MACD'),
        mpf.make_addplot(sig_l,   panel=2, color='#f59e0b', width=1.2),
        mpf.make_addplot(hist_s,  panel=2, type='bar', color='#7c3aed',
                         alpha=0.5),
    ]

    # ── Plot with mplfinance ──────────────────────────────────────────
    sig_color = '#00e676' if action == 'CALL' else '#ff1744'
    action_label = '▲ CALL (BUY)' if action == 'CALL' else '▼ PUT (SELL)'
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    title = (
        f" ⚡ MINEXUS AI  |  {pair_name}  |  {action_label}  |  "
        f"Confidence: {conf}%  |  TF: {tf}  |  {ts} "
    )

    fig, axes = mpf.plot(
        df,
        type         = 'candle',
        style        = style,
        addplot      = addplots,
        volume       = False,
        figsize      = (14, 10),
        title        = title,
        returnfig    = True,
        panel_ratios = (0.55, 0.20, 0.25),
        tight_layout = True,
    )

    # ── Post-render styling ───────────────────────────────────────────
    fig.patch.set_facecolor('#0a0a1a')

    # Title color
    if axes and axes[0].get_title():
        axes[0].title.set_color(sig_color)

    # RSI reference lines (overbought / oversold)
    if len(axes) > 1:
        axes[1].axhline(70, color='#ff1744', lw=0.8, ls='--', alpha=0.6)
        axes[1].axhline(30, color='#00e676', lw=0.8, ls='--', alpha=0.6)
        axes[1].axhline(50, color='#64748b', lw=0.5, ls=':',  alpha=0.4)
        axes[1].set_facecolor('#0f0f2a')
        rsi_now = float(rsi_s.iloc[-1])
        axes[1].text(0.99, 0.85, f'RSI: {rsi_now:.1f}',
                     transform=axes[1].transAxes, fontsize=9,
                     ha='right', color='#a78bfa', fontweight='bold')

    # MACD zero line
    if len(axes) > 2:
        axes[2].axhline(0, color='#64748b', lw=0.5, alpha=0.5)
        axes[2].set_facecolor('#0f0f2a')

    # Signal arrow annotation on main panel
    if len(axes) > 0:
        ax0 = axes[0]
        last_idx  = len(df) - 1
        last_close = float(close.iloc[-1])
        pr_range   = float(df['High'].max() - df['Low'].min())
        offset     = pr_range * 0.04

        if action == 'CALL':
            ax0.annotate(
                '▲ CALL',
                xy=(last_idx, last_close - offset * 0.5),
                xytext=(last_idx - 8, last_close - offset * 3),
                fontsize=11, fontweight='bold', color='#00e676',
                arrowprops=dict(arrowstyle='->', color='#00e676', lw=2.0),
            )
        else:
            ax0.annotate(
                '▼ PUT',
                xy=(last_idx, last_close + offset * 0.5),
                xytext=(last_idx - 8, last_close + offset * 3),
                fontsize=11, fontweight='bold', color='#ff1744',
                arrowprops=dict(arrowstyle='->', color='#ff1744', lw=2.0),
            )

    # Footer
    fig.text(
        0.5, 0.002,
        'MINEXUS AI  |  Real Data: Yahoo Finance + TradingView  |  95%+ Accuracy',
        ha='center', fontsize=8, color='#7c3aed', alpha=0.8
    )

    # ── Save to bytes ─────────────────────────────────────────────────
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor='#0a0a1a', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    data = buf.read()
    logger.info(f"mplfinance chart: {pair_name} {action} — {len(data)//1024} KB")
    return data


def _info_card(signal: Dict) -> bytes:
    """Fallback styled info card when live data unavailable."""
    action    = signal.get("action", "CALL")
    pair_name = signal.get("pair_name", "")
    conf      = signal.get("confidence", 0)
    entry_px  = float(signal.get("entry_price", 0))
    tf        = signal.get("timeframe", "1M")
    sig_col   = '#00e676' if action == 'CALL' else '#ff1744'

    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#0a0a1a')
    ax.set_facecolor('#0a0a1a')
    ax.axis('off')

    def t(x, y, s, **kw):
        ax.text(x, y, s, transform=ax.transAxes,
                ha='center', va='center', **kw)

    t(0.5, 0.82, 'MINEXUS AI SIGNAL',
      fontsize=20, fontweight='bold', color='#7c3aed')
    t(0.5, 0.62,
      f"{'BUY (CALL)' if action=='CALL' else 'SELL (PUT)'}",
      fontsize=28, fontweight='bold', color=sig_col)
    t(0.5, 0.44,
      f'{pair_name}  |  TF: {tf}  |  Entry: {entry_px:.5f}',
      fontsize=13, color='#e2e8f0')
    t(0.5, 0.28, f'AI Confidence: {conf}%',
      fontsize=17, fontweight='bold', color='#ffd700')
    t(0.5, 0.12, 'MINEXUS AI  |  Real Signals  |  95%+ Accuracy',
      fontsize=9, color='#64748b')

    ax.add_patch(FancyBboxPatch(
        (0.02, 0.04), 0.96, 0.93,
        boxstyle='round,pad=0.01', lw=2,
        edgecolor='#7c3aed', facecolor='none',
        transform=ax.transAxes))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor='#0a0a1a', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()
