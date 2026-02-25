"""
FlowX Trading Bot - Main Entry Point
Modular architecture with clean separation of concerns
Features: Threading, Capital Protection, Backtesting
"""

# Ensure project root is on sys.path so sibling modules import correctly
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))


import time
import numpy as np
from datetime import datetime, timedelta
import signal
import sys
import argparse
import MetaTrader5 as mt5

# Import all modules
import config
from logger import Logger
from memory_manager import MemoryManager
from telegram_client import TelegramClient
from session_manager import SessionManager
from news_filter import NewsFilter
from signals import SignalGenerator, TradeCalculator
from mt5_client import MT5Client
from trade_manager import TradeManager
from capital_protection import CapitalManager, RiskLimiter
from backtest import Backtester
from threading_manager import ThreadManager


class FlowXBot:
    """Main bot orchestrator with threading and capital protection"""
    
    def __init__(self, use_threading: bool = True):
        # Initialize core components
        self.logger = Logger(config.TZ, config.LOG_FILE)
        self.memory = MemoryManager(config.MEMORY_FILE, config.TZ)
        self.telegram = TelegramClient(config.BOT_TOKEN, config.CHAT_ID, self.logger)
        self.session_mgr = SessionManager(config.TZ)
        self.news_filter = NewsFilter(config.ECON_API_KEY, self.logger, config.TZ)
        self.mt5 = MT5Client(config.SYMBOL, self.logger)
        self.trade_mgr = TradeManager(self.logger)
        
        # Capital protection
        self.capital_mgr = CapitalManager(
            config.INITIAL_BALANCE,
            config.MAX_DRAWDOWN_PERCENT,
            self.logger,
            config.TZ
        )
        self.risk_limiter = RiskLimiter(self.logger)
        self.risk_limiter.daily_loss_limit = config.MAX_DAILY_LOSS
        
        # Threading
        self.use_threading = use_threading
        self.thread_mgr: ThreadManager = None
        if use_threading:
            self.thread_mgr = ThreadManager(self.logger)
        
        # State tracking
        self.last_signal_time = None
        self.signals_this_session = 0
        self.morning_sent = False
        self.evening_sent = False
        self.daily_report_sent = False
        self.current_day = datetime.now(config.TZ).date()
        
        # Daily stats
        self.daily_signals = 0
        self.daily_wins = 0
        self.daily_losses = 0
        # Weekly report tracking
        self.weekly_report_sent = False
        
        # Asian snapshot
        self.asian_snapshot = {
            "range": 0.0,
            "trend": "NEUTRAL",
            "volatility": 0.0
        }
    
    def startup(self):
        """Initialize bot"""
        # Декорация: FlowX + изображение на злато (ASCII Art)
        gold_art = '''
   ________      _      _   _   _   _
  |  ____  |    | |    | | | | | | | |
  | |    | |  __| | __ | |_| |_| |_| |  
  | |    | | / _` |/ _` |  _  _  _  _|
  | |____| || (_| | (_| | | | | | | |
  |________| \__,_|\__,_|_| |_| |_| |_|

        .: FLOWX GOLD :. 
        ╔══════════════════════╗
        ║   🟡 TRADE GOLD 🟡   ║
        ╚══════════════════════╝
        '''
        print(gold_art)
        self.logger.ok("FlowX Balanced Pro Engine LIVE")

        # Initialize MT5
        if not self.mt5.initialize():
            self.logger.error("Failed to initialize MT5")
            sys.exit(1)

        # Print capital status
        self.logger.ok(f"Starting capital: ${config.INITIAL_BALANCE:.2f}")
        self.logger.ok(f"Max drawdown threshold: {config.MAX_DRAWDOWN_PERCENT}%")
        self.logger.ok(f"Max daily loss: ${config.MAX_DAILY_LOSS:.2f}")

        # Send startup message
        self.telegram.startup()

        # Start threads
        if self.use_threading:
            self.thread_mgr.set_monitor_callback(self.monitor_active_trade)
            self.thread_mgr.set_signal_callback(self.generate_and_execute_signal)
            self.thread_mgr.start_all()
            self.logger.ok("Trading threads started (monitor + signal generator)")
    
    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        
        if self.use_threading and self.thread_mgr:
            self.thread_mgr.stop_all()
        
        self.mt5.shutdown()
        
        # Final capital report
        self.capital_mgr.report_stats()
        
        sys.exit(0)
    
    def process_rates(self) -> dict:
        """Fetch and analyze market data"""
        rates = self.mt5.get_rates(config.TIMEFRAME_MINUTES, 200)
        
        if rates is None:
            return None
        
        close = rates["close"]
        high = rates["high"]
        low = rates["low"]
        volume = rates["volume"]
        
        # Calculate indicators
        ema50 = SignalGenerator.calculate_ema(close, config.EMA_FAST)
        ema200 = SignalGenerator.calculate_ema(close, config.EMA_SLOW)
        atr = SignalGenerator.calculate_atr(high, low, close, config.ATR_PERIOD)
        
        return {
            "close": close,
            "high": high,
            "low": low,
            "volume": volume,
            "ema50": ema50,
            "ema200": ema200,
            "atr": atr,
            "price": close[-1]
        }
    
    def update_asian_session(self, data: dict):
        """Update Asian session snapshot"""
        close = data["close"]
        high = data["high"]
        low = data["low"]
        atr = data["atr"]
        
        range_val = max(high) - min(low)
        
        if close[-1] > close[0]:
            trend = "BULLISH"
        elif close[-1] < close[0]:
            trend = "BEARISH"
        else:
            trend = "RANGE"
        
        self.asian_snapshot = {
            "range": range_val,
            "trend": trend,
            "volatility": atr
        }
        
        self.memory.update_asian_snapshot(range_val, trend, atr)
    
    def check_daily_reset(self, now: datetime):
        """Reset daily statistics if new day"""
        if now.date() != self.current_day:
            self.logger.sys(f"New trading day: {now.date()}")
            self.current_day = now.date()
            self.daily_signals = 0
            self.daily_wins = 0
            self.daily_losses = 0
            self.daily_report_sent = False
            self.morning_sent = False
            self.evening_sent = False
            self.memory.reset_daily_stats()

            # Reset weekly flag on Monday
            if now.weekday() == 0:
                self.weekly_report_sent = False
            
            # Reset risk limiter
            self.risk_limiter.reset_daily_limits()
            self.capital_mgr.reset_daily_stats()
            
            self.logger.ok("Daily stats reset")
    
    def send_daily_messages(self, now: datetime):
        """Send morning/evening/report messages"""
        
        # Morning briefing
        if (now.time() >= config.MORNING_MESSAGE_TIME and not self.morning_sent):
            if self.asian_snapshot["volatility"] > 0:
                self.telegram.morning_briefing(
                    self.asian_snapshot["range"],
                    self.asian_snapshot["volatility"],
                    self.asian_snapshot["trend"]
                )
            self.morning_sent = True
        
        # Evening briefing
        if (now.time() >= config.EVENING_MESSAGE_TIME and not self.evening_sent):
            self.telegram.evening_briefing()
            self.evening_sent = True
        
        # Daily report
        if (now.time() >= config.DAILY_REPORT_TIME and not self.daily_report_sent):
            self.telegram.daily_performance_report(
                self.daily_signals,
                self.daily_wins,
                self.daily_losses
            )
            
            # Include capital report
            self.capital_mgr.report_stats()
            
            self.daily_report_sent = True

        # Weekly report (send on Sunday at daily report time)
        try:
            if now.weekday() == 6 and not self.weekly_report_sent and now.time() >= config.DAILY_REPORT_TIME:
                # compute last 7 days stats from trade history
                wins = 0
                losses = 0
                signals = 0
                cutoff = now.date() - timedelta(days=7)
                for t in self.trade_mgr.trade_history:
                    if t.closed_at is None:
                        continue
                    # compare dates (t.closed_at may be naive)
                    closed_date = t.closed_at.date() if hasattr(t.closed_at, 'date') else None
                    if closed_date and closed_date >= cutoff:
                        signals += 1
                        if t.close_reason == 'TP':
                            wins += 1
                        elif t.close_reason == 'SL':
                            losses += 1

                self.telegram.weekly_performance_report(signals, wins, losses)
                self.weekly_report_sent = True
        except Exception:
            pass
    
    def generate_and_execute_signal(self):
        """
        Generate and execute signal (can run in separate thread)
        Only generates signal if no active trade
        """
        # Начален таймер при стартиране (например 10 минути)
        WAIT_AFTER_START_MINUTES = 10
        WAIT_AFTER_TRADE_MINUTES = 10
        now = datetime.now(config.TZ)

        # Ако ботът току-що е стартирал, изчакай
        if not hasattr(self, 'start_time'):
            self.start_time = now
        if (now - self.start_time).total_seconds() < WAIT_AFTER_START_MINUTES * 60:
            return

        # Забавяне след отваряне на позиция
        if self.trade_mgr.has_active_trade():
            if hasattr(self, 'last_trade_close_time'):
                if (now - self.last_trade_close_time).total_seconds() < WAIT_AFTER_TRADE_MINUTES * 60:
                    return
            return

        # Skip if capital protection triggered
        if not self.capital_mgr.can_trade():
            self.logger.warn("Trading disabled: Capital protection active")
            return

        # Skip if capital protection threshold exceeded
        if not self.capital_mgr.check_capital_protection():
            self.shutdown()

        session = self.session_mgr.get_current_session(now)

        # Skip if not in trading hours
        if session == "OFF":
            return

        # Skip if in session opening guard
        if self.session_mgr.is_session_opening(session, now):
            return

        # Fetch market data
        data = self.process_rates()
        if data is None:
            return

        # Update Asian snapshot
        if session == "ASIAN":
            self.update_asian_session(data)

        # Check for high-impact news
        can_trade, reason = self.news_filter.should_trade(now)
        if not can_trade:
            return

        # Check risk limits
        if not self.risk_limiter.can_open_trade(1 if self.trade_mgr.has_active_trade() else 0):
            return

        # Generate signal
        signal = self.generate_signal(data, session)

        if signal:
            self.execute_signal(signal, session)
            self.last_trade_close_time = now
    
    def generate_signal(self, data: dict, session: str) -> dict:
        """Generate trading signal from market data, с мултитаймфрейм потвърждение (5m, 15m, 4h) + RSI/MACD + Structure Break (BOS)"""
        close = data["close"]
        price = data["price"]
        ema50 = data["ema50"]
        ema200 = data["ema200"]
        atr = data["atr"]
        volume = data["volume"]

        # RSI (14)
        def calc_rsi(prices, period=14):
            deltas = np.diff(prices)
            seed = deltas[:period]
            up = seed[seed > 0].sum() / period
            down = -seed[seed < 0].sum() / period
            rs = up / down if down != 0 else 0
            rsi = np.zeros_like(prices)
            rsi[:period] = 50
            for i in range(period, len(prices)):
                delta = deltas[i - 1]
                upval = max(delta, 0)
                downval = -min(delta, 0)
                up = (up * (period - 1) + upval) / period
                down = (down * (period - 1) + downval) / period
                rs = up / down if down != 0 else 0
                rsi[i] = 100 - 100 / (1 + rs)
            return rsi

        # MACD
        def calc_macd(prices, fast=12, slow=26, signal=9):
            ema_fast = SignalGenerator.calculate_ema(prices, fast)
            ema_slow = SignalGenerator.calculate_ema(prices, slow)
            macd_line = ema_fast - ema_slow
            signal_line = SignalGenerator.calculate_ema(macd_line, signal)
            hist = macd_line - signal_line
            return macd_line, signal_line, hist

        # Structure Break (BOS) - simple swing high/low break
        def structure_break(prices, direction, lookback=20):
            if len(prices) < lookback + 2:
                return False
            highs = prices[-lookback-1:-1]
            lows = prices[-lookback-1:-1]
            last_close = prices[-1]
            prev_high = np.max(highs)
            prev_low = np.min(lows)
            if direction == "BUY":
                return last_close > prev_high
            elif direction == "SELL":
                return last_close < prev_low
            return False

        rsi = calc_rsi(np.array(close))
        if isinstance(rsi, (float, int, np.floating, np.integer)):
            rsi = np.array([rsi])
        macd_line, signal_line, macd_hist = calc_macd(np.array(close))
        if isinstance(macd_line, (float, int, np.floating, np.integer)):
            macd_line = np.array([macd_line])
        if isinstance(macd_hist, (float, int, np.floating, np.integer)):
            macd_hist = np.array([macd_hist])

        # 1. Check market regime
        atr_history = [atr] * 10  # Simplified
        regime = SignalGenerator.market_regime(atr, atr_history)
        if regime == "CHOPPY":
            self.logger.think("Market too choppy, skipping")
            return None

        # 2. Check volume
        vol_ratio = SignalGenerator.volume_confirmation(volume, config.VOL_PERIOD)
        if vol_ratio < 0.5:
            self.logger.think(f"Low volume (ratio={vol_ratio:.2f}), skipping")
            return None

        # 3. Generate signal (5m)
        direction = SignalGenerator.breakout_signal(close, atr, 20)
        if direction is None:
            direction = SignalGenerator.trend_signal(price, ema50, ema200)
        if direction is None:
            return None

        # --- Индикаторен филтър ---
        # RSI: не търгувай ако е над 80 или под 20
        if rsi[-1] > 80 or rsi[-1] < 20:
            self.logger.think(f"RSI extreme ({rsi[-1]:.1f}), skipping")
            return None

        # MACD: търгувай само ако macd_line и hist са в посока на сигнала
        if direction == "BUY" and (macd_line[-1] < 0 or macd_hist[-1] < 0):
            self.logger.think("MACD не потвърждава BUY, skipping")
            return None
        if direction == "SELL" and (macd_line[-1] > 0 or macd_hist[-1] > 0):
            self.logger.think("MACD не потвърждава SELL, skipping")
            return None

        # --- Structure Break (BOS) ---
        if session in ("NEW_YORK", "ASIAN"):
            if not structure_break(np.array(close), direction, lookback=20):
                self.logger.think(f"No structure break for {direction} in {session}, skipping")
                return None

        # --- Мултитаймфрейм потвърждение ---
        import MetaTrader5 as mt5
        # 15m timeframe
        rates_15m = self.mt5.get_rates(mt5.TIMEFRAME_M15, 200)
        if rates_15m is None:
            self.logger.warn("Неуспешно извличане на 15m данни за MTF потвърждение")
            return None
        close_15m = rates_15m["close"]
        if isinstance(close_15m, (float, int, np.floating, np.integer)):
            close_15m = np.array([close_15m])
        ema50_15m = SignalGenerator.calculate_ema(close_15m, config.EMA_FAST)
        ema200_15m = SignalGenerator.calculate_ema(close_15m, config.EMA_SLOW)
        direction_15m = SignalGenerator.trend_signal(close_15m[-1], ema50_15m, ema200_15m)
        if direction_15m != direction:
            self.logger.think(f"MTF: 15m не потвърждава {direction}, skipping")
            return None

        # 4h timeframe
        rates_4h = self.mt5.get_rates(mt5.TIMEFRAME_H4, 200)
        if rates_4h is None:
            self.logger.warn("Неуспешно извличане на 4h данни за MTF потвърждение")
            return None
        close_4h = rates_4h["close"]
        if isinstance(close_4h, (float, int, np.floating, np.integer)):
            close_4h = np.array([close_4h])
        ema50_4h = SignalGenerator.calculate_ema(close_4h, config.EMA_FAST)
        ema200_4h = SignalGenerator.calculate_ema(close_4h, config.EMA_SLOW)
        direction_4h = SignalGenerator.trend_signal(close_4h[-1], ema50_4h, ema200_4h)
        if direction_4h != direction:
            self.logger.think(f"MTF: 4h не потвърждава {direction}, skipping")
            return None

        # 4. Validate pullback (relaxed: only skip if extremely invalid)
        pullback_score = SignalGenerator.pullback_valid(price, ema50, ema200, atr, direction)
        if pullback_score is False:
            self.logger.think(f"Invalid pullback for {direction}, skipping")
            return None

        # 5. Calculate levels
        sl, tps = TradeCalculator.calculate_levels(
            price, atr, direction,
            config.RISK_RATIO,
            config.TP1_RATIO,
            config.TP2_RATIO,
            config.TP3_RATIO
        )

        return {
            "direction": direction,
            "price": price,
            "sl": sl,
            "tps": tps,
            "atr": atr,
            "rsi": rsi[-1],
            "macd": macd_line[-1],
            "macd_hist": macd_hist[-1]
        }
    
    def execute_signal(self, signal: dict, session: str):
        """Execute a trading signal"""
        # Calculate volume using percent-based sizing
        try:
            volume = self.mt5.calculate_volume(signal["sl"], signal["price"])
        except Exception:
            volume = config.ORDER_VOLUME

        # Calculate partial TP fractions (use default or config)
        tp_fractions = getattr(config, 'TP_FRACTIONS', [0.5, 0.25, 0.25])

        # Open trade in manager (track it)
        trade = self.trade_mgr.open_trade(
            signal["direction"],
            signal["price"],
            signal["sl"],
            signal["tps"][0],
            signal["tps"][1],
            signal["tps"][2],
            signal.get("atr", None),
            volume=volume,
            tp_fractions=tp_fractions
        )

        # Send Telegram notification
        self.telegram.send_signal(
            signal["direction"],
            signal["price"],
            signal["sl"],
            signal["tps"],
            session
        )

        # Place order on MT5
        result = self.mt5.place_order(
            signal["direction"],
            volume,
            signal["sl"],
            signal["tps"][2],
            f"FlowX {signal['direction']}"
        )

        if result:
            trade.order_sent = True
            self.daily_signals += 1
            self.memory.increment_daily_stat("signals_today")

        else:
            self.logger.error("Order placement failed. No position opened.")

        self.last_signal_time = datetime.now(config.TZ)
        self.signals_this_session += 1
    
    def monitor_active_trade(self):
        """Monitor and manage active trade with clear Telegram summary for partial TP and SL"""
        if not self.trade_mgr.has_active_trade():
            return

        trade = self.trade_mgr.active_trade
        tick = self.mt5.get_tick()

        if not tick:
            return

        price = tick.ask if trade.direction == "BUY" else tick.bid

        # Track if partial TP was hit before SL
        partial_tp_hit = False
        partial_tp_level = 0

        # Check TP1
        if not trade.tp_hit[0]:
            if (trade.direction == "BUY" and price >= trade.tp1) or \
               (trade.direction == "SELL" and price <= trade.tp1):
                self.trade_mgr.mark_tp_hit(1)
                self.telegram.tp_hit(1)
                self.telegram.breakeven_warning()
                self.daily_wins += 1
                trade.counted = True
                partial_tp_hit = True
                partial_tp_level = 1

                # Move SL to breakeven (ако желаеш автоматично)
                self.trade_mgr.move_sl_to_breakeven()

                # BE warning logic и условен alert за опасност
                atr_val = SignalGenerator.calculate_atr(
                    np.array([tick.ask if trade.direction == "BUY" else tick.bid] * 14),
                    np.array([tick.bid if trade.direction == "BUY" else tick.ask] * 14),
                    np.array([price] * 14),
                    14
                )

                be_zone = atr_val * 0.25
                danger = False

                # Условие: ако цената се върне близо до входа след TP1
                if trade.direction == "BUY":
                    danger = price <= trade.entry + be_zone
                else:
                    danger = price >= trade.entry - be_zone

                # Допълнително: ако последната свещ е контра и по-голяма от средната (примерна логика)
                candle_size = abs(tick.ask - tick.bid)
                avg_candle = atr_val  # ATR като среден размер
                is_counter = False
                if trade.direction == "BUY" and tick.bid < tick.ask and candle_size > avg_candle:
                    is_counter = True
                if trade.direction == "SELL" and tick.ask < tick.bid and candle_size > avg_candle:
                    is_counter = True

                # Изпрати alert само при опасност
                if (danger or is_counter) and not trade.be_sent:
                    self.telegram.send_message("⚠️ Пазарът обръща! Помислете за затваряне на сделката или преместване на SL на BE.")
                    self.trade_mgr.mark_be_warning_sent()

        # Check TP2
        if not trade.tp_hit[1]:
            if (trade.direction == "BUY" and price >= trade.tp2) or \
               (trade.direction == "SELL" and price <= trade.tp2):
                self.trade_mgr.mark_tp_hit(2)
                self.telegram.tp_hit(2)
                partial_tp_hit = True
                partial_tp_level = 2

                # Условие: ако цената се върне близо до входа след TP2 или има контра-свещ
                atr_val = SignalGenerator.calculate_atr(
                    np.array([tick.ask if trade.direction == "BUY" else tick.bid] * 14),
                    np.array([tick.bid if trade.direction == "BUY" else tick.ask] * 14),
                    np.array([price] * 14),
                    14
                )
                be_zone = atr_val * 0.25
                danger = False
                if trade.direction == "BUY":
                    danger = price <= trade.entry + be_zone
                else:
                    danger = price >= trade.entry - be_zone

                candle_size = abs(tick.ask - tick.bid)
                avg_candle = atr_val
                is_counter = False
                if trade.direction == "BUY" and tick.bid < tick.ask and candle_size > avg_candle:
                    is_counter = True
                if trade.direction == "SELL" and tick.ask < tick.bid and candle_size > avg_candle:
                    is_counter = True

                if (danger or is_counter) and not trade.be_sent:
                    self.telegram.send_message("⚠️ Пазарът обръща! Помислете за затваряне на сделката или преместване на SL на BE.")
                    self.trade_mgr.mark_be_warning_sent()

        # Check TP3 (close trade)
        if (trade.direction == "BUY" and price >= trade.tp3) or \
           (trade.direction == "SELL" and price <= trade.tp3):
            self.trade_mgr.close_trade("TP")
            self.telegram.tp_hit(3, is_final=True)
            return

        # Check SL
        if (trade.direction == "BUY" and price <= trade.sl) or \
           (trade.direction == "SELL" and price >= trade.sl):
            self.trade_mgr.mark_sl_hit()

            # Ново: ако има частично затваряне, изпрати обобщено съобщение
            if trade.tp_hit[1]:
                self.telegram.send_message("TP1 и TP2 са ударени, остатъкът затворен на SL.")
            elif trade.tp_hit[0]:
                self.telegram.send_message("TP1 е ударен, остатъкът затворен на SL.")
            else:
                self.telegram.sl_hit()

            # Record loss for risk limiter
            loss_amount = abs((price - trade.entry) * 10000)
            self.risk_limiter.record_loss(loss_amount)

            if not trade.counted:
                self.daily_losses += 1
                trade.counted = True

        # Update peak/trough and apply ATR-based trailing stop
        try:
            self.trade_mgr.update_peak_trough(price)
            moved = self.trade_mgr.move_sl_to_trail(config.TRAIL_ATR_MULTIPLIER)
            if moved:
                self.logger.sys("Trailing SL adjusted based on ATR")
                self.telegram.send_message("🔁 Trailing SL adjusted based on ATR")
        except Exception:
            pass
    
    def main_loop(self):
        """Main bot loop"""
        self.logger.ok("Starting main loop...")
        
        # If threading enabled, threads handle trading
        # This loop just handles daily messages and monitoring
        if self.use_threading:
            return self._main_loop_threaded()
        else:
            return self._main_loop_sync()
    
    def _main_loop_threaded(self):
        """Main loop with threading enabled"""
        self.logger.ok("Using threaded architecture")
        
        while True:
            try:
                now = datetime.now(config.TZ)
                
                # Check capital protection
                if not self.capital_mgr.check_capital_protection():
                    self.telegram.sys_status(
                        "🔒 <b>CAPITAL PROTECTION TRIGGERED</b>\n\n"
                        f"Drawdown: {self.capital_mgr.calculate_drawdown():.2f}%\n"
                        "Trading has been disabled."
                    )
                    self.shutdown()
                
                # Daily reset and messages
                self.check_daily_reset(now)
                self.send_daily_messages(now)
                
                # Heartbeat
                self.logger.sys(f"Heartbeat | Drawdown: {self.capital_mgr.calculate_drawdown():.2f}%")
                
                # Check threads are alive
                if not self.thread_mgr.all_alive():
                    self.logger.error("Thread crashed!")
                    self.shutdown()
                
                time.sleep(30)  # Check every 30 seconds
            
            except KeyboardInterrupt:
                self.logger.warn("Keyboard interrupt received")
                self.shutdown()
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(30)
    
    def _main_loop_sync(self):
        """Main loop without threading (synchronous)"""
        self.logger.ok("Using synchronous architecture")
        
        while True:
            try:
                now = datetime.now(config.TZ)
                session = self.session_mgr.get_current_session(now)
                
                # Heartbeat
                self.logger.sys(f"Heartbeat | Session: {session}")
                
                # Daily reset and messages
                self.check_daily_reset(now)
                self.send_daily_messages(now)
                
                # Check capital protection
                if not self.capital_mgr.check_capital_protection():
                    self.telegram.sys_status(
                        "🔒 <b>CAPITAL PROTECTION TRIGGERED</b>\n\n"
                        f"Drawdown: {self.capital_mgr.calculate_drawdown():.2f}%\n"
                        "Trading has been disabled."
                    )
                    self.shutdown()
                
                # Skip if not in trading hours
                if session == "OFF":
                    time.sleep(config.CHECK_INTERVAL_SECONDS)
                    continue
                
                # Skip if in session opening guard
                if self.session_mgr.is_session_opening(session, now):
                    self.logger.think(f"{session} opening guard active, waiting...")
                    time.sleep(60)
                    continue
                
                # Skip if active trade
                if self.trade_mgr.has_active_trade():
                    self.monitor_active_trade()
                    time.sleep(30)
                    continue
                
                # Monitor active trade
                self.monitor_active_trade()
                
                # Generate and execute signal
                self.generate_and_execute_signal()
                
                time.sleep(config.CHECK_INTERVAL_SECONDS)
            
            except KeyboardInterrupt:
                self.logger.warn("Keyboard interrupt received")
                self.shutdown()
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(config.CHECK_INTERVAL_SECONDS)


