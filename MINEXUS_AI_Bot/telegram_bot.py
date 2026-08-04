#!/usr/bin/env python3
"""
telegram_bot.py - MINEXUS AI Telegram Bot
Full command interface with pair selection buttons, instant on-demand signals,
HTML photo captions, and auto Win/Loss result broadcasts.
"""

import io
import logging
import asyncio
from typing import Dict, Optional

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

from signal_engine import ALL_PAIRS, analyze_single
from chart_generator import generate_signal_chart

logger = logging.getLogger("MINEXUSBot")

BANNER = "⚡ <b>MINEXUS AI TRADING SIGNALS</b> ⚡\n━━━━━━━━━━━━━━━━━━━━━━\n"

# ── Pair selection keyboard (chunked into rows of 2) ─────────────────
def _pair_keyboard(prefix="sel_"):
    btns = []
    row = []
    for i, p in enumerate(ALL_PAIRS):
        label = p["name"] + (" 🔶" if p["type"] == "OTC" else
                             " 🪙" if p["type"] == "CRYPTO" else " 🌐")
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}{p['symbol']}"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(btns)


def _tf_keyboard(symbol: str):
    tfs = [("1 Min", "1M"), ("5 Min", "5M"), ("15 Min", "15M"), ("1 Hour", "1H")]
    btns = [[InlineKeyboardButton(lbl, callback_data=f"tf_{symbol}_{tf}")]
            for lbl, tf in tfs]
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(btns)


