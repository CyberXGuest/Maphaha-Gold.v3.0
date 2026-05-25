#!/usr/bin/env python3
"""
Maphaha Gold Trading System v3.1 - Kali Linux Professional Edition
No external dependencies - uses only standard library + numpy
"""

import os
import sys
import time
import json
import signal
import logging
import sqlite3
import random
import math
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from abc import ABC, abstractmethod
import argparse

# Try to import numpy (optional, for better performance)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Create dummy numpy-like functions
    class DummyNumpy:
        @staticmethod
        def mean(arr):
            return sum(arr) / len(arr) if arr else 0
        @staticmethod
        def std(arr):
            if len(arr) < 2:
                return 0
            mean = sum(arr) / len(arr)
            variance = sum((x - mean) ** 2 for x in arr) / len(arr)
            return math.sqrt(variance)
        @staticmethod
        def random_normal(mean, std):
            return random.gauss(mean, std)
    
    np = DummyNumpy()

# Try to import termcolor (optional)
try:
    from termcolor import colored
    TERMCOLOR_AVAILABLE = True
except ImportError:
    TERMCOLOR_AVAILABLE = False

# ============================================
# CONFIGURATION
# ============================================

VERSION = "3.1.0"
AUTHOR = "Maphaha Trading Systems"

class Config:
    """Global configuration settings"""
    # Trading Settings
    INITIAL_CAPITAL = 10000.0
    BASE_LOT_SIZE = 0.20
    MAX_POSITIONS = 5
    RISK_PER_TRADE = 0.02  # 2% risk per trade
    MAX_DAILY_LOSS = 500.0  # Maximum daily loss in USD
    MAX_DAILY_TRADES = 20   # Maximum trades per day
    
    # Strategy Parameters
    AMA_FAST_PERIOD = 10
    AMA_SLOW_PERIOD = 20
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    BB_PERIOD = 20
    BB_STD = 2
    
    SIGNAL_THRESHOLD_STRONG = 85
    SIGNAL_THRESHOLD_WEAK = 60
    STOP_LOSS_PTS = 1000
    TAKE_PROFIT_PTS = 1500
    
    # System Settings
    UPDATE_INTERVAL = 3  # seconds
    HISTORY_BARS = 500
    ENABLE_LOGGING = True
    ENABLE_SOUND = False
    
    # File Paths
    LOG_DIR = os.path.expanduser("~/maphaha_logs")
    DB_PATH = os.path.expanduser("~/maphaha_trading.db")
    REPORT_DIR = os.path.expanduser("~/maphaha_reports")
    
    # Color Scheme (ANSI)
    COLORS = {
        'GREEN': '\033[92m',
        'RED': '\033[91m',
        'YELLOW': '\033[93m',
        'CYAN': '\033[96m',
        'MAGENTA': '\033[95m',
        'BLUE': '\033[94m',
        'WHITE': '\033[97m',
        'BOLD': '\033[1m',
        'DIM': '\033[2m',
        'RESET': '\033[0m',
        'BG_GREEN': '\033[42m',
        'BG_RED': '\033[41m',
        'BG_YELLOW': '\033[43m',
        'BG_BLUE': '\033[44m'
    }

# ============================================
# LOGGING SYSTEM
# ============================================

class TradingLogger:
    """Professional logging system"""
    
    def __init__(self):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        
        log_file = os.path.join(Config.LOG_DIR, f"trading_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger("MaphahaGold")
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)
    
    def debug(self, msg):
        self.logger.debug(msg)

# ============================================
# ENUMS AND DATA CLASSES
# ============================================

class SignalType(Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"

class OrderStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Trade:
    """Enhanced trade object"""
    id: int
    symbol: str
    direction: SignalType
    entry_price: float
    volume: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    profit: float = 0.0
    profit_pips: float = 0.0
    status: OrderStatus = OrderStatus.OPEN
    notes: str = ""
    tags: List[str] = field(default_factory=list)

@dataclass
class TradingSignal:
    """Enhanced trading signal"""
    type: SignalType
    strength: float
    confidence: float  # 0-100%
    timestamp: datetime
    indicators: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

# ============================================
# DATABASE MANAGER
# ============================================

class DatabaseManager:
    """SQLite database manager"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize all database tables"""
        with sqlite3.connect(self.db_path) as conn:
            # Trades table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    volume REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    profit REAL DEFAULT 0,
                    profit_pips REAL DEFAULT 0,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    status TEXT DEFAULT 'OPEN',
                    notes TEXT,
                    tags TEXT
                )
            """)
            
            # Daily performance table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    best_trade REAL DEFAULT 0,
                    worst_trade REAL DEFAULT 0
                )
            """)
            
            # Market data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER DEFAULT 0,
                    UNIQUE(symbol, timestamp)
                )
            """)
    
    def save_trade(self, trade: Trade):
        """Save trade to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trades 
                (id, symbol, direction, entry_price, exit_price, volume, stop_loss, 
                 take_profit, profit, profit_pips, entry_time, exit_time, status, notes, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.id, trade.symbol, trade.direction.value, trade.entry_price,
                trade.exit_price, trade.volume, trade.stop_loss, trade.take_profit,
                trade.profit, trade.profit_pips, trade.entry_time.isoformat(),
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.status.value, trade.notes, ','.join(trade.tags) if trade.tags else None
            ))
    
    def get_trades(self, symbol: Optional[str] = None, limit: int = 1000) -> List[Trade]:
        """Retrieve trades from database"""
        trades = []
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                trade = Trade(
                    id=row[0], symbol=row[1], direction=SignalType(row[2]),
                    entry_price=row[3], exit_price=row[4], volume=row[5],
                    stop_loss=row[6], take_profit=row[7], profit=row[8],
                    profit_pips=row[9] if len(row) > 9 else 0,
                    entry_time=datetime.fromisoformat(row[10]),
                    exit_time=datetime.fromisoformat(row[11]) if row[11] else None,
                    status=OrderStatus(row[12]), notes=row[13] if len(row) > 13 else "",
                    tags=row[14].split(',') if len(row) > 14 and row[14] else []
                )
                trades.append(trade)
        
        return trades

