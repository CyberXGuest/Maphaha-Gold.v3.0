#!/usr/bin/env python3
"""
MAPHAHA GOLD v3.1 - Kali Linux Professional Edition
"""

import os
import sys
import time
import random
import math
import sqlite3
from datetime import datetime
from collections import deque

# Colors for Termux
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

# Trading Symbols
SYMBOLS = {
    "1": {"symbol": "EURUSD", "name": "Euro/USD", "type": "Forex", "volatility": 0.008},
    "2": {"symbol": "GBPUSD", "name": "GBP/USD", "type": "Forex", "volatility": 0.010},
    "3": {"symbol": "USDJPY", "name": "USD/JPY", "type": "Forex", "volatility": 0.007},
    "4": {"symbol": "XAUUSD", "name": "Gold", "type": "Commodity", "volatility": 0.015},
    "5": {"symbol": "BTCUSD", "name": "Bitcoin", "type": "Crypto", "volatility": 0.040},
    "6": {"symbol": "ETHUSD", "name": "Ethereum", "type": "Crypto", "volatility": 0.045},
    "7": {"symbol": "US30", "name": "Dow Jones", "type": "Index", "volatility": 0.012},
    "8": {"symbol": "US500", "name": "S&P 500", "type": "Index", "volatility": 0.013}
}

class SimpleIndicators:
    @staticmethod
    def rsi(prices, period=14):
        if len(prices) < period + 1:
            return 50
        gains = losses = 0
        for i in range(-period, 0):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        if losses == 0:
            return 100
        if gains == 0:
            return 0
        return 100 - (100 / (1 + (gains / losses)))

class TradingBot:
    def __init__(self):
        self.prices = {}
        self.init_prices()
    
    def init_prices(self):
        for key, info in SYMBOLS.items():
            symbol = info["symbol"]
            if symbol == "XAUUSD":
                self.prices[symbol] = 2350.50
            elif symbol == "BTCUSD":
                self.prices[symbol] = 65000
            elif symbol == "ETHUSD":
                self.prices[symbol] = 3500
            else:
                self.prices[symbol] = 1.0850
    
    def update_price(self, symbol):
        old = self.prices[symbol]
        change = random.gauss(0, 0.005 * old)
        new = max(old + change, 0.0001)
        self.prices[symbol] = new
        return new
    
    def get_signal(self, symbol):
        return "NEUTRAL", random.randint(30, 70)

bot = TradingBot()

def clear():
    os.system('clear')

def main():
    while True:
        clear()
        print(f"{CYAN}{BOLD}")
        print("="*50)
        print("  MAPHAHA GOLD v3.1 - TERMUX EDITION")
        print("="*50)
        print(f"{RESET}")
        
        for num, info in SYMBOLS.items():
            print(f"  {GREEN}{num}{RESET}. {info['symbol']} - {info['name']}")
        
        print(f"\n{YELLOW}[1-8] Select | [q] Quit{RESET}")
        
        choice = input(f"\n{GREEN}➜ {RESET}").strip()
        
        if choice.lower() == 'q':
            print(f"\n{GREEN}Goodbye!{RESET}")
            break
        
        if choice in SYMBOLS:
            symbol_info = SYMBOLS[choice]
            print(f"\n{CYAN}Monitoring {symbol_info['symbol']}...{RESET}")
            time.sleep(1)
            
            try:
                while True:
                    price = bot.update_price(symbol_info["symbol"])
                    signal, strength = bot.get_signal(symbol_info["symbol"])
                    
                    clear()
                    print(f"{BOLD}{CYAN}MAPHAHA GOLD v3.1{RESET}")
                    print(f"Symbol: {symbol_info['symbol']}")
                    print(f"Price: ${price:.5f}")
                    print(f"Signal: {signal} ({strength}%)")
                    
                    for i in range(3, 0, -1):
                        print(f"\rUpdate in {i}s...", end="", flush=True)
                        time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n{YELLOW}Returning to menu{RESET}")
                time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{GREEN}Goodbye!{RESET}")
