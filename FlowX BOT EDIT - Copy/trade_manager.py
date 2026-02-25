"""
Trade Manager - Track and manage active trades
"""

from typing import Optional, Dict
from datetime import datetime
import pytz


class Trade:
    """Represents an active trade"""
    
    def __init__(self, trade_id: str, direction: str, entry: float, 
                 sl: float, tp1: float, tp2: float, tp3: float, atr: float = None):
        self.trade_id = trade_id
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp1 = tp1
        self.tp2 = tp2
        self.tp3 = tp3
        self.atr = atr

        self.volume = 0.0
        self.remaining = 0.0
        self.tp_fractions = [0.5, 0.25, 0.25]
        self.tp_hit = [False, False, False]
        self.be_sent = False
        self.order_sent = False
        self.counted = False  # For daily stat tracking
        # track peak/trough since entry for trailing SL
        self.peak_price = entry
        self.trough_price = entry
        
        self.opened_at = datetime.now()
        self.closed_at = None
        self.close_reason = None  # "TP", "SL", "MANUAL"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "trade_id": self.trade_id,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "tp_hit": self.tp_hit,
            "be_sent": self.be_sent,
            "order_sent": self.order_sent,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "close_reason": self.close_reason
        }


class TradeManager:
    """Manage active trades and trade history"""
    
    def __init__(self, logger):
        self.logger = logger
        self.active_trade: Optional[Trade] = None
        self.trade_history = []
    
    def open_trade(self, direction: str, entry: float, sl: float, 
                  tp1: float, tp2: float, tp3: float, atr: float = None, volume: float = 0.01, tp_fractions: list = None) -> Trade:
        """Open a new trade"""
        if self.active_trade is not None:
            self.logger.warn("Closing existing trade before opening new one")
            self.close_trade("MANUAL")
        
        trade_id = f"{direction}_{entry:.2f}_{datetime.now().timestamp()}"
        self.active_trade = Trade(trade_id, direction, entry, sl, tp1, tp2, tp3, atr)
        # set volume and partial TP fractions
        self.active_trade.volume = volume
        self.active_trade.remaining = volume
        if tp_fractions:
            self.active_trade.tp_fractions = tp_fractions
        
        self.logger.signal(f"TRADE OPENED: {direction} @ {entry:.2f}")
        return self.active_trade
    
    def close_trade(self, reason: str) -> Optional[Trade]:
        """Close active trade"""
        if self.active_trade is None:
            return None
        
        trade = self.active_trade
        trade.closed_at = datetime.now()
        trade.close_reason = reason
        
        self.trade_history.append(trade)
        
        self.logger.info(f"Trade closed: {reason}")
        self.active_trade = None
        
        return trade
    
    def mark_tp_hit(self, tp_level: int) -> bool:
        """Mark TP level as hit"""
        if self.active_trade is None:
            return False
        idx = tp_level - 1
        if 0 <= idx < 3 and not self.active_trade.tp_hit[idx]:
            self.active_trade.tp_hit[idx] = True
            frac = self.active_trade.tp_fractions[idx]
            # reduce remaining volume
            self.active_trade.remaining = round(self.active_trade.remaining * (1 - frac), 6)

            # if fully taken, close
            if self.active_trade.remaining <= 0.0001:
                self.close_trade("TP")

            return True

        return False
    
    def mark_sl_hit(self) -> bool:
        """Mark SL as hit"""
        if self.active_trade is None:
            return False
        
        self.close_trade("SL")
        return True
    
    def mark_be_warning_sent(self) -> bool:
        """Mark breakeven warning as sent"""
        if self.active_trade is None:
            return False
        
        self.active_trade.be_sent = True
        return True
    
    def move_sl_to_breakeven(self) -> bool:
        """Move SL to breakeven"""
        if self.active_trade is None:
            return False
        
        self.active_trade.sl = self.active_trade.entry
        return True

    def move_sl_to_trail(self, atr_multiplier: float) -> bool:
        """Move SL to a trailing level based on ATR multiplier.

        Returns True if SL was moved.
        """
        if self.active_trade is None:
            return False

        trade = self.active_trade
        if trade.atr is None or atr_multiplier is None:
            return False

        if trade.direction == "BUY":
            # compute trailing level from peak price
            trail_level = trade.peak_price - (atr_multiplier * trade.atr)
            # only move SL up (never down)
            if trail_level > trade.sl:
                trade.sl = trail_level
                return True
        else:
            trail_level = trade.trough_price + (atr_multiplier * trade.atr)
            # for SELL we only move SL down (more favorable)
            if trail_level < trade.sl:
                trade.sl = trail_level
                return True

        return False

    def update_peak_trough(self, price: float):
        """Update peak/trough since entry for trailing calculations"""
        if self.active_trade is None:
            return

        trade = self.active_trade
        if trade.direction == "BUY":
            trade.peak_price = max(trade.peak_price, price)
        else:
            trade.trough_price = min(trade.trough_price, price)
    
    def has_active_trade(self) -> bool:
        """Check if there's an active trade"""
        return self.active_trade is not None
    
    def get_pnl(self, current_price: float) -> float:
        """Calculate current P&L in pips"""
        if self.active_trade is None:
            return 0.0
        
        trade = self.active_trade
        if trade.direction == "BUY":
            return (current_price - trade.entry) * 10000
        else:
            return (trade.entry - current_price) * 10000
    
    def get_session_stats(self) -> Dict:
        """Get trading statistics"""
        closed_trades = [t for t in self.trade_history if t.closed_at is not None]
        
        wins = sum(1 for t in closed_trades if t.close_reason == "TP")
        losses = sum(1 for t in closed_trades if t.close_reason == "SL")
        
        winrate = (wins / len(closed_trades) * 100) if closed_trades else 0
        
        return {
            "total_trades": len(closed_trades),
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "active_trade": self.active_trade is not None
        }