# ============================================
# TECHNICAL INDICATORS
# ============================================

class TechnicalIndicators:
    """Technical indicators suite"""
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return 50
        
        deltas = []
        for i in range(-period, 0):
            deltas.append(prices[i] - prices[i-1])
        
        gains = sum(d for d in deltas if d > 0)
        losses = sum(-d for d in deltas if d < 0)
        
        if losses == 0:
            return 100
        if gains == 0:
            return 0
        
        rs = gains / losses
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_macd(prices: List[float], fast=12, slow=26, signal=9) -> Tuple[float, float, float]:
        """MACD Indicator"""
        if len(prices) < slow:
            return 0, 0, 0
        
        ema_fast = TechnicalIndicators.calculate_ema(prices, fast)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        signal_line = macd_line * 0.8
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period=20, std_dev=2) -> Tuple[float, float, float]:
        """Bollinger Bands"""
        if len(prices) < period:
            return 0, 0, 0
        
        recent = prices[-period:]
        sma = sum(recent) / period
        variance = sum((p - sma) ** 2 for p in recent) / period
        std = math.sqrt(variance)
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        return upper, sma, lower
    
    @staticmethod
    def calculate_stochastic(prices: List[float], highs: List[float], lows: List[float], k_period=14) -> float:
        """Stochastic Oscillator"""
        if len(prices) < k_period:
            return 50
        
        recent_prices = prices[-k_period:]
        recent_highs = highs[-k_period:]
        recent_lows = lows[-k_period:]
        
        highest = max(recent_highs)
        lowest = min(recent_lows)
        
        if highest == lowest:
            return 50
        
        k = ((prices[-1] - lowest) / (highest - lowest)) * 100
        return k

class AdaptiveMovingAverage:
    """Adaptive Moving Average (AMA)"""
    
    def __init__(self, period_fast: int = 2, period_slow: int = 30):
        self.period_fast = period_fast
        self.period_slow = period_slow
        self.prev_ama = None
    
    def calculate_efficiency_ratio(self, prices: List[float]) -> float:
        if len(prices) < self.period_slow:
            return 0.5
        
        change = abs(prices[-1] - prices[-self.period_slow])
        volatility = 0
        for i in range(-self.period_slow+1, 0):
            volatility += abs(prices[i] - prices[i-1])
        
        if volatility == 0:
            return 0.5
        return change / volatility
    
    def calculate_smoothing_constant(self, er: float) -> float:
        fastest = 2.0 / (self.period_fast + 1)
        slowest = 2.0 / (self.period_slow + 1)
        ssc = er * (fastest - slowest) + slowest
        return max(min(ssc * ssc, 1.0), 0.0)
    
    def calculate(self, prices: List[float]) -> float:
        if len(prices) < self.period_slow:
            return prices[-1] if prices else 0
        
        current = prices[-1]
        er = self.calculate_efficiency_ratio(prices)
        ssc = self.calculate_smoothing_constant(er)
        
        if self.prev_ama is None:
            self.prev_ama = sum(prices[-self.period_slow:]) / self.period_slow
        else:
            self.prev_ama = self.prev_ama + ssc * (current - self.prev_ama)
        
        return self.prev_ama

# ============================================
# TRADING STRATEGY
# ============================================

