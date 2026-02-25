"""
Backtest System - Validate trading strategy on historical data
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import MetaTrader5 as mt5
from logger import Logger
from signals import SignalGenerator, TradeCalculator
from config import (
    SYMBOL, TIMEFRAME_MINUTES, EMA_FAST, EMA_SLOW, ATR_PERIOD,
    VOL_PERIOD, RISK_RATIO, TP1_RATIO, TP2_RATIO, TP3_RATIO
)


class BacktestTrade:
    """Represents a trade in backtest"""
    
    def __init__(self, entry_price: float, direction: str, sl: float, tps: List[float]):
        self.entry_price = entry_price
        self.direction = direction
        self.sl = sl
        self.tps = tps
        self.tp_hits = [False, False, False]
        
        self.exit_price = None
        self.exit_reason = None  # "TP", "SL"
        self.pnl = 0.0
        self.entry_bar = None
        self.exit_bar = None
    
    def check_exit(self, price: float, bar_idx: int) -> Optional[str]:
        """Check if trade should exit at this price"""
        
        if self.direction == "BUY":
            # Check TP hits (in order)
            for i, tp in enumerate(self.tps):
                if not self.tp_hits[i] and price >= tp:
                    self.tp_hits[i] = True
            
            # Check SL
            if price <= self.sl:
                self.exit_price = self.sl
                self.exit_reason = "SL"
                self.pnl = (self.sl - self.entry_price) * 10000  # Pips
                self.exit_bar = bar_idx
                return "SL"
            
            # Check TP3 (final)
            if price >= self.tps[2]:
                self.exit_price = self.tps[2]
                self.exit_reason = "TP"
                self.pnl = (self.tps[2] - self.entry_price) * 10000
                self.exit_bar = bar_idx
                return "TP"
        
        else:  # SELL
            # Check TP hits
            for i, tp in enumerate(self.tps):
                if not self.tp_hits[i] and price <= tp:
                    self.tp_hits[i] = True
            
            # Check SL
            if price >= self.sl:
                self.exit_price = self.sl
                self.exit_reason = "SL"
                self.pnl = (self.entry_price - self.sl) * 10000
                self.exit_bar = bar_idx
                return "SL"
            
            # Check TP3
            if price <= self.tps[2]:
                self.exit_price = self.tps[2]
                self.exit_reason = "TP"
                self.pnl = (self.entry_price - self.tps[2]) * 10000
                self.exit_bar = bar_idx
                return "TP"
        
        return None


class Backtester:
    """Run backtest on historical data"""
    
    def __init__(self, symbol: str, timeframe_minutes: int, logger: Logger):
        self.symbol = symbol
        self.timeframe_minutes = timeframe_minutes
        self.logger = logger
        self.trades = []
        self.signals_generated = 0
    
    def fetch_history(self, days_back: int) -> Optional[Dict]:
        """Fetch historical data"""
        try:
            if self.timeframe_minutes == 5:
                timeframe = mt5.TIMEFRAME_M5
            elif self.timeframe_minutes == 15:
                timeframe = mt5.TIMEFRAME_M15
            elif self.timeframe_minutes == 60:
                timeframe = mt5.TIMEFRAME_H1
            else:
                timeframe = mt5.TIMEFRAME_M5
            
            # Calculate bars needed
            bars_needed = (days_back * 24 * 60) // self.timeframe_minutes + 100
            
            rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars_needed)
            
            if rates is None:
                self.logger.error(f"Failed to fetch history: {mt5.last_error()}")
                return None
            
            return {
                "open": rates["open"],
                "high": rates["high"],
                "low": rates["low"],
                "close": rates["close"],
                "volume": rates["tick_volume"]
            }
        
        except Exception as e:
            self.logger.error(f"History fetch error: {e}")
            return None
    
    def run(self, days_back: int = 7) -> Dict:
        """Run backtest on historical data"""
        
        self.logger.ok(f"Starting backtest: {self.symbol} {days_back} days")
        
        # Fetch data
        data = self.fetch_history(days_back)
        if data is None:
            return None
        
        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]
        
        active_trade = None
        
        # Iterate through bars
        for bar_idx in range(200, len(close)):
            # Current bar data
            lookback_close = close[:bar_idx]
            lookback_high = high[:bar_idx]
            lookback_low = low[:bar_idx]
            lookback_volume = volume[:bar_idx]
            
            current_price = close[bar_idx]
            current_high = high[bar_idx]
            current_low = low[bar_idx]
            
            # Check active trade exit
            if active_trade is not None:
                # Check high and low of current bar
                exit_reason = None
                
                # Check if TP or SL hit in this bar
                if active_trade.direction == "BUY":
                    if current_low <= active_trade.sl:
                        exit_reason = active_trade.check_exit(active_trade.sl, bar_idx)
                    elif current_high >= active_trade.tps[2]:
                        exit_reason = active_trade.check_exit(active_trade.tps[2], bar_idx)
                else:
                    if current_high >= active_trade.sl:
                        exit_reason = active_trade.check_exit(active_trade.sl, bar_idx)
                    elif current_low <= active_trade.tps[2]:
                        exit_reason = active_trade.check_exit(active_trade.tps[2], bar_idx)
                
                if exit_reason:
                    self.trades.append(active_trade)
                    active_trade = None
                else:
                    # Trade still active
                    continue
            
            # Skip if active trade (don't generate new signals)
            if active_trade is not None:
                continue
            
            # Generate signal
            ema50 = SignalGenerator.calculate_ema(lookback_close, EMA_FAST)
            ema200 = SignalGenerator.calculate_ema(lookback_close, EMA_SLOW)
            atr = SignalGenerator.calculate_atr(
                lookback_high, lookback_low, lookback_close, ATR_PERIOD
            )
            
            # Check market regime
            atr_history = [atr] * 10
            regime = SignalGenerator.market_regime(atr, atr_history)
            
            if regime == "CHOPPY":
                continue
            
            # Get direction
            direction = SignalGenerator.breakout_signal(lookback_close, atr, 20)
            if direction is None:
                direction = SignalGenerator.trend_signal(current_price, ema50, ema200)
            
            if direction is None:
                continue
            
            # Validate pullback
            if not SignalGenerator.pullback_valid(current_price, ema50, ema200, atr, direction):
                continue
            
            # Calculate levels
            sl, tps = TradeCalculator.calculate_levels(
                current_price, atr, direction,
                RISK_RATIO, TP1_RATIO, TP2_RATIO, TP3_RATIO
            )
            
            # Open trade
            active_trade = BacktestTrade(current_price, direction, sl, tps)
            active_trade.entry_bar = bar_idx
            self.signals_generated += 1
        
        # Close remaining trade at last bar
        if active_trade is not None:
            active_trade.exit_price = close[-1]
            active_trade.exit_reason = "OPEN"
            active_trade.pnl = (
                (close[-1] - active_trade.entry_price) * 10000
                if active_trade.direction == "BUY"
                else (active_trade.entry_price - close[-1]) * 10000
            )
            self.trades.append(active_trade)
        
        return self._calculate_stats()
    
    def _calculate_stats(self) -> Dict:
        """Calculate backtest statistics"""
        
        if not self.trades:
            return {
                "trades_total": 0,
                "trades_won": 0,
                "trades_lost": 0,
                "winrate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "consecutive_wins": 0,
                "consecutive_losses": 0,
                "profit_factor": 0.0
            }
        
        wins = [t for t in self.trades if t.exit_reason == "TP"]
        losses = [t for t in self.trades if t.exit_reason == "SL"]
        
        win_pnls = [t.pnl for t in wins]
        loss_pnls = [t.pnl for t in losses]
        
        total_wins = sum(win_pnls) if win_pnls else 0.0
        total_losses = abs(sum(loss_pnls)) if loss_pnls else 0.0
        
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        max_consecutive = self._get_max_consecutive(wins, losses)
        
        return {
            "trades_total": len(self.trades),
            "trades_won": len(wins),
            "trades_lost": len(losses),
            "winrate": (len(wins) / len(self.trades) * 100) if self.trades else 0.0,
            "total_pnl": sum(t.pnl for t in self.trades),
            "avg_win": np.mean(win_pnls) if win_pnls else 0.0,
            "avg_loss": -np.mean(loss_pnls) if loss_pnls else 0.0,
            "largest_win": max(win_pnls) if win_pnls else 0.0,
            "largest_loss": -min(loss_pnls) if loss_pnls else 0.0,
            "consecutive_wins": max_consecutive["wins"],
            "consecutive_losses": max_consecutive["losses"],
            "profit_factor": profit_factor
        }
    
    def _get_max_consecutive(self, wins: List, losses: List) -> Dict:
        """Get max consecutive wins/losses"""
        
        sequence = []
        for trade in self.trades:
            sequence.append("W" if trade.exit_reason == "TP" else "L")
        
        max_w = 0
        max_l = 0
        current_w = 0
        current_l = 0
        
        for outcome in sequence:
            if outcome == "W":
                current_w += 1
                max_w = max(max_w, current_w)
                current_l = 0
            else:
                current_l += 1
                max_l = max(max_l, current_l)
                current_w = 0
        
        return {"wins": max_w, "losses": max_l}
    
    def print_report(self, stats: Dict):
        """Pretty-print backtest report"""
        
        self.logger.ok(
            f"\n{'='*60}\n"
            f"BACKTEST REPORT\n"
            f"{'='*60}\n"
            f"Total Trades: {stats['trades_total']}\n"
            f"Winning Trades: {stats['trades_won']} ({stats['winrate']:.1f}%)\n"
            f"Losing Trades: {stats['trades_lost']}\n"
            f"\n"
            f"Total P&L: {stats['total_pnl']:.0f} pips\n"
            f"Avg Win: {stats['avg_win']:.0f} pips\n"
            f"Avg Loss: {stats['avg_loss']:.0f} pips\n"
            f"Largest Win: {stats['largest_win']:.0f} pips\n"
            f"Largest Loss: {stats['largest_loss']:.0f} pips\n"
            f"\n"
            f"Max Consecutive Wins: {stats['consecutive_wins']}\n"
            f"Max Consecutive Losses: {stats['consecutive_losses']}\n"
            f"Profit Factor: {stats['profit_factor']:.2f}\n"
            f"{'='*60}\n"
        )
