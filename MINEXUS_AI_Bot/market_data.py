#!/usr/bin/env python3
"""
market_data.py - Real-Time Market Data Streamer & TradingView Fetcher
Fetches live quote data, OHLC candles, and technical analysis indicators
for Quotex Real & OTC pairs from TradingView and secondary live market feeds.
"""

import time
import logging
import requests
from typing import Dict, List, Optional
from tradingview_ta import TA_Handler, Interval, Exchange

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Supported Quotex & Global Market Asset Pairs (Real & OTC)
ALL_PAIRS = [
    # Major Forex Pairs
    {"symbol": "EURUSD", "tv_symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC", "name": "EUR/USD", "type": "REAL"},
    {"symbol": "GBPUSD", "tv_symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC", "name": "GBP/USD", "type": "REAL"},
    {"symbol": "USDJPY", "tv_symbol": "USDJPY", "screener": "forex", "exchange": "FX_IDC", "name": "USD/JPY", "type": "REAL"},
    {"symbol": "AUDUSD", "tv_symbol": "AUDUSD", "screener": "forex", "exchange": "FX_IDC", "name": "AUD/USD", "type": "REAL"},
    {"symbol": "USDCAD", "tv_symbol": "USDCAD", "screener": "forex", "exchange": "FX_IDC", "name": "USD/CAD", "type": "REAL"},
    {"symbol": "EURGBP", "tv_symbol": "EURGBP", "screener": "forex", "exchange": "FX_IDC", "name": "EUR/GBP", "type": "REAL"},
    {"symbol": "AUDCAD", "tv_symbol": "AUDCAD", "screener": "forex", "exchange": "FX_IDC", "name": "AUD/CAD", "type": "REAL"},
    {"symbol": "GBPJPY", "tv_symbol": "GBPJPY", "screener": "forex", "exchange": "FX_IDC", "name": "GBP/JPY", "type": "REAL"},
    
    # Quotex Popular OTC Pairs (Synthesized & Live Forex Feed Aligned)
    {"symbol": "EURUSD_OTC", "tv_symbol": "EURUSD", "screener": "forex", "exchange": "FX_IDC", "name": "EUR/USD (OTC)", "type": "OTC"},
    {"symbol": "GBPUSD_OTC", "tv_symbol": "GBPUSD", "screener": "forex", "exchange": "FX_IDC", "name": "GBP/USD (OTC)", "type": "OTC"},
    {"symbol": "USDJPY_OTC", "tv_symbol": "USDJPY", "screener": "forex", "exchange": "FX_IDC", "name": "USD/JPY (OTC)", "type": "OTC"},
    {"symbol": "USDBRL_OTC", "tv_symbol": "USDBRL", "screener": "forex", "exchange": "FX_IDC", "name": "USD/BRL (OTC)", "type": "OTC"},
    {"symbol": "NZDCAD_OTC", "tv_symbol": "NZDCAD", "screener": "forex", "exchange": "FX_IDC", "name": "NZD/CAD (OTC)", "type": "OTC"},
    {"symbol": "AUDJPY_OTC", "tv_symbol": "AUDJPY", "screener": "forex", "exchange": "FX_IDC", "name": "AUD/JPY (OTC)", "type": "OTC"},

    # Crypto Pairs
    {"symbol": "BTCUSD", "tv_symbol": "BTCUSDT", "screener": "crypto", "exchange": "BINANCE", "name": "BTC/USDT", "type": "CRYPTO"},
    {"symbol": "ETHUSD", "tv_symbol": "ETHUSDT", "screener": "crypto", "exchange": "BINANCE", "name": "ETH/USDT", "type": "CRYPTO"},
]

# Timeframe Mappings
TIMEFRAME_MAP = {
    "1M": Interval.INTERVAL_1_MINUTE,
    "5M": Interval.INTERVAL_5_MINUTES,
    "15M": Interval.INTERVAL_15_MINUTES,
    "1H": Interval.INTERVAL_1_HOUR,
}


class MarketDataProvider:
    """Provides technical analysis metrics & price data for Quotex pairs."""

    @staticmethod
    def get_tradingview_analysis(pair_info: Dict, timeframe_str: str = "1M") -> Optional[Dict]:
        """
        Fetches technical indicators, oscillator ratings, and summary from TradingView.
        """
        interval = TIMEFRAME_MAP.get(timeframe_str, Interval.INTERVAL_1_MINUTE)
        try:
            handler = TA_Handler(
                symbol=pair_info["tv_symbol"],
                screener=pair_info["screener"],
                exchange=pair_info["exchange"],
                interval=interval,
                timeout=8
            )
            analysis = handler.get_analysis()
            
            return {
                "recommendation": analysis.summary.get("RECOMMENDATION", "NEUTRAL"),
                "buy_count": analysis.summary.get("BUY", 0),
                "sell_count": analysis.summary.get("SELL", 0),
                "neutral_count": analysis.summary.get("NEUTRAL", 0),
                "indicators": analysis.indicators,
                "oscillators_rec": analysis.oscillators.get("RECOMMENDATION", "NEUTRAL"),
                "moving_averages_rec": analysis.moving_averages.get("RECOMMENDATION", "NEUTRAL"),
                "price": analysis.indicators.get("close", 0.0),
                "high": analysis.indicators.get("high", 0.0),
                "low": analysis.indicators.get("low", 0.0),
                "open": analysis.indicators.get("open", 0.0),
                "rsi": analysis.indicators.get("RSI", 50.0),
                "macd": analysis.indicators.get("MACD.macd", 0.0),
                "macd_signal": analysis.indicators.get("MACD.signal", 0.0),
                "ema20": analysis.indicators.get("EMA20", 0.0),
                "ema50": analysis.indicators.get("EMA50", 0.0),
                "ema200": analysis.indicators.get("EMA200", 0.0),
                "stoch_k": analysis.indicators.get("Stoch.K", 50.0),
                "stoch_d": analysis.indicators.get("Stoch.D", 50.0),
                "bb_upper": analysis.indicators.get("BB.upper", 0.0),
                "bb_lower": analysis.indicators.get("BB.lower", 0.0),
            }
        except Exception as e:
            logging.warning(f"TradingView TA fetch error for {pair_info['name']} ({timeframe_str}): {e}")
            return None

    @staticmethod
    def fetch_live_price(pair_info: Dict) -> float:
        """
        Fetches current live price using fallback REST API if TradingView stream is delayed.
        """
        try:
            if pair_info["screener"] == "crypto":
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair_info['tv_symbol']}"
                res = requests.get(url, timeout=5).json()
                return float(res.get("price", 0.0))
            else:
                # Forex fallbacks
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{pair_info['tv_symbol']}=X"
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(url, headers=headers, timeout=5).json()
                price = res["chart"]["result"][0]["meta"]["regularMarketPrice"]
                return float(price)
        except Exception:
            # Fallback to TradingView TA price
            ta = MarketDataProvider.get_tradingview_analysis(pair_info, "1M")
            return ta.get("price", 0.0) if ta else 0.0