class MaphahaStrategy:
    """Maphaha Gold trading strategy"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        
        # Indicators
        self.ama_fast = AdaptiveMovingAverage(period_fast=2, period_slow=30)
        self.ama_slow = AdaptiveMovingAverage(period_fast=5, period_slow=20)
        
        # Data storage
        self.price_history = deque(maxlen=Config.HISTORY_BARS)
        self.high_history = deque(maxlen=Config.HISTORY_BARS)
        self.low_history = deque(maxlen=Config.HISTORY_BARS)
        
        self.ama_fast_history = deque(maxlen=100)
        self.ama_slow_history = deque(maxlen=100)
        
        self.last_signal = SignalType.NEUTRAL
        self.is_warmed_up = False
    
    def add_price(self, price: float, high: float = None, low: float = None):
        """Add new price data"""
        self.price_history.append(price)
        self.high_history.append(high or price)
        self.low_history.append(low or price)
        
        if len(self.price_history) >= 50:
            prices_list = list(self.price_history)
            self.ama_fast_history.append(self.ama_fast.calculate(prices_list))
            self.ama_slow_history.append(self.ama_slow.calculate(prices_list))
            
            if len(self.ama_fast_history) >= 20:
                self.is_warmed_up = True
    
    def get_signal(self) -> TradingSignal:
        """Generate trading signal"""
        if not self.is_warmed_up:
            return TradingSignal(SignalType.NEUTRAL, 0, 0, datetime.now(), {}, "Warming up")
        
        prices = list(self.price_history)
        highs = list(self.high_history)
        lows = list(self.low_history)
        
        current_fast = self.ama_fast_history[-1]
        current_slow = self.ama_slow_history[-1]
        prev_fast = self.ama_fast_history[-2]
        prev_slow = self.ama_slow_history[-2]
        
        # Calculate indicators
        rsi = TechnicalIndicators.calculate_rsi(prices, Config.RSI_PERIOD)
        macd, macd_signal, macd_hist = TechnicalIndicators.calculate_macd(prices)
        upper_bb, mid_bb, lower_bb = TechnicalIndicators.calculate_bollinger_bands(
            prices, Config.BB_PERIOD, Config.BB_STD
        )
        stoch = TechnicalIndicators.calculate_stochastic(prices, highs, lows)
        
        current_price = prices[-1]
        
        # Signal scoring
        buy_score = 0
        sell_score = 0
        indicators_used = {}
        
        # AMA Crossover (40 points)
        if current_fast > current_slow and prev_fast <= prev_slow:
            buy_score += 40
            indicators_used['ama'] = 'bullish_crossover'
        elif current_fast < current_slow and prev_fast >= prev_slow:
            sell_score += 40
            indicators_used['ama'] = 'bearish_crossover'
        
        # RSI (20 points)
        if rsi < Config.RSI_OVERSOLD:
            buy_score += 20
            indicators_used['rsi'] = f'oversold ({rsi:.1f})'
        elif rsi > Config.RSI_OVERBOUGHT:
            sell_score += 20
            indicators_used['rsi'] = f'overbought ({rsi:.1f})'
        
        # MACD (15 points)
        if macd > macd_signal and macd_hist > 0:
            buy_score += 15
            indicators_used['macd'] = 'bullish'
        elif macd < macd_signal and macd_hist < 0:
            sell_score += 15
            indicators_used['macd'] = 'bearish'
        
        # Bollinger Bands (15 points)
        if current_price <= lower_bb:
            buy_score += 15
            indicators_used['bb'] = 'lower_band_touch'
        elif current_price >= upper_bb:
            sell_score += 15
            indicators_used['bb'] = 'upper_band_touch'
        
        # Stochastic (10 points)
        if stoch < 20:
            buy_score += 10
            indicators_used['stoch'] = f'oversold ({stoch:.1f})'
        elif stoch > 80:
            sell_score += 10
            indicators_used['stoch'] = f'overbought ({stoch:.1f})'
        
        # Determine signal
        net_score = buy_score - sell_score
        total_score = buy_score + sell_score
        
        if total_score > 0:
            if net_score > 50:
                signal_type = SignalType.STRONG_BUY
                strength = min(100, net_score + 20)
                confidence = (net_score / total_score) * 100
            elif net_score > 20:
                signal_type = SignalType.BUY
                strength = net_score
                confidence = (net_score / total_score) * 100
            elif net_score < -50:
                signal_type = SignalType.STRONG_SELL
                strength = min(100, abs(net_score) + 20)
                confidence = (abs(net_score) / total_score) * 100
            elif net_score < -20:
                signal_type = SignalType.SELL
                strength = abs(net_score)
                confidence = (abs(net_score) / total_score) * 100
            else:
                signal_type = SignalType.NEUTRAL
                strength = 50
                confidence = 50
        else:
            signal_type = SignalType.NEUTRAL
            strength = 50
            confidence = 50
        
        if strength < Config.SIGNAL_THRESHOLD_WEAK:
            signal_type = SignalType.NEUTRAL
        
        reason = f"{', '.join(indicators_used.keys())}" if indicators_used else "No clear signals"
        
        return TradingSignal(
            type=signal_type,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators={
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'bb_upper': upper_bb,
                'bb_middle': mid_bb,
                'bb_lower': lower_bb,
                'stoch': stoch,
                'ama_fast': current_fast,
                'ama_slow': current_slow,
            },
            reason=reason
        )

# ============================================
# RISK MANAGER
# ============================================

class RiskManager:
    """Risk management system"""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.daily_capital = initial_capital
        self.drawdowns = []
        self.trades: List[Trade] = []
        self.daily_trades = 0
        self.daily_loss = 0
        self.last_reset_date = datetime.now().date()
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trades = 0
            self.daily_loss = 0
            self.daily_capital = self.current_capital
            self.last_reset_date = today
    
    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed"""
        self.reset_daily_stats()
        
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            return False, "Daily trade limit reached"
        
        daily_loss_amount = self.daily_capital - self.current_capital
        if daily_loss_amount >= Config.MAX_DAILY_LOSS:
            return False, f"Daily loss limit reached (${daily_loss_amount:.2f})"
        
        if self.get_current_drawdown() > 25:
            return False, f"Maximum drawdown exceeded"
        
        return True, "OK"
    
    def calculate_position_size(self, price: float, stop_loss: float, signal_strength: float) -> float:
        """Calculate position size"""
        risk_amount = self.current_capital * Config.RISK_PER_TRADE
        risk_per_unit = abs(price - stop_loss)
        
        if risk_per_unit <= 0:
            return Config.BASE_LOT_SIZE
        
        size = risk_amount / risk_per_unit
        strength_multiplier = signal_strength / 100
        size *= strength_multiplier
        
        if self.get_win_rate() > 60:
            size *= 1.2
        elif self.get_win_rate() < 40:
            size *= 0.8
        
        size = max(min(size, Config.BASE_LOT_SIZE * 2), Config.BASE_LOT_SIZE * 0.5)
        return size
    
    def calculate_stop_loss(self, direction: SignalType, price: float, atr: float) -> float:
        """Calculate stop loss"""
        stop_distance = atr * 2
        
        if direction in [SignalType.BUY, SignalType.STRONG_BUY]:
            return price - stop_distance
        else:
            return price + stop_distance
    
    def calculate_take_profit(self, direction: SignalType, price: float, stop_loss: float) -> float:
        """Calculate take profit"""
        risk = abs(price - stop_loss)
        reward = risk * 1.5
        
        if direction in [SignalType.BUY, SignalType.STRONG_BUY]:
            return price + reward
        else:
            return price - reward
    
    def update_capital(self, trade: Trade):
        """Update capital after trade"""
        self.current_capital += trade.profit
        self.trades.append(trade)
        self.daily_trades += 1
        
        if trade.profit < 0:
            self.daily_loss += abs(trade.profit)
        
        if self.trades:
            peak = max(self.current_capital, max(t.profit for t in self.trades))
            drawdown = (peak - self.current_capital) / peak * 100 if peak > 0 else 0
            self.drawdowns.append(drawdown)
    
    def get_win_rate(self, lookback: int = 20) -> float:
        """Calculate win rate"""
        if not self.trades:
            return 0
        
        recent = self.trades[-lookback:]
        winning = sum(1 for t in recent if t.profit > 0)
        return (winning / len(recent)) * 100 if recent else 0
    
    def get_current_drawdown(self) -> float:
        """Get current drawdown"""
        return max(self.drawdowns) if self.drawdowns else 0
    
    def get_metrics(self) -> Dict:
        """Get performance metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_profit': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'current_capital': self.current_capital,
                'total_return': 0,
                'profit_factor': 0,
                'daily_trades': self.daily_trades
            }
        
        profits = [t.profit for t in self.trades]
        winning = [p for p in profits if p > 0]
        losing = [p for p in profits if p < 0]
        
        total_profit = sum(profits)
        win_rate = (len(winning) / len(self.trades)) * 100
        
        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 1
        profit_factor = gross_profit / gross_loss
        
        # Sharpe ratio approximation
        if len(profits) > 1:
            mean_profit = sum(profits) / len(profits)
            variance = sum((p - mean_profit) ** 2 for p in profits) / len(profits)
            std_dev = math.sqrt(variance)
            sharpe = (mean_profit / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': total_profit / len(self.trades),
            'max_drawdown': self.get_current_drawdown(),
            'sharpe_ratio': sharpe,
            'current_capital': self.current_capital,
            'total_return': ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            'profit_factor': profit_factor,
            'avg_win': sum(winning) / len(winning) if winning else 0,
            'avg_loss': sum(losing) / len(losing) if losing else 0,
            'daily_trades': self.daily_trades
        }

# ============================================
# TRADE EXECUTOR
# ============================================

class TradeExecutor:
    """Trade execution system"""
    
    def __init__(self, risk_manager: RiskManager, db_manager: DatabaseManager):
        self.risk_manager = risk_manager
        self.db_manager = db_manager
        self.open_trades: List[Trade] = []
        self.trade_counter = 0
    
    def open_trade(self, symbol: str, signal: TradingSignal, price: float, atr: float) -> Optional[Trade]:
        """Open a new trade"""
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            print(f"{Config.COLORS['RED']}Cannot trade: {reason}{Config.COLORS['RESET']}")
            return None
        
        if len(self.open_trades) >= Config.MAX_POSITIONS:
            return None
        
        # Check for duplicate direction
        same_direction = any(
            t.direction in [SignalType.BUY, SignalType.STRONG_BUY] and 
            signal.type in [SignalType.BUY, SignalType.STRONG_BUY]
            for t in self.open_trades
        )
        
        if same_direction:
            return None
        
        # Calculate risk parameters
        stop_loss = self.risk_manager.calculate_stop_loss(signal.type, price, atr)
        take_profit = self.risk_manager.calculate_take_profit(signal.type, price, stop_loss)
        volume = self.risk_manager.calculate_position_size(price, stop_loss, signal.strength)
        
        self.trade_counter += 1
        trade = Trade(
            id=self.trade_counter,
            symbol=symbol,
            direction=signal.type,
            entry_price=price,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_time=datetime.now(),
            tags=['auto']
        )
        
        self.open_trades.append(trade)
        self.db_manager.save_trade(trade)
        
        return trade
    
    def check_trades(self, symbol: str, current_price: float, current_signal: TradingSignal) -> List[Trade]:
        """Check and close trades"""
        closed_trades = []
        
        for trade in self.open_trades[:]:
            # Check SL/TP
            if trade.direction in [SignalType.BUY, SignalType.STRONG_BUY]:
                if current_price <= trade.stop_loss:
                    self.close_trade(trade, current_price, "STOP_LOSS")
                    closed_trades.append(trade)
                elif current_price >= trade.take_profit:
                    self.close_trade(trade, current_price, "TAKE_PROFIT")
                    closed_trades.append(trade)
            else:
                if current_price >= trade.stop_loss:
                    self.close_trade(trade, current_price, "STOP_LOSS")
                    closed_trades.append(trade)
                elif current_price <= trade.take_profit:
                    self.close_trade(trade, current_price, "TAKE_PROFIT")
                    closed_trades.append(trade)
            
            # Check signal reversal for strong signals
            if current_signal.strength >= Config.SIGNAL_THRESHOLD_STRONG:
                if trade.direction in [SignalType.BUY, SignalType.STRONG_BUY] and \
                   current_signal.type in [SignalType.SELL, SignalType.STRONG_SELL]:
                    self.close_trade(trade, current_price, "SIGNAL_REVERSAL")
                    closed_trades.append(trade)
                elif trade.direction in [SignalType.SELL, SignalType.STRONG_SELL] and \
                     current_signal.type in [SignalType.BUY, SignalType.STRONG_BUY]:
                    self.close_trade(trade, current_price, "SIGNAL_REVERSAL")
                    closed_trades.append(trade)
        
        return closed_trades
    
    def close_trade(self, trade: Trade, price: float, reason: str):
        """Close a trade"""
        if trade.direction in [SignalType.BUY, SignalType.STRONG_BUY]:
            trade.profit = (price - trade.entry_price) * trade.volume
            trade.profit_pips = (price - trade.entry_price) * 10000
        else:
            trade.profit = (trade.entry_price - price) * trade.volume
            trade.profit_pips = (trade.entry_price - price) * 10000
        
        trade.exit_price = price
        trade.exit_time = datetime.now()
        trade.status = OrderStatus.CLOSED
        trade.notes = reason
        
        self.risk_manager.update_capital(trade)
        self.db_manager.save_trade(trade)
        self.open_trades.remove(trade)
        
        profit_color = Config.COLORS['GREEN'] if trade.profit > 0 else Config.COLORS['RED']
        profit_sign = '+' if trade.profit > 0 else ''
        
        print(f"\n{profit_color}[CLOSE] {trade.direction.value} {trade.symbol} | "
              f"P&L: {profit_sign}${trade.profit:.2f} ({profit_sign}{trade.profit_pips:.1f} pips) | "
              f"Reason: {reason}{Config.COLORS['RESET']}")

# ============================================
# MARKET SIMULATOR
# ============================================

class MarketSimulator:
    """Market data simulator"""
    
    def __init__(self):
        self.symbols_data = {}
        self.init_symbols()
    
    def init_symbols(self):
        """Initialize symbols"""
        symbols_config = {
            "EURUSD": {"price": 1.0850, "volatility": 0.008, "trend": 0.0002, "spread": 0.0001},
            "GBPUSD": {"price": 1.2650, "volatility": 0.010, "trend": 0.0001, "spread": 0.00012},
            "USDJPY": {"price": 148.50, "volatility": 0.007, "trend": -0.0003, "spread": 0.015},
            "XAUUSD": {"price": 2350.50, "volatility": 0.015, "trend": 0.002, "spread": 0.30},
            "BTCUSD": {"price": 65000, "volatility": 0.040, "trend": 0.005, "spread": 50},
            "ETHUSD": {"price": 3500, "volatility": 0.045, "trend": 0.004, "spread": 5},
            "US30": {"price": 38500, "volatility": 0.012, "trend": 0.001, "spread": 5},
            "US500": {"price": 5100, "volatility": 0.013, "trend": 0.002, "spread": 0.5},
        }
        
        for symbol, config in symbols_config.items():
            self.symbols_data[symbol] = {
                'price': config['price'],
                'volatility': config['volatility'],
                'trend': config['trend'],
                'spread': config['spread'],
                'history': deque(maxlen=Config.HISTORY_BARS),
                'highs': deque(maxlen=Config.HISTORY_BARS),
                'lows': deque(maxlen=Config.HISTORY_BARS)
            }
            
            for _ in range(Config.HISTORY_BARS):
                self.symbols_data[symbol]['history'].append(config['price'])
                self.symbols_data[symbol]['highs'].append(config['price'] * 1.001)
                self.symbols_data[symbol]['lows'].append(config['price'] * 0.999)
    
    def get_price(self, symbol: str) -> float:
        """Get current price"""
        return self.symbols_data[symbol]['price']
    
    def get_ask_price(self, symbol: str) -> float:
        """Get ask price"""
        return self.symbols_data[symbol]['price'] + self.symbols_data[symbol]['spread']
    
    def get_high_low(self, symbol: str) -> Tuple[float, float]:
        """Get high and low"""
        data = self.symbols_data[symbol]
        return data['highs'][-1] if data['highs'] else data['price'], \
               data['lows'][-1] if data['lows'] else data['price']
    
    def get_atr(self, symbol: str) -> float:
        """Get ATR approximation"""
        data = self.symbols_data[symbol]
        return data['volatility'] * data['price']
    
    def update_price(self, symbol: str) -> float:
        """Update price"""
        data = self.symbols_data[symbol]
        old_price = data['price']
        
        trend_effect = data['trend'] * old_price * 0.1
        volatility_effect = random.gauss(0, data['volatility'] * old_price * 0.5)
        
        # Momentum effect
        if len(data['history']) > 10:
            recent_momentum = (data['history'][-1] - data['history'][-10]) / 10
            momentum_effect = recent_momentum * 0.3
        else:
            momentum_effect = 0
        
        change = trend_effect + volatility_effect + momentum_effect
        
        # Occasional spikes
        if random.random() < 0.03:
            spike = random.choice([-1, 1]) * data['volatility'] * old_price * 2
            change += spike
        
        new_price = max(old_price + change, 0.0001)
        data['price'] = new_price
        data['history'].append(new_price)
        
        price_range = new_price * data['volatility'] * 0.5
        data['highs'].append(new_price + abs(random.gauss(0, price_range)))
        data['lows'].append(new_price - abs(random.gauss(0, price_range)))
        
        return new_price

# ============================================
# DISPLAY MANAGER
# ============================================

class DisplayManager:
    """Display management"""
    
    def __init__(self):
        self.colors = Config.COLORS
    
    def clear(self):
        """Clear screen"""
        os.system('clear')
    
    def print_header(self, title: str, subtitle: str = ""):
        """Print header"""
        print(f"{self.colors['CYAN']}{self.colors['BOLD']}")
        print("="*70)
        print(f"{title:^70}")
        if subtitle:
            print(f"{subtitle:^70}")
        print("="*70)
        print(f"{self.colors['RESET']}")
    
    def print_trading_view(self, symbol: str, price: float, signal: TradingSignal,
                          strategy: MaphahaStrategy, executor: TradeExecutor,
                          metrics: Dict, market: MarketSimulator):
        """Print trading view"""
        self.clear()
        
        # Signal color
        if signal.type in [SignalType.STRONG_BUY, SignalType.BUY]:
            signal_color = self.colors['GREEN']
            bg_color = self.colors['BG_GREEN']
        elif signal.type in [SignalType.STRONG_SELL, SignalType.SELL]:
            signal_color = self.colors['RED']
            bg_color = self.colors['BG_RED']
        else:
            signal_color = self.colors['YELLOW']
            bg_color = self.colors['BG_YELLOW']
        
        # Header
        print(f"{bg_color}{self.colors['BOLD']}{'='*70}{self.colors['RESET']}")
        print(f"{bg_color}{self.colors['BOLD']}{f'MAPHAHA GOLD v{VERSION} - {symbol}':^70}{self.colors['RESET']}")
        print(f"{bg_color}{self.colors['BOLD']}{'='*70}{self.colors['RESET']}\n")
        
        # Price Information
        print(f"{self.colors['BOLD']}┌──────────────────────────────────────────────────────────────────────┐{self.colors['RESET']}")
        print(f"│ {self.colors['BOLD']}PRICE INFORMATION{self.colors['RESET']}                                                      │")
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        
        bid_price = price
        ask_price = market.get_ask_price(symbol)
        spread = ask_price - bid_price
        
        print(f"│ Bid: {self.colors['GREEN']}${bid_price:.5f}{self.colors['RESET']}  |  "
              f"Ask: ${ask_price:.5f}  |  Spread: {spread:.5f}  │")
        
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        print(f"│ {self.colors['BOLD']}SIGNAL INFORMATION{self.colors['RESET']}                                                      │")
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        
        print(f"│ Type: {signal_color}{signal.type.value:^12}{self.colors['RESET']}  |  "
              f"Strength: {signal_color}{signal.strength:>5.1f}%{self.colors['RESET']}  |  "
              f"Confidence: {signal_color}{signal.confidence:>5.1f}%{self.colors['RESET']}  │")
        print(f"│ Reason: {signal.reason[:55]:<55} │")
        
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        print(f"│ {self.colors['BOLD']}TECHNICAL INDICATORS{self.colors['RESET']}                                                  │")
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        
        ind = signal.indicators
        print(f"│ RSI: {ind.get('rsi', 50):>6.1f}  |  MACD: {ind.get('macd', 0):>8.4f}  |  "
              f"Stoch: {ind.get('stoch', 50):>6.1f}  │")
        
        if 'bb_lower' in ind:
            print(f"│ BB: {ind.get('bb_lower', 0):>8.4f} / {ind.get('bb_middle', 0):>8.4f} / {ind.get('bb_upper', 0):>8.4f}  │")
        
        if 'ama_fast' in ind and 'ama_slow' in ind:
            ama_dir = '▲' if ind['ama_fast'] > ind['ama_slow'] else '▼'
            print(f"│ AMA Fast: {ind['ama_fast']:.5f}  |  AMA Slow: {ind['ama_slow']:.5f}  |  Direction: {ama_dir}  │")
        
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        print(f"│ {self.colors['BOLD']}PERFORMANCE METRICS{self.colors['RESET']}                                                    │")
        print(f"├──────────────────────────────────────────────────────────────────────┤")
        
        win_rate_color = self.colors['GREEN'] if metrics.get('win_rate', 0) >= 50 else self.colors['RED']
        profit_color = self.colors['GREEN'] if metrics.get('total_profit', 0) >= 0 else self.colors['RED']
        
        print(f"│ Trades: {metrics.get('total_trades', 0):>4}  |  "
              f"Win Rate: {win_rate_color}{metrics.get('win_rate', 0):>5.1f}%{self.colors['RESET']}  |  "
              f"Profit: {profit_color}${metrics.get('total_profit', 0):>8.2f}{self.colors['RESET']}  │")
        print(f"│ Drawdown: {metrics.get('max_drawdown', 0):>5.1f}%  |  "
              f"Sharpe: {metrics.get('sharpe_ratio', 0):>5.2f}  |  "
              f"Return: {profit_color}{metrics.get('total_return', 0):>+6.1f}%{self.colors['RESET']}  │")
        print(f"│ Capital: ${metrics.get('current_capital', 0):>8.2f}  |  "
              f"Open: {len(executor.open_trades)}  |  "
              f"Daily: {metrics.get('daily_trades', 0)}/{Config.MAX_DAILY_TRADES}  │")
        
        # Open Positions
        if executor.open_trades:
            print(f"├──────────────────────────────────────────────────────────────────────┤")
            print(f"│ {self.colors['YELLOW']}OPEN POSITIONS{self.colors['RESET']}                                                      │")
            print(f"├──────────────────────────────────────────────────────────────────────┤")
            
            for trade in executor.open_trades[:3]:  # Show max 3
                trade_color = self.colors['GREEN'] if trade.direction in [SignalType.BUY, SignalType.STRONG_BUY] else self.colors['RED']
                
                if trade.direction in [SignalType.BUY, SignalType.STRONG_BUY]:
                    unrealized = (price - trade.entry_price) * trade.volume
                else:
                    unrealized = (trade.entry_price - price) * trade.volume
                
                unrealized_color = self.colors['GREEN'] if unrealized >= 0 else self.colors['RED']
                
                print(f"│ {trade_color}{trade.direction.value[:4]:<4}{self.colors['RESET']} "
                      f"Entry: ${trade.entry_price:.5f}  SL: ${trade.stop_loss:.5f}  "
                      f"P&L: {unrealized_color}${unrealized:+.2f}{self.colors['RESET']}  │")
        
        print(f"{self.colors['BOLD']}└──────────────────────────────────────────────────────────────────────┘{self.colors['RESET']}")
        
        # Controls
        print(f"\n{self.colors['MAGENTA']}[Ctrl+C] Menu  |  [q] Quit  |  [t] Trades{self.colors['RESET']}")
    
    def print_menu(self):
        """Print main menu"""
        self.clear()
        
        print(f"{self.colors['CYAN']}{self.colors['BOLD']}")
        print("╔" + "="*68 + "╗")
        print(f"║{'MAPHAHA GOLD TRADING SYSTEM v' + VERSION:^68}║")
        print(f"║{'Kali Linux Edition':^68}║")
        print("╠" + "="*68 + "╣")
        print(f"║{'No External Dependencies Required':^68}║")
        print("╚" + "="*68 + "╝")
        print(f"{self.colors['RESET']}")
        
        print(f"\n{self.colors['YELLOW']}{self.colors['BOLD']}TRADING SYMBOLS:{self.colors['RESET']}")
        
        symbols = [
            ("1", "EURUSD", "Euro/US Dollar"),
            ("2", "GBPUSD", "British Pound"),
            ("3", "USDJPY", "USD/Japanese Yen"),
            ("4", "XAUUSD", "Gold"),
            ("5", "BTCUSD", "Bitcoin"),
            ("6", "ETHUSD", "Ethereum"),
            ("7", "US30", "Dow Jones"),
            ("8", "US500", "S&P 500"),
        ]
        
        for i in range(0, len(symbols), 2):
            row = symbols[i:i+2]
            line = ""
            for num, sym, name in row:
                line += f"  {self.colors['GREEN']}{num:>2}{self.colors['RESET']}. {self.colors['CYAN']}{sym:<8}{self.colors['RESET']} {name:<20} "
            print(line)
        
        print(f"\n{self.colors['MAGENTA']}{self.colors['BOLD']}COMMANDS:{self.colors['RESET']}")
        print(f"  {self.colors['GREEN']}[1-8]{self.colors['RESET']}  - Select symbol to trade")
        print(f"  {self.colors['CYAN']}[stats]{self.colors['RESET']}   - View statistics")
        print(f"  {self.colors['RED']}[q]{self.colors['RESET']}        - Quit")
        
        print(f"\n{self.colors['DIM']}Press Ctrl+C to return to menu{self.colors['RESET']}")
    
    def print_trades_view(self, trades: List[Trade]):
        """Display trade history"""
        self.clear()
        self.print_header("TRADE HISTORY", f"Total Trades: {len(trades)}")
        
        if not trades:
            print(f"\n{self.colors['YELLOW']}No trades recorded yet{self.colors['RESET']}")
        else:
            print(f"\n{self.colors['BOLD']}{'ID':<4} {'Symbol':<8} {'Direction':<12} {'Entry':<12} {'Exit':<12} {'Profit':<10}{self.colors['RESET']}")
            print("-"*70)
            
            for trade in trades[:50]:
                profit_color = self.colors['GREEN'] if trade.profit > 0 else self.colors['RED'] if trade.profit < 0 else self.colors['YELLOW']
                profit_sign = '+' if trade.profit > 0 else ''
                
                print(f"{trade.id:<4} {trade.symbol:<8} {trade.direction.value:<12} "
                      f"${trade.entry_price:<11.4f} ${trade.exit_price:<11.4f} "
                      f"{profit_color}${profit_sign}{trade.profit:<9.2f}{self.colors['RESET']}")
        
        print(f"\n{self.colors['YELLOW']}Press Enter to continue...{self.colors['RESET']}")
        input()
    
    def print_analytics(self, metrics: Dict):
        """Display analytics"""
        self.clear()
        self.print_header("TRADING ANALYTICS", "Performance Summary")
        
        print(f"\n{self.colors['BOLD']}{'='*50}{self.colors['RESET']}")
        
        metrics_data = [
            ("Total Trades", metrics.get('total_trades', 0)),
            ("Winning Trades", metrics.get('winning_trades', 0)),
            ("Losing Trades", metrics.get('losing_trades', 0)),
            ("Win Rate", f"{metrics.get('win_rate', 0):.1f}%"),
            ("Total Profit", f"${metrics.get('total_profit', 0):.2f}"),
            ("Average Profit", f"${metrics.get('avg_profit', 0):.2f}"),
            ("Max Drawdown", f"{metrics.get('max_drawdown', 0):.1f}%"),
            ("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.3f}"),
            ("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}"),
            ("Total Return", f"{metrics.get('total_return', 0):.1f}%"),
            ("Current Capital", f"${metrics.get('current_capital', 0):.2f}"),
        ]
        
        for label, value in metrics_data:
            print(f"{label:<20} : {value}")
        
        # Recommendations
        print(f"\n{self.colors['BOLD']}{'='*50}{self.colors['RESET']}")
        print(f"{self.colors['CYAN']}RECOMMENDATIONS{self.colors['RESET']}")
        print(f"{self.colors['BOLD']}{'='*50}{self.colors['RESET']}")
        
        win_rate = metrics.get('win_rate', 0)
        if win_rate > 60:
            print(f"{self.colors['GREEN']}✓ Excellent win rate! Consider increasing position size.{self.colors['RESET']}")
        elif win_rate < 40:
            print(f"{self.colors['RED']}✗ Low win rate. Review strategy or reduce risk.{self.colors['RESET']}")
        
        profit_factor = metrics.get('profit_factor', 0)
        if profit_factor > 1.5:
            print(f"{self.colors['GREEN']}✓ Good profit factor. Strategy is profitable.{self.colors['RESET']}")
        elif profit_factor < 1:
            print(f"{self.colors['RED']}✗ Profit factor below 1. Strategy is losing.{self.colors['RESET']}")
        
        drawdown = metrics.get('max_drawdown', 0)
        if drawdown > 20:
            print(f"{self.colors['YELLOW']}⚠ High drawdown. Consider reducing risk per trade.{self.colors['RESET']}")
        
        print(f"\n{self.colors['YELLOW']}Press Enter to continue...{self.colors['RESET']}")
        input()

# ============================================
# MAIN APPLICATION
# ============================================

class TradingApp:
    """Main trading application"""
    
    def __init__(self):
        self.logger = TradingLogger()
        self.db_manager = DatabaseManager(Config.DB_PATH)
        self.market = MarketSimulator()
        self.display = DisplayManager()
        
        self.strategies: Dict[str, MaphahaStrategy] = {}
        self.executors: Dict[str, TradeExecutor] = {}
        self.running = True
        
        # Initialize symbols
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD", "ETHUSD", "US30", "US500"]
        
        for symbol in symbols:
            self.strategies[symbol] = MaphahaStrategy(symbol)
            risk_manager = RiskManager(Config.INITIAL_CAPITAL)
            self.executors[symbol] = TradeExecutor(risk_manager, self.db_manager)
            
            # Warm up strategies
            for _ in range(Config.HISTORY_BARS):
                price = self.market.get_price(symbol)
                high, low = self.market.get_high_low(symbol)
                self.strategies[symbol].add_price(price, high, low)
        
        print(f"{Config.COLORS['GREEN']}✓ System initialized successfully{Config.COLORS['RESET']}")
        self.logger.info("Trading application initialized")
    
    def run_symbol(self, symbol: str):
        """Run trading for specific symbol"""
        strategy = self.strategies[symbol]
        executor = self.executors[symbol]
        
        print(f"\n{Config.COLORS['GREEN']}Starting {symbol} trading...{Config.COLORS['RESET']}")
        time.sleep(1)
        
        try:
            while self.running:
                # Update market data
                price = self.market.update_price(symbol)
                high, low = self.market.get_high_low(symbol)
                atr = self.market.get_atr(symbol)
                
                # Update strategy
                strategy.add_price(price, high, low)
                signal = strategy.get_signal()
                
                # Check existing trades
                closed = executor.check_trades(symbol, price, signal)
                
                # Open new trade if signal strong
                if signal.type != SignalType.NEUTRAL and signal.strength >= Config.SIGNAL_THRESHOLD_WEAK:
                    executor.open_trade(symbol, signal, price, atr)
                
                # Get metrics
                metrics = executor.risk_manager.get_metrics()
                
                # Display
                self.display.print_trading_view(symbol, price, signal, strategy, executor, metrics, self.market)
                
                # Wait for update
                time.sleep(Config.UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            print(f"\n{Config.COLORS['YELLOW']}Returning to menu...{Config.COLORS['RESET']}")
            time.sleep(1)
    
    def show_statistics(self):
        """Show statistics"""
        all_metrics = {}
        for symbol, executor in self.executors.items():
            metrics = executor.risk_manager.get_metrics()
            if metrics and metrics.get('total_trades', 0) > 0:
                all_metrics[symbol] = metrics
        
        if not all_metrics:
            print(f"\n{Config.COLORS['YELLOW']}No trading data available{Config.COLORS['RESET']}")
            time.sleep(2)
            return
        
        total_trades = sum(m['total_trades'] for m in all_metrics.values())
        total_profit = sum(m['total_profit'] for m in all_metrics.values())
        total_wins = sum(m['winning_trades'] for m in all_metrics.values())
        
        self.display.clear()
        self.display.print_header("GLOBAL STATISTICS", f"Across {len(all_metrics)} Symbols")
        
        print(f"\n{Config.COLORS['BOLD']}AGGREGATE METRICS:{Config.COLORS['RESET']}")
        print(f"  Total Trades: {total_trades}")
        print(f"  Total Wins: {total_wins}")
        print(f"  Overall Win Rate: {(total_wins/total_trades*100):.1f}%" if total_trades > 0 else "  Overall Win Rate: 0%")
        print(f"  Total Profit: ${total_profit:.2f}")
        
        print(f"\n{Config.COLORS['BOLD']}PER SYMBOL BREAKDOWN:{Config.COLORS['RESET']}")
        print(f"{'Symbol':<10} {'Trades':<8} {'Win Rate':<10} {'Profit':<12}")
        print("-"*50)
        
        for symbol, metrics in sorted(all_metrics.items()):
            win_color = Config.COLORS['GREEN'] if metrics['win_rate'] >= 50 else Config.COLORS['RED']
            profit_color = Config.COLORS['GREEN'] if metrics['total_profit'] >= 0 else Config.COLORS['RED']
            
            print(f"{symbol:<10} {metrics['total_trades']:<8} "
                  f"{win_color}{metrics['win_rate']:>6.1f}%{Config.COLORS['RESET']} "
                  f"{profit_color}${metrics['total_profit']:>10.2f}{Config.COLORS['RESET']}")
        
        print(f"\n{Config.COLORS['YELLOW']}Press Enter to continue...{Config.COLORS['RESET']}")
        input()
    
    def show_trades(self):
        """Show trade history"""
        trades = self.db_manager.get_trades(limit=100)
        self.display.print_trades_view(trades)
    
    def run(self):
        """Main loop"""
        def signal_handler(sig, frame):
            self.running = False
            print(f"\n{Config.COLORS['GREEN']}Goodbye! Happy Trading!{Config.COLORS['RESET']}")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        while self.running:
            self.display.print_menu()
            
            try:
                choice = input(f"\n{Config.COLORS['GREEN']}{Config.COLORS['BOLD']}➜ {Config.COLORS['RESET']}").strip().lower()
                
                if choice == 'q':
                    break
                elif choice == 'stats':
                    self.show_statistics()
                elif choice == 't':
                    self.show_trades()
                else:
                    symbol_map = {
                        "1": "EURUSD", "2": "GBPUSD", "3": "USDJPY",
                        "4": "XAUUSD", "5": "BTCUSD", "6": "ETHUSD",
                        "7": "US30", "8": "US500"
                    }
                    
                    if choice in symbol_map:
                        self.run_symbol(symbol_map[choice])
                    elif choice:
                        print(f"\n{Config.COLORS['RED']}Invalid choice! Enter 1-8, 'stats', 't', or 'q'{Config.COLORS['RESET']}")
                        time.sleep(1)
                        
            except Exception as e:
                print(f"\n{Config.COLORS['RED']}Error: {e}{Config.COLORS['RESET']}")
                self.logger.error(f"Error: {e}")
                time.sleep(1)

# ============================================
# ENTRY POINT
# ============================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Maphaha Gold Trading System v3.1')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    
    args = parser.parse_args()
    
    if args.no_color:
        for key in Config.COLORS:
            Config.COLORS[key] = ''
    
    try:
        print(f"{Config.COLORS['CYAN']}{Config.COLORS['BOLD']}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                    MAPHAHA GOLD TRADING SYSTEM                   ║")
        print(f"║                           v{VERSION}                              ║")
        print("║                    Kali Linux Professional Edition               ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"{Config.COLORS['RESET']}")
        
        print(f"{Config.COLORS['YELLOW']}Initializing trading engine...{Config.COLORS['RESET']}")
        time.sleep(1)
        
        app = TradingApp()
        app.run()
        
    except KeyboardInterrupt:
        print(f"\n{Config.COLORS['GREEN']}Goodbye! Happy Trading!{Config.COLORS['RESET']}")
        sys.exit(0)
    except Exception as e:
        print(f"{Config.COLORS['RED']}Fatal Error: {e}{Config.COLORS['RESET']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
