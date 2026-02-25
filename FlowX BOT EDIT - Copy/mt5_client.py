"""
MT5 Client - MetaTrader5 integration and order execution
"""

import MetaTrader5 as mt5
from typing import Optional, Dict
from logger import Logger
from config import SYMBOL, MT5_MAGIC, ORDER_VOLUME


class MT5Client:
    """Handle MetaTrader5 connection and trading operations"""
    
    def __init__(self, symbol: str, logger: Logger):
        self.symbol = symbol
        self.logger = logger
        self.is_connected = False
    
    def initialize(self) -> bool:
        """Initialize MetaTrader5 connection"""
        try:
            if not mt5.initialize():
                self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            
            if not mt5.symbol_select(self.symbol, True):
                self.logger.error(f"Failed to select symbol {self.symbol}")
                return False
            
            self.is_connected = True
            self.logger.ok(f"MT5 connected, symbol {self.symbol} selected")
            return True
        
        except Exception as e:
            self.logger.error(f"MT5 initialization error: {e}")
            return False
    
    def shutdown(self):
        """Shutdown MetaTrader5 connection"""
        try:
            mt5.shutdown()
            self.is_connected = False
            self.logger.info("MT5 shutdown complete")
        except Exception as e:
            self.logger.error(f"MT5 shutdown error: {e}")
    
    def get_rates(self, timeframe: int, count: int) -> Optional[Dict]:
        """Fetch OHLCV data"""
        try:
            rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
            
            if rates is None:
                self.logger.warn(f"Failed to fetch rates: {mt5.last_error()}")
                return None
            
            return {
                "open": rates["open"],
                "high": rates["high"],
                "low": rates["low"],
                "close": rates["close"],
                "volume": rates["tick_volume"]
            }
        
        except Exception as e:
            self.logger.error(f"Rate fetch error: {e}")
            return None
    
    def get_tick(self) -> Optional[float]:
        """Get current bid/ask price"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            return tick if tick else None
        except Exception as e:
            self.logger.error(f"Tick fetch error: {e}")
            return None
    
    def get_positions(self) -> list:
        """Get open positions"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            return list(positions) if positions else []
        except Exception as e:
            self.logger.error(f"Position fetch error: {e}")
            return []
    
    def place_order(self, direction: str, volume: float, sl: float, 
                   tp: float, comment: str = "FlowX") -> Optional[Dict]:
        """
        Place market order
        
        Args:
            direction: "BUY" or "SELL"
            volume: Order volume (e.g., 0.01)
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment
        
        Returns:
            Order result or None
        """
        if not self.is_connected:
            self.logger.error("MT5 not connected")
            return None
        
        try:
            tick = self.get_tick()
            if not tick:
                self.logger.error("Cannot get current price")
                return None
            
            order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
            price = tick.ask if direction == "BUY" else tick.bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": MT5_MAGIC,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error("Order send returned None")
                return None
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.ok(f"Order placed: {direction} {volume} @ {price:.2f}")
                return {
                    "ticket": result.order,
                    "price": price,
                    "type": direction,
                    "volume": volume,
                    "sl": sl,
                    "tp": tp
                }
            else:
                self.logger.error(f"Order failed: {result.comment}")
                return None
        
        except Exception as e:
            self.logger.error(f"Order placement error: {e}")
            return None
    
    def close_position(self, position) -> bool:
        """Close a position"""
        try:
            tick = self.get_tick()
            if not tick:
                return False
            
            price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": price,
                "deviation": 20,
                "magic": MT5_MAGIC,
                "comment": "FlowX Manual Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            return result and result.retcode == mt5.TRADE_RETCODE_DONE
        
        except Exception as e:
            self.logger.error(f"Position close error: {e}")
            return False

