#!/usr/bin/env python3
"""
main.py - MINEXUS AI Signal Bot — Master Entry Point
24/7 scanner using yfinance (no TradingView rate limits).
"""

import os
import sys
import time
import asyncio
import logging

from signal_engine import scan_all_markets
from result_verifier import ActiveTradeTracker
from telegram_bot import MINEXUSBot
from chart_generator import generate_signal_chart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MINEXUS] %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("minexus_bot.log", mode='a', encoding='utf-8'),
    ]
)
logger = logging.getLogger("MINEXUS")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

SCAN_INTERVAL_SEC   = 60    # Scan every 60s (no rate limit issues)
SIGNAL_COOLDOWN_SEC = 300   # 5 min cooldown per pair
TRADE_EXPIRY_SEC    = 60    # 1 min trade expiry


async def scan_and_broadcast(bot, tracker, last_signal_time, chat_id):
    try:
        # Check expired trades
        results = tracker.check_expired_trades()
        for res in results:
            if chat_id:
                await bot.send_result(chat_id, res)

        # Scan all markets
        logger.info("Scanning all pairs...")
        all_signals = scan_all_markets(timeframe="5M")

        for sig in all_signals:
            sym = sig["symbol"]
            now = time.time()
            if (now - last_signal_time.get(sym, 0)) < SIGNAL_COOLDOWN_SEC:
                continue
            last_signal_time[sym] = now

            logger.info(f"New signal: {sig['pair_name']} {sig['action']} {sig['confidence']}%")
            chart_bytes = generate_signal_chart(sig)

            if chat_id:
                await bot.send_signal(chat_id, sig, chart_bytes)

            tracker.add_trade(sig, duration_seconds=TRADE_EXPIRY_SEC)

    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)


async def main_loop(bot):
    chat_id = TELEGRAM_CHAT_ID
    tracker = ActiveTradeTracker()
    last_signal_time = {}

    logger.info("=" * 60)
    logger.info("  MINEXUS AI SIGNAL BOT - STARTED")
    logger.info(f"  Data source: Yahoo Finance (no rate limits)")
    logger.info(f"  Scan: every {SCAN_INTERVAL_SEC}s | Cooldown: {SIGNAL_COOLDOWN_SEC}s")
    logger.info("=" * 60)

    await bot.app.initialize()
    await bot.app.start()
    await bot.app.updater.start_polling(drop_pending_updates=True)

    if chat_id:
        await bot.send_startup_message(chat_id)

    while True:
        await scan_and_broadcast(bot, tracker, last_signal_time, chat_id)
        await asyncio.sleep(SCAN_INTERVAL_SEC)


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("\n" + "=" * 60)
        print("  Set TELEGRAM_BOT_TOKEN environment variable!")
        print("  Windows:  set TELEGRAM_BOT_TOKEN=your_token")
        print("  Linux:    export TELEGRAM_BOT_TOKEN=your_token")
        print("=" * 60 + "\n")
        sys.exit(1)

    bot = MINEXUSBot(TELEGRAM_BOT_TOKEN)
    try:
        asyncio.run(main_loop(bot))
    except (KeyboardInterrupt, SystemExit):
        logger.info("MINEXUS Bot stopped.")


if __name__ == "__main__":
    main()
