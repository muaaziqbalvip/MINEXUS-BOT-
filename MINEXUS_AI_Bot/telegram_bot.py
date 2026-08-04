#!/usr/bin/env python3
"""
telegram_bot.py - MINEXUS AI Telegram Bot Interface
Handles all Telegram messaging: signal photos, result updates, commands, and menus.
"""

import logging
from typing import Dict, Optional
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
import io

logger = logging.getLogger("MINEXUSBot")

BANNER = (
    "⚡ <b>MINEXUS AI TRADING SIGNALS</b> ⚡\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
)


class MINEXUSBot:
    """MINEXUS Telegram Bot — Signal Sender & Command Manager."""

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

    # ── Command Handlers ──────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("⚡ Get Signal", callback_data="cb_signal"),
             InlineKeyboardButton("📊 Pairs",      callback_data="cb_pairs")],
            [InlineKeyboardButton("📈 Stats",       callback_data="cb_stats"),
             InlineKeyboardButton("❓ Help",         callback_data="cb_help")],
        ]
        text = (
            f"{BANNER}"
            "Welcome to <b>MINEXUS</b> — the world's most advanced binary trading "
            "signal analyzer bot.\n\n"
            "🧠 <b>AI Engine:</b> 95%+ Confluence Filter\n"
            "📸 <b>Chart Images:</b> Live candlestick charts with every signal\n"
            "🟢🔴 <b>Auto Result:</b> Win/Loss verification after expiry\n"
            "☁️ <b>Uptime:</b> 24/7 via GitHub Actions\n\n"
            "Use <code>/signal</code> for instant scan or wait for auto-alerts!"
        )
        await update.message.reply_html(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (
            f"{BANNER}"
            "<b>HOW TO USE MINEXUS:</b>\n\n"
            "1️⃣  Receive a signal with chart image.\n"
            "2️⃣  Note: Asset • Direction (CALL/PUT) • Expiry time.\n"
            "3️⃣  Open <a href='https://qxbroker.com'>Quotex</a> and place trade immediately.\n"
            "4️⃣  MINEXUS auto-checks result and sends 🟢 WIN / 🔴 LOSS after expiry.\n\n"
            "<b>Commands:</b>\n"
            "/signal — Instant signal scan (all pairs)\n"
            "/pairs  — View monitored assets\n"
            "/stats  — Session win/loss stats\n"
            "/help   — This guide"
        )
        await update.message.reply_html(text, disable_web_page_preview=True)

    async def _cmd_pairs(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (
            f"{BANNER}"
            "<b>📊 MONITORED ASSET PAIRS</b>\n\n"
            "<b>Forex (Real Market):</b>\n"
            "  EUR/USD • GBP/USD • USD/JPY\n"
            "  AUD/USD • USD/CAD • EUR/GBP\n"
            "  AUD/CAD • GBP/JPY\n\n"
            "<b>OTC (Quotex Synthetic):</b>\n"
            "  EUR/USD OTC • GBP/USD OTC\n"
            "  USD/JPY OTC • USD/BRL OTC\n"
            "  NZD/CAD OTC • AUD/JPY OTC\n\n"
            "<b>Crypto:</b>\n"
            "  BTC/USDT • ETH/USDT\n\n"
            "<i>Timeframes: 1M · 5M · 15M | Scanned every 20s</i>"
        )
        await update.message.reply_html(text)

    async def _cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = (
            f"{BANNER}"
            "<b>📈 MINEXUS ENGINE SPECS</b>\n\n"
            "🔬 Indicators Analyzed Per Signal:\n"
            "  • TradingView Summary Rating\n"
            "  • RSI (14) Overbought/Oversold\n"
            "  • MACD Crossover Direction\n"
            "  • EMA 20 / EMA 50 Alignment\n"
            "  • Stochastic Oscillator Hook\n"
            "  • Pinbar / Wick Rejection Pattern\n\n"
            "✅ Min Confidence Threshold: <b>95.0%</b>\n"
            "☁️ Uptime: <b>24/7 GitHub Actions</b>\n"
            "📸 Chart Type: <b>Live Candlestick + RSI + MACD</b>"
        )
        await update.message.reply_html(text)

    async def _cmd_signal(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_html(
            f"{BANNER}"
            "🔎 Scanning all 16 asset pairs for 95%+ confidence signals...\n"
            "<i>Chart image will be sent if a qualifying signal is found!</i>"
        )

    async def _handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        if q.data == "cb_signal":
            await self._cmd_signal(q, ctx)
        elif q.data == "cb_pairs":
            await self._cmd_pairs(q, ctx)
        elif q.data == "cb_stats":
            await self._cmd_stats(q, ctx)
        elif q.data == "cb_help":
            await self._cmd_help(q, ctx)

    # ── Broadcast Methods ─────────────────────────────────────────────────

    async def send_startup_message(self, chat_id: str):
        text = (
            f"{BANNER}"
            "🟢 <b>MINEXUS AI Bot Online!</b>\n"
            "Scanning 16 asset pairs every 20 seconds.\n"
            "95%+ Confidence signals with live chart images incoming!"
        )
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Startup message error: {e}")

    async def send_signal(self, chat_id: str, signal: Dict, chart_bytes: Optional[bytes]):
        """Send signal as a photo with HTML caption."""
        reasons_html = "\n".join([f"  ✦ {r}" for r in signal.get("reasons", [])])
        action  = signal["action"]
        emoji   = "🚀" if action == "CALL" else "🔻"
        sig_dir = "CALL (BUY)" if action == "CALL" else "PUT (SELL)"

        caption = (
            f"⚡ <b>MINEXUS AI SIGNAL</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Asset:</b> {signal['pair_name']} [{signal['pair_type']}]\n"
            f"{emoji} <b>Action:</b> <b>{sig_dir}</b>\n"
            f"⏱ <b>Timeframe:</b> {signal.get('timeframe','1M')} · Expiry: 1 Min\n"
            f"🔥 <b>AI Confidence:</b> <b>{signal['confidence']}%</b>\n"
            f"📍 <b>Entry:</b> <code>{signal.get('entry_price', 0):.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Confluence Reasons:</b>\n{reasons_html}\n\n"
            f"<i>⚡ MINEXUS · Place trade now on Quotex!</i>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Open Quotex", url="https://qxbroker.com")],
            [InlineKeyboardButton("⚡ Result Tracking Active...", callback_data="cb_stats")]
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
                    chat_id=chat_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            logger.info(f"Signal sent: {signal['pair_name']} {action} {signal['confidence']}%")
        except Exception as e:
            logger.error(f"Signal send error: {e}")

    async def send_result(self, chat_id: str, res: Dict):
        """Send Win/Loss result verification update."""
        is_win = res["is_win"]
        emoji  = "🟢" if is_win else "🔴"
        text = (
            f"{'🏆' if is_win else '⚠️'} <b>MINEXUS RESULT UPDATE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Asset:</b> {res['pair_name']}\n"
            f"🎲 <b>Signal:</b> {res['action']} · Confidence: {res['confidence']}%\n"
            f"{emoji} <b>Outcome: {res['result_status']}</b>  ({res['badge']})\n"
            f"📍 Entry: <code>{res['entry_price']:.5f}</code> → Exit: <code>{res['exit_price']:.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Session: {res['total_wins']}W – {res['total_losses']}L · "
            f"Win Rate: <b>{res['win_rate']}%</b>"
        )
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            logger.info(f"Result sent: {res['pair_name']} → {res['result_status']}")
        except Exception as e:
            logger.error(f"Result send error: {e}")
