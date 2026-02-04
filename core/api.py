"""
FaucetPlay Bot - Core API Module
Handles all DuckDice API interactions
"""

import requests
from typing import Dict, List, Optional


class DuckDiceAPI:
    """DuckDice API wrapper"""
    
    BASE_URL = "https://duckdice.io"
    
    def __init__(self, api_key: str, cookie: str = ""):
        self.api_key = api_key
        self.cookie = cookie
    
    def get_browser_headers(self) -> Dict[str, str]:
        """Build browser headers with cookie"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "x-fingerprint": "f1958fcb6b5c154edf3993cd27f3cbce",
            "Content-Type": "application/json",
            "Cookie": self.cookie
        }
    
    def get_available_currencies(self) -> List[str]:
        """Fetch available currencies from API"""
        url = f"{self.BASE_URL}/api/bot/user-info?api_key={self.api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            data = response.json()
            balances = data.get('balances', [])
            currencies = [b.get('currency') for b in balances if b.get('currency')]
            return sorted(list(set(currencies)))
        except Exception as e:
            print(f"Error fetching currencies: {e}")
            return []
    
    def get_balance(self, currency: str) -> Dict[str, float]:
        """Get current balance for a currency"""
        url = f"{self.BASE_URL}/api/bot/user-info?api_key={self.api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return {"main": 0.0, "faucet": 0.0}
            
            data = response.json()
            balances = data.get('balances', [])
            
            for balance_entry in balances:
                if balance_entry.get('currency') == currency.upper():
                    main = float(balance_entry.get('main', 0))
                    faucet = float(balance_entry.get('faucet', 0))
                    return {"main": main, "faucet": faucet}
            
            return {"main": 0.0, "faucet": 0.0}
        except Exception as e:
            print(f"Error getting balance: {e}")
            return {"main": 0.0, "faucet": 0.0}
    
    def play_dice(self, currency: str, amount: float, chance: float, 
                  is_high: bool = True, use_faucet: bool = True) -> Optional[Dict]:
        """Place a dice bet"""
        url = f"{self.BASE_URL}/api/dice/play?api_key={self.api_key}"
        payload = {
            "symbol": currency.upper(),
            "amount": str(amount),
            "chance": str(chance),
            "isHigh": is_high,
            "faucet": use_faucet
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"Bet API error: {response.status_code} - {response.text}")
                return None
            
            return response.json()
        except Exception as e:
            print(f"Bet error: {e}")
            return None
    
    def claim_faucet(self, currency: str) -> bool:
        """Claim faucet for a currency"""
        url = f"{self.BASE_URL}/api/faucet"
        headers = self.get_browser_headers()
        
        try:
            response = requests.post(
                url, 
                headers=headers, 
                json={"symbol": currency.upper(), "results": []},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Claim error: {e}")
            return False
    
    def cashout(self, currency: str, amount: float) -> bool:
        """Transfer from faucet to main wallet"""
        # TODO: Implement cashout API call
        # This endpoint needs to be verified from DuckDice API docs
        pass
    
    def withdraw(self, currency: str, amount: float, address: str) -> Optional[Dict]:
        """Withdraw to external wallet"""
        # TODO: Implement withdrawal API call
        # This endpoint needs to be verified from DuckDice API docs
        pass
