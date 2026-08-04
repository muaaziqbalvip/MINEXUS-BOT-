#!/usr/bin/env python3
"""
result_verifier.py - Automatic Trade Outcome & Result Tracker
Tracks emitted signals, waits for the trade duration expiry, fetches the closing price,
verifies whether the trade was a WIN 🟢 or LOSS 🔴, and updates the Telegram channel.
"""

import time
import logging
from typing import Dict, List
from market_data import MarketDataProvider, ALL_PAIRS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class ActiveTradeTracker:
    """Manages active trade signals and checks post-expiry outcomes."""

    def __init__(self):
        self.pending_trades: List[Dict] = []
        self.total_wins = 0
        self.total_losses = 0

    def add_trade(self, signal: Dict, duration_seconds: int = 60):
        """Adds a signal to the tracking queue with an expiry timestamp."""
        expiry_time = time.time() + duration_seconds
        trade = {
            "signal": signal,
            "entry_price": signal["entry_price"],
            "action": signal["action"],
            "expiry_time": expiry_time,
            "symbol": signal["symbol"],
            "pair_name": signal["pair_name"],
            "confidence": signal["confidence"],
            "message_id": None,
        }
        self.pending_trades.append(trade)
        logging.info(f"Tracking trade {signal['pair_name']} {signal['action']} expiring in {duration_seconds}s")

    def check_expired_trades(self) -> List[Dict]:
        """
        Scans pending trades. If expiry time is reached, fetches closing price,
        determines WIN/LOSS result, and returns result payloads.
        """
        now = time.time()
        completed_results = []
        remaining_trades = []

        for trade in self.pending_trades:
            if now >= trade["expiry_time"]:
                # Fetch live close price
                pair_info = next((p for p in ALL_PAIRS if p["symbol"] == trade["symbol"]), None)
                if pair_info:
                    exit_price = MarketDataProvider.fetch_live_price(pair_info)
                else:
                    exit_price = trade["entry_price"]

                entry_price = trade["entry_price"]
                action = trade["action"]

                # Win / Loss Logic
                if action == "CALL":
                    is_win = exit_price > entry_price
                else:  # PUT
                    is_win = exit_price < entry_price

                if is_win:
                    self.total_wins += 1
                    result_status = "WIN 🟢"
                    badge = "🏆 ITM (In The Money)"
                else:
                    self.total_losses += 1
                    result_status = "LOSS 🔴"
                    badge = "⚠️ OTM (Out of The Money)"

                total_trades = self.total_wins + self.total_losses
                win_rate = (self.total_wins / total_trades * 100.0) if total_trades > 0 else 0.0

                res_payload = {
                    "pair_name": trade["pair_name"],
                    "action": action,
                    "confidence": trade["confidence"],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "is_win": is_win,
                    "result_status": result_status,
                    "badge": badge,
                    "total_wins": self.total_wins,
                    "total_losses": self.total_losses,
                    "win_rate": round(win_rate, 1),
                }
                completed_results.append(res_payload)
                logging.info(f"Trade result: {trade['pair_name']} -> {result_status} (Entry: {entry_price}, Exit: {exit_price})")
            else:
                remaining_trades.append(trade)

        self.pending_trades = remaining_trades
        return completed_results
