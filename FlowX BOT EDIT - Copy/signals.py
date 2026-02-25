"""
Signals Module - Technical analysis and signal generation
"""

import numpy as np
from typing import Optional, List, Tuple
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, VOL_PERIOD


class SignalGenerator:
    """Generate trading signals based on technical analysis"""
    
    @staticmethod
    def calculate_ema(prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        import numpy as np
        # Ако е подадено число, го правим масив
        if isinstance(prices, (float, int, np.floating, np.integer)):
            prices = np.array([prices])
        if len(prices) < period:
            return np.mean(prices)
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)
        return ema
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, 
                      close: np.ndarray, period: int) -> float:
        """Calculate Average True Range"""
        import numpy as np
        # Ако е подадено число, го правим масив
        if isinstance(high, (float, int, np.floating, np.integer)):
            high = np.array([high])
        if isinstance(low, (float, int, np.floating, np.integer)):
            low = np.array([low])
        if isinstance(close, (float, int, np.floating, np.integer)):
            close = np.array([close])
        if len(high) < period:
            return np.mean(high - low)
        tr = np.maximum(
            high[1:] - low[1:],
            np.abs(high[1:] - close[:-1])
        )
        return np.mean(tr[-period:])
    
    @staticmethod
    def market_regime(atr: float, atr_history: List[float]) -> str:
        """Classify market regime"""
        if not atr_history:
            return "NORMAL"
        
        avg_atr = np.mean(atr_history)
        
        if atr < avg_atr * 0.8:
            return "CHOPPY"  # Low volatility
        elif atr > avg_atr * 1.3:
            return "TRENDING"  # High volatility
        else:
            return "NORMAL"
    
    @staticmethod
    def breakout_signal(close: np.ndarray, atr: float, lookback: int = 20) -> Optional[str]:
        """Detect breakout from range"""
        import numpy as np
        if isinstance(close, (float, int, np.floating, np.integer)):
            close = np.array([close])
        if len(close) < lookback:
            return None
        recent_range = max(close[-lookback:]) - min(close[-lookback:])
        # Breakout only in low consolidation
        if recent_range < atr * 1.2:
            if close[-1] > max(close[-lookback:-1]):
                return "BUY"
            elif close[-1] < min(close[-lookback:-1]):
                return "SELL"
        return None
    
    @staticmethod
    def trend_signal(price: float, ema50: float, ema200: float) -> Optional[str]:
        """Detect trend-based signal"""
        if price > ema50 > ema200:
            return "BUY"
        elif price < ema50 < ema200:
            return "SELL"
        return None
    
    @staticmethod
    def pullback_valid(price: float, ema50: float, ema200: float, 
                       atr: float, direction: str) -> bool:
        """Check if pullback is valid for entry"""
        tolerance = atr * 0.4
        distance_from_ema50 = abs(price - ema50)
        
        if direction == "BUY":
            # Price should be above EMA200, close to EMA50
            return (price > ema200 and distance_from_ema50 <= tolerance)
        
        elif direction == "SELL":
            # Price should be below EMA200, close to EMA50
            return (price < ema200 and distance_from_ema50 <= tolerance)
        
        return False
    
    @staticmethod
    def volume_confirmation(volume: np.ndarray, period: int = 20) -> float:
        """Get volume strength ratio"""
        import numpy as np
        if isinstance(volume, (float, int, np.floating, np.integer)):
            volume = np.array([volume])
        if len(volume) < period:
            return volume[-1] / np.mean(volume)
        avg_vol = np.mean(volume[-period:])
        return volume[-1] / avg_vol if avg_vol > 0 else 1.0

    # RSI Signal
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        import numpy as np
        if isinstance(prices, (float, int, np.floating, np.integer)):
            prices = np.array([prices])
        if len(prices) < period + 1:
            return 50
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def rsi_signal(rsi: float, direction: str = None) -> Optional[str]:
        """RSI Oversold/Overbought signal"""
        if rsi < 30:
            return "BUY"
        elif rsi > 70:
            return "SELL"
        return None

    # MACD Signal
    @staticmethod
    def calculate_macd(prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD (12, 26, 9)"""
        import numpy as np
        if isinstance(prices, (float, int, np.floating, np.integer)):
            prices = np.array([prices])
        ema12 = SignalGenerator.calculate_ema(prices, 12)
        ema26 = SignalGenerator.calculate_ema(prices, 26)
        macd = ema12 - ema26
        signal_line = SignalGenerator.calculate_ema(np.array([macd] * 9), 9)
        histogram = macd - signal_line
        return macd, signal_line, histogram

    @staticmethod
    def macd_signal(macd: float, signal_line: float, prev_histogram: float, curr_histogram: float) -> Optional[str]:
        """MACD crossover signal"""
        if prev_histogram < 0 and curr_histogram > 0:  # Bullish crossover
            return "BUY"
        elif prev_histogram > 0 and curr_histogram < 0:  # Bearish crossover
            return "SELL"
        return None

    # Stochastic Signal
    @staticmethod
    def calculate_stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Tuple[float, float]:
        """Calculate Stochastic Oscillator"""
        import numpy as np
        if isinstance(high, (float, int, np.floating, np.integer)):
            high = np.array([high])
        if isinstance(low, (float, int, np.floating, np.integer)):
            low = np.array([low])
        if isinstance(close, (float, int, np.floating, np.integer)):
            close = np.array([close])
        if len(close) < period:
            return 50, 50
        lowest_low = np.min(low[-period:])
        highest_high = np.max(high[-period:])
        k = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low) if (highest_high - lowest_low) > 0 else 50
        d = k  # Simplified (normally would be MA of K)
        return k, d

    @staticmethod
    def stochastic_signal(k: float, d: float) -> Optional[str]:
        """Stochastic oversold/overbought signal"""
        if k < 20 and d < 20:
            return "BUY"
        elif k > 80 and d > 80:
            return "SELL"
        return None


class TradeCalculator:
    """Calculate trade levels based on technical metrics"""
    
    @staticmethod
    def calculate_levels(price: float, atr: float, direction: str, 
                        risk_ratio: float = 1.2,
                        tp1_ratio: float = 0.8,
                        tp2_ratio: float = 1.6,
                        tp3_ratio: float = 2.4) -> Tuple[float, List[float]]:
        """
        Calculate SL and TP levels
        
        Returns:
            (stop_loss, [tp1, tp2, tp3])
        """
        sl_dist = atr * risk_ratio
        
        if direction == "BUY":
            sl = price - sl_dist
            tps = [
                price + atr * tp1_ratio,
                price + atr * tp2_ratio,
                price + atr * tp3_ratio
            ]
        else:  # SELL
            sl = price + sl_dist
            tps = [
                price - atr * tp1_ratio,
                price - atr * tp2_ratio,
                price - atr * tp3_ratio
            ]
        
        return sl, tps
