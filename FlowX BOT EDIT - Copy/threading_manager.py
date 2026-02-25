"""
Trade Monitor Thread - Monitor active trades without blocking signal generation
"""

import threading
import time
from typing import Callable, Optional
from logger import Logger


class TradeMonitorThread:
    """Separate thread for continuous trade monitoring"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.thread: Optional[threading.Thread] = None
        self.is_running = False
        self.callback: Optional[Callable] = None
        self.check_interval = 5  # Check every 5 seconds
    
    def set_callback(self, callback: Callable):
        """Set the monitoring callback function"""
        self.callback = callback
    
    def start(self):
        """Start the monitor thread"""
        if self.is_running:
            self.logger.warn("Monitor thread already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger.ok("Trade monitor thread started")
    
    def stop(self):
        """Stop the monitor thread"""
        self.is_running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.logger.info("Trade monitor thread stopped")
    
    def _run(self):
        """Main loop for monitor thread"""
        try:
            while self.is_running:
                if self.callback:
                    try:
                        self.callback()
                    except Exception as e:
                        self.logger.error(f"Monitor callback error: {e}")
                time.sleep(self.check_interval)
        
        except Exception as e:
            self.logger.error(f"Monitor thread error: {e}")
            self.is_running = False
    
    def is_alive(self) -> bool:
        """Check if thread is still running"""
        return self.is_running and (self.thread is None or self.thread.is_alive())


class SignalGeneratorThread:
    """Separate thread for signal generation"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.thread: Optional[threading.Thread] = None
        self.is_running = False
        self.callback: Optional[Callable] = None
        self.check_interval = 60  # Check every 60 seconds
    
    def set_callback(self, callback: Callable):
        """Set the signal generation callback"""
        self.callback = callback
    
    def start(self):
        """Start the signal generation thread"""
        if self.is_running:
            self.logger.warn("Signal thread already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger.ok("Signal generation thread started")
    
    def stop(self):
        """Stop the signal generation thread"""
        self.is_running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.logger.info("Signal generation thread stopped")
    
    def _run(self):
        """Main loop for signal generation thread"""
        try:
            while self.is_running:
                if self.callback:
                    try:
                        self.callback()
                    except Exception as e:
                        self.logger.error(f"Signal callback error: {e}")
                time.sleep(self.check_interval)
        
        except Exception as e:
            self.logger.error(f"Signal thread error: {e}")
            self.is_running = False
    
    def is_alive(self) -> bool:
        """Check if thread is still running"""
        return self.is_running and (self.thread is None or self.thread.is_alive())


class ThreadManager:
    """Manage all bot threads"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.monitor_thread = TradeMonitorThread(logger)
        self.signal_thread = SignalGeneratorThread(logger)
    
    def start_all(self):
        """Start all threads"""
        self.monitor_thread.start()
        self.signal_thread.start()
        self.logger.ok("All threads started")
    
    def stop_all(self):
        """Stop all threads"""
        self.monitor_thread.stop()
        self.signal_thread.stop()
        self.logger.ok("All threads stopped")
    
    def set_monitor_callback(self, callback: Callable):
        """Set trade monitor callback"""
        self.monitor_thread.set_callback(callback)
    
    def set_signal_callback(self, callback: Callable):
        """Set signal generation callback"""
        self.signal_thread.set_callback(callback)
    
    def all_alive(self) -> bool:
        """Check if all threads are alive"""
        return self.monitor_thread.is_alive() and self.signal_thread.is_alive()