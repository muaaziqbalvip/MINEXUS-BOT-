#!/usr/bin/env python3
"""
main.py - MINEXUS AI Telegram Trading Signal Bot — Master Entry Point
24/7 multi-pair scanner with live chart image generation, 95%+ confluence signals,
auto Win/Loss tracking, and Telegram broadcast.
"""

import os
import sys
import time
import asyncio
import logging
from datetime import datetime

from signal_engine import SignalEngine
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
SCAN_INTERVAL_SEC  = 20        # Scan every 20 seconds
SIGNAL_COOLDOWN_SEC = 120      # Min 2 min between same-pair signals
TRADE_EXPIRY_SEC    = 60       # Default 1 min trade expiry


async def scan_and_broadcast(bot: MINEXUSBot, tracker: ActiveTradeTracker,
                              last_signal_time: dict, chat_id: str):
    """Single scan cycle: fetch signals, generate charts, broadcast, track results."""
    try:
        # 1. Check expired trades → broadcast Win/Loss results
        results = tracker.check_expired_trades()
        for res in results:
            await bot.send_result(chat_id, res)

        # 2. Scan all pairs for 95%+ signals
        all_signals = SignalEngine.scan_all_markets(timeframe="1M")

        for sig in all_signals:
            sym = sig["symbol"]
            now = time.time()

            # Cooldown guard
            if (now - last_signal_time.get(sym, 0)) < SIGNAL_COOLDOWN_SEC:
                continue
            last_signal_time[sym] = now

            # Generate chart image
            logger.info(f"Generating chart for {sig['pair_name']} {sig['action']} ({sig['confidence']}%)")
            chart_bytes = generate_signal_chart(sig)

            # Send signal photo + caption to Telegram
            await bot.send_signal(chat_id, sig, chart_bytes)

            # Track for result verification
            tracker.add_trade(sig, duration_seconds=TRADE_EXPIRY_SEC)

    except Exception as e:
        logger.error(f"Scan cycle error: {e}", exc_info=True)


async def main_loop(bot: MINEXUSBot):
    """Main 24/7 scanner loop."""
    chat_id = TELEGRAM_CHAT_ID
    tracker = ActiveTradeTracker()
    last_signal_time = {}

    logger.info("=" * 60)
    logger.info("  ⚡ MINEXUS AI SIGNAL BOT — STARTED")
    logger.info(f"  Scan interval: {SCAN_INTERVAL_SEC}s | Cooldown: {SIGNAL_COOLDOWN_SEC}s")
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
        print("\n" + "="*65)
        print("  ⚠️  Set TELEGRAM_BOT_TOKEN environment variable first!")
        print("  Example:")
        print("    Windows:  set TELEGRAM_BOT_TOKEN=your_token_here")
        print("    Linux:    export TELEGRAM_BOT_TOKEN=your_token_here")
        print("="*65 + "\n")
        sys.exit(1)

    bot = MINEXUSBot(TELEGRAM_BOT_TOKEN)
    try:
        asyncio.run(main_loop(bot))
    except (KeyboardInterrupt, SystemExit):
        logger.info("MINEXUS Bot stopped.")


if __name__ == "__main__":
    main()