def main():
    """Entry point with command-line arguments"""
    parser = argparse.ArgumentParser(description="FlowX Trading Bot")
    parser.add_argument("--backtest", type=int, default=0, 
                       help="Run backtest on N days of history (0=disabled)")
    parser.add_argument("--no-threading", action="store_true",
                       help="Disable threading (run synchronously)")
    
    args = parser.parse_args()
    
    # Initialize MT5 first
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        sys.exit(1)
        sys.exit(1)
    
    # Run backtest if requested
    if args.backtest > 0:
        logger = Logger(config.TZ)
        logger.ok(f"Running backtest on {args.backtest} days...")
        
        backtester = Backtester(config.SYMBOL, config.TIMEFRAME_MINUTES, logger)
        results = backtester.run(args.backtest)
        
        if results:
            backtester.print_report(results)
            print(f"\n✅ Backtest complete")
            print(f"Total trades: {results['trades_total']}")
            print(f"Winrate: {results['winrate']:.1f}%")
            print(f"Total P&L: {results['total_pnl']:.0f} pips")
        
        mt5.shutdown()
        sys.exit(0)
    
    # Run live trading
    bot = FlowXBot(use_threading=not args.no_threading)
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        bot.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bot.startup()
    bot.main_loop()


if __name__ == "__main__":
    main()
