"""
Capital Protection - Monitor drawdown and stop trading if thresholds exceeded
"""

from typing import Dict, Optional
from datetime import datetime
import pytz
from logger import Logger


class CapitalManager:
    """Manage capital and monitor drawdown"""
    
    def __init__(self, initial_balance: float, max_drawdown_percent: float, 
                 logger: Logger, timezone: pytz.timezone):
        """
        Args:
            initial_balance: Starting account balance
            max_drawdown_percent: Maximum allowed drawdown (e.g., 5.0 for 5%)
            logger: Logger instance
            timezone: Timezone for timestamps
        """
        self.initial_balance = initial_balance
        self.max_drawdown_percent = max_drawdown_percent
        self.current_balance = initial_balance
        self.peak_balance = initial_balance
        self.logger = logger
        self.tz = timezone
        
        self.is_protected = False  # Flag if drawdown exceeded
        self.protection_triggered_at = None
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_peak = initial_balance
    
    def update_balance(self, new_balance: float):
        """Update current account balance"""
        self.current_balance = new_balance
        
        # Update peak if higher
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
            self.logger.ok(f"New peak balance: ${new_balance:.2f}")
    
    def calculate_drawdown(self) -> float:
        """
        Calculate current drawdown percentage
        
        Returns:
            Drawdown as percentage (0-100)
        """
        if self.peak_balance == 0:
            return 0.0
        
        drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        return max(0.0, drawdown)
    
    def calculate_daily_pnl(self, current_balance: float) -> float:
        """Calculate P&L for current day"""
        return current_balance - self.daily_peak
    
    def is_drawdown_exceeded(self) -> bool:
        """Check if drawdown exceeds threshold"""
        drawdown = self.calculate_drawdown()
        return drawdown >= self.max_drawdown_percent
    
    def check_capital_protection(self) -> bool:
        """
        Monitor capital and trigger protection if needed
        
        Returns:
            True if trading should continue, False if protection triggered
        """
        if self.is_drawdown_exceeded() and not self.is_protected:
            self.is_protected = True
            self.protection_triggered_at = datetime.now(self.tz)
            
            current_drawdown = self.calculate_drawdown()
            self.logger.error(
                f"CAPITAL PROTECTION TRIGGERED! "
                f"Drawdown: {current_drawdown:.2f}% (threshold: {self.max_drawdown_percent}%)"
            )
            
            return False
        
        return not self.is_protected
    
    def can_trade(self) -> bool:
        """Check if trading is allowed"""
        return not self.is_protected
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.daily_peak = self.current_balance
    
    def get_stats(self) -> Dict:
        """Get comprehensive capital stats"""
        drawdown = self.calculate_drawdown()
        
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "drawdown_percent": drawdown,
            "drawdown_allowed": self.max_drawdown_percent,
            "total_pnl": self.current_balance - self.initial_balance,
            "total_pnl_percent": ((self.current_balance - self.initial_balance) / self.initial_balance) * 100,
            "is_protected": self.is_protected,
            "protection_triggered_at": self.protection_triggered_at.isoformat() if self.protection_triggered_at else None,
            "daily_pnl": self.daily_pnl,
            "daily_peak": self.daily_peak
        }
    
    def report_stats(self):
        """Log capital stats"""
        stats = self.get_stats()
        
        status = "🔒 PROTECTED" if stats["is_protected"] else "🟢 ACTIVE"
        
        self.logger.info(
            f"{status}\n"
            f"Balance: ${stats['current_balance']:.2f} "
            f"(Peak: ${stats['peak_balance']:.2f})\n"
            f"Drawdown: {stats['drawdown_percent']:.2f}% / {stats['drawdown_allowed']:.2f}%\n"
            f"Total P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_percent']:.2f}%)"
        )


class RiskLimiter:
    """Additional risk controls beyond drawdown"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.max_concurrent_trades = 1  # Only 1 active trade at a time
        self.daily_loss_limit = 100.0  # Max daily loss in dollars
        self.daily_losses = 0.0
    
    def can_open_trade(self, active_trades_count: int) -> bool:
        """Check if new trade can be opened"""
        if active_trades_count >= self.max_concurrent_trades:
            self.logger.warn(f"Max concurrent trades ({self.max_concurrent_trades}) reached")
            return False
        return True
    
    def record_loss(self, loss_amount: float):
        """Record a loss"""
        self.daily_losses += loss_amount
        self.logger.warn(f"Daily losses: ${self.daily_losses:.2f} / ${self.daily_loss_limit:.2f}")
    
    def reset_daily_limits(self):
        """Reset daily loss tracking"""
        self.daily_losses = 0.0
    
    def get_remaining_risk_budget(self) -> float:
        """Get remaining loss budget for the day"""
        return max(0.0, self.daily_loss_limit - self.daily_losses)