class MINEXUSBot:

    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start",  self._cmd_start))
        self.app.add_handler(CommandHandler("help",   self._cmd_help))
        self.app.add_handler(CommandHandler("pairs",  self._cmd_pairs))
        self.app.add_handler(CommandHandler("stats",  self._cmd_stats))
        self.app.add_handler(CommandHandler("signal", self._cmd_signal))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))

    # ── Commands ─────────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Get Signal Now", callback_data="ask_pair"),
             InlineKeyboardButton("📊 All Pairs",      callback_data="cb_pairs")],
            [InlineKeyboardButton("📈 Stats",           callback_data="cb_stats"),
             InlineKeyboardButton("❓ Help",             callback_data="cb_help")],
        ])
        text = (
            f"{BANNER}"
            "Welcome to <b>MINEXUS</b> — Real-Time AI Trading Signal Bot!\n\n"
            "🧠 <b>Engine:</b> RSI + MACD + EMA + Stochastic + Pinbar\n"
            "📸 <b>Chart:</b> Real candlestick chart with every signal\n"
            "🟢🔴 <b>Auto Result:</b> Win/Loss verified after expiry\n"
            "☁️ <b>Cloud:</b> 24/7 via GitHub Actions\n\n"
            "Tap <b>Get Signal Now</b> to choose your pair!"
        )
        await update.message.reply_html(text, reply_markup=keyboard)

    async def _cmd_signal(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_html(
            f"{BANNER}Select the pair you want a signal for:",
            reply_markup=_pair_keyboard()
        )

    async def _cmd_pairs(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        lines = []
        for p in ALL_PAIRS:
            icon = "🔶" if p["type"] == "OTC" else "🪙" if p["type"] == "CRYPTO" else "🌐"
            lines.append(f"{icon} {p['name']}")
        text = f"{BANNER}<b>All Monitored Pairs:</b>\n\n" + "\n".join(lines)
        await update.message.reply_html(text)

    async def _cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (
            f"{BANNER}<b>AI ENGINE SPECS</b>\n\n"
            "📊 Indicators Used:\n"
            "  • RSI(14) — Overbought / Oversold\n"
            "  • MACD(12,26,9) — Crossover Direction\n"
            "  • EMA 20/50 — Trend Alignment\n"
            "  • Stochastic(14) — Hook Detection\n"
            "  • Pinbar — Wick Rejection Pattern\n\n"
            "✅ Min Confidence: <b>95%</b>\n"
            "📡 Data Source: <b>Yahoo Finance (Real OHLCV)</b>\n"
            "⚡ No TradingView — No Rate Limits"
        )
        await update.message.reply_html(text)

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (
            f"{BANNER}<b>HOW TO USE MINEXUS:</b>\n\n"
            "1️⃣  Tap /signal — select your pair\n"
            "2️⃣  Select timeframe (1M / 5M / 15M / 1H)\n"
            "3️⃣  AI analyzes with real OHLCV data\n"
            "4️⃣  Receive signal + real chart image\n"
            "5️⃣  Place trade on <a href='https://qxbroker.com'>Quotex</a>\n"
            "6️⃣  MINEXUS auto-sends 🟢 WIN / 🔴 LOSS result\n\n"
            "Auto-scan runs every 60s in background too!"
        )
        await update.message.reply_html(text, disable_web_page_preview=True)

    # ── Callback Handler ─────────────────────────────────────────────────

    async def _handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q   = update.callback_query
        data = q.data
        await q.answer()

        if data == "cancel":
            await q.edit_message_text("Cancelled.")
            return

        if data in ("ask_pair", "cb_signal"):
            await q.edit_message_text(
                "📊 Select a pair for your signal:",
                reply_markup=_pair_keyboard()
            )
            return

        if data == "cb_pairs":
            await self._cmd_pairs(q, ctx)
            return
        if data == "cb_stats":
            await self._cmd_stats(q, ctx)
            return
        if data == "cb_help":
            await self._cmd_help(q, ctx)
            return

        # Pair selected → ask timeframe
        if data.startswith("sel_"):
            symbol = data[4:]
            pair   = next((p for p in ALL_PAIRS if p["symbol"] == symbol), None)
            if pair:
                await q.edit_message_text(
                    f"⏱ <b>{pair['name']}</b> selected!\n\nChoose timeframe / trade duration:",
                    parse_mode="HTML",
                    reply_markup=_tf_keyboard(symbol)
                )
            return

        # Timeframe selected → analyze and send signal
        if data.startswith("tf_"):
            parts    = data.split("_", 2)
            symbol   = parts[1]
            tf       = parts[2] if len(parts) > 2 else "5M"
            pair_obj = next((p for p in ALL_PAIRS if p["symbol"] == symbol), None)
            if not pair_obj:
                await q.edit_message_text("Pair not found.")
                return

            await q.edit_message_text(
                f"🔎 Analyzing <b>{pair_obj['name']}</b> on <b>{tf}</b>...\n"
                "Generating real chart, please wait ⏳",
                parse_mode="HTML"
            )

            # Run analysis in executor to avoid blocking
            loop = asyncio.get_event_loop()
            signal = await loop.run_in_executor(None, analyze_single, symbol, tf)

            chat_id = q.message.chat_id

            if signal:
                chart = await loop.run_in_executor(None, generate_signal_chart, signal)
                await self.send_signal(str(chat_id), signal, chart)
            else:
                # No 95%+ signal — send current market data anyway
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"{BANNER}"
                        f"📊 <b>{pair_obj['name']}</b> | TF: <b>{tf}</b>\n\n"
                        "⚠️ <b>No 95%+ confidence signal right now.</b>\n\n"
                        "Indicators are not fully aligned at this moment.\n"
                        "Try a different timeframe or wait for the next scan.\n\n"
                        "<i>Auto-scan is running every 60s — you'll be notified when a signal forms!</i>"
                    ),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Try Another Pair", callback_data="ask_pair")
                    ]])
                )
            return

    # ── Broadcast Methods ─────────────────────────────────────────────────

    async def send_startup_message(self, chat_id: str):
        text = (
            f"{BANNER}"
            "🟢 <b>MINEXUS AI Bot is Online!</b>\n\n"
            "Scanning 16 pairs every 60s for 95%+ signals.\n"
            "Use /signal to get an instant on-demand analysis!"
        )
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Startup msg error (check TELEGRAM_CHAT_ID): {e}")

    async def send_signal(self, chat_id: str, signal: Dict, chart_bytes: Optional[bytes]):
        reasons_html = "\n".join([f"  ✦ {r}" for r in signal.get("reasons", [])])
        action  = signal["action"]
        emoji   = "🚀" if action == "CALL" else "🔻"
        exp_map = {"1M": "1 Min", "5M": "5 Min", "15M": "15 Min", "1H": "1 Hour"}
        expiry  = exp_map.get(signal.get("timeframe", "5M"), "5 Min")

        caption = (
            f"⚡ <b>MINEXUS AI SIGNAL</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Asset:</b> {signal['pair_name']} [{signal['pair_type']}]\n"
            f"{emoji} <b>Action: {signal['action']}</b>\n"
            f"⏱ <b>Expiry:</b> {expiry}\n"
            f"🔥 <b>AI Confidence:</b> <b>{signal['confidence']}%</b>\n"
            f"📍 <b>Entry:</b> <code>{signal.get('entry_price', 0):.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Analysis:</b>\n{reasons_html}\n\n"
            f"<i>Place trade on Quotex now! Result tracking active...</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Open Quotex", url="https://qxbroker.com")],
            [InlineKeyboardButton("⚡ Get Another Signal", callback_data="ask_pair")]
        ])
        try:
            if chart_bytes:
                await self.app.bot.send_photo(
                    chat_id=chat_id,
                    photo=io.BytesIO(chart_bytes),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                await self.app.bot.send_message(
                    chat_id=chat_id, text=caption,
                    parse_mode="HTML", reply_markup=keyboard
                )
            logger.info(f"Signal sent: {signal['pair_name']} {action} {signal['confidence']}%")
        except Exception as e:
            logger.error(f"send_signal error: {e}")

    async def send_result(self, chat_id: str, res: Dict):
        is_win = res["is_win"]
        text = (
            f"{'🏆' if is_win else '⚠️'} <b>MINEXUS RESULT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 {res['pair_name']} | {res['action']}\n"
            f"{'🟢 WIN' if is_win else '🔴 LOSS'} ({res['badge']})\n"
            f"Entry: <code>{res['entry_price']:.5f}</code> → "
            f"Exit: <code>{res['exit_price']:.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Session: {res['total_wins']}W – {res['total_losses']}L | "
            f"Win Rate: <b>{res['win_rate']}%</b>"
        )
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"send_result error: {e}")
