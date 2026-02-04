"""
FaucetPlay Bot - Main Bot Logic
Handles the claim-bet-cashout-withdraw cycle
"""

import time
from typing import Callable, Optional
from datetime import datetime
from .api import DuckDiceAPI
from .config import BotConfig


class FaucetBot:
    """Main bot logic for automated betting"""
    
    def __init__(self, config: BotConfig, log_callback: Optional[Callable] = None):
        self.config = config
        self.log_callback = log_callback or print
        
        # Initialize API
        self.api = DuckDiceAPI(
            api_key=config.get('api_key'),
            cookie=config.get('cookie')
        )
        
        # Bot state
        self.running = False
        self.paused = False
        self.last_claim_time = 0
        self.claim_cooldown = 60
        
        # Statistics
        self.stats = {
            'session_start': None,
            'total_bets': 0,
            'total_wins': 0,
            'total_losses': 0,
            'starting_balance': 0.0,
            'current_balance': 0.0,
            'total_profit': 0.0,
            'total_claimed': 0.0
        }
    
    def log(self, message: str):
        """Log a message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_callback(f"[{timestamp}] {message}")
    
    def start(self):
        """Start the bot"""
        self.running = True
        self.stats['session_start'] = datetime.now()
        self.log("=" * 60)
        self.log("🎰 BOT STARTED")
        self.log("=" * 60)
        self._run_loop()
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        self.log("🛑 Bot stopped")
    
    def pause(self):
        """Pause the bot"""
        self.paused = True
        self.log("⏸ Bot paused")
    
    def resume(self):
        """Resume the bot"""
        self.paused = False
        self.log("▶ Bot resumed")
    
    def _run_loop(self):
        """Main bot loop"""
        currency = self.config.get('currency')
        target_amount = self.config.get('target_amount')
        min_bet = self.config.get('min_bet')
        
        self.log(f"Currency: {currency}")
        self.log(f"Target: ${target_amount:.2f}")
        self.log(f"Strategy: Claim → All-in Roll → Repeat")
        self.log("=" * 60)
        
        # Get starting balance
        balance_info = self.api.get_balance(currency)
        self.stats['starting_balance'] = balance_info['faucet']
        
        while self.running:
            # Handle pause
            while self.paused and self.running:
                time.sleep(0.5)
            
            if not self.running:
                break
            
            # Get current balance
            balance_info = self.api.get_balance(currency)
            faucet_balance = balance_info['faucet']
            main_balance = balance_info['main']
            self.stats['current_balance'] = faucet_balance
            
            # Check for target reached
            if faucet_balance >= target_amount:
                self.log(f"🎉 TARGET REACHED: {faucet_balance:.6f} {currency}")
                
                # Auto cashout if enabled
                if self.config.get('auto_cashout'):
                    self._auto_cashout(currency, faucet_balance)
                
                # Auto withdrawal if enabled
                if self.config.get('auto_withdrawal'):
                    self._auto_withdraw(currency, main_balance)
                
                break
            
            # Check if balance too low - need to claim
            if faucet_balance < min_bet:
                self._claim_faucet(currency)
                continue
            
            # Place bet
            self._place_bet(currency, faucet_balance, target_amount)
        
        self._show_final_stats()
    
    def _claim_faucet(self, currency: str):
        """Claim faucet with cooldown handling"""
        time_since_claim = time.time() - self.last_claim_time
        
        if time_since_claim < self.claim_cooldown:
            wait_time = int(self.claim_cooldown - time_since_claim)
            self.log(f"Cooldown active. Waiting {wait_time}s...")
            
            for remaining in range(wait_time, 0, -1):
                if not self.running:
                    return
                while self.paused and self.running:
                    time.sleep(0.5)
                if remaining % 10 == 0:
                    self.log(f"Cooldown: {remaining}s")
                time.sleep(1)
        
        self.log("Claiming faucet...")
        if self.api.claim_faucet(currency):
            self.last_claim_time = time.time()
            self.log("✅ Claim successful!")
            self.stats['total_claimed'] += 0.21  # Approximate faucet value
            time.sleep(10)  # Wait for balance sync
        else:
            self.log("❌ Claim failed. Retrying...")
            time.sleep(10)
    
    def _place_bet(self, currency: str, balance: float, target: float):
        """Place an all-in bet"""
        house_edge = self.config.get('house_edge')
        
        # Calculate required win chance
        multiplier_needed = target / balance
        raw_chance = (100.0 * (1.0 - house_edge)) / multiplier_needed if multiplier_needed > 0 else 0.0
        chance = max(0.01, min(99.0, round(raw_chance, 2)))
        
        self.log("=" * 50)
        self.log(f"Faucet: {balance:.8f} {currency}")
        self.log(f"Multiplier needed: {multiplier_needed:.2f}x")
        self.log(f"Win chance: {chance:.2f}%")
        self.log(f"ALL-IN BET: {balance:.8f} {currency}")
        self.log("=" * 50)
        
        # Place bet
        result = self.api.play_dice(currency, balance, chance, is_high=True, use_faucet=True)
        
        self.stats['total_bets'] += 1
        
        if result:
            data = result.get('data', {})
            new_balance = float(data.get('balance', {}).get('faucet', 0))
            win = data.get('win', False)
            
            if win:
                self.stats['total_wins'] += 1
                self.log(f"🎉 WON! New balance: {new_balance:.8f} {currency}")
            else:
                self.stats['total_losses'] += 1
                self.log(f"❌ Lost. New balance: {new_balance:.8f} {currency}")
        else:
            self.log("❌ Bet failed")
        
        time.sleep(2)
    
    def _auto_cashout(self, currency: str, amount: float):
        """Automatically cashout to main wallet"""
        threshold = self.config.get('cashout_threshold')
        
        if amount >= threshold:
            self.log(f"💰 Auto-cashout triggered: {amount:.6f} {currency}")
            # TODO: Implement cashout API call
            # self.api.cashout(currency, amount)
            self.log("⚠️ Cashout API not yet implemented")
    
    def _auto_withdraw(self, currency: str, amount: float):
        """Automatically withdraw to external wallet"""
        min_amount = self.config.get('withdrawal_amount')
        address = self.config.get('withdrawal_address')
        
        if amount >= min_amount and address:
            self.log(f"📤 Auto-withdrawal triggered: {amount:.6f} {currency}")
            self.log(f"Address: {address}")
            # TODO: Implement withdrawal API call
            # self.api.withdraw(currency, amount, address)
            self.log("⚠️ Withdrawal API not yet implemented")
    
    def _show_final_stats(self):
        """Show final session statistics"""
        self.log("=" * 60)
        self.log("📊 SESSION STATISTICS")
        self.log("=" * 60)
        self.log(f"Duration: {datetime.now() - self.stats['session_start']}")
        self.log(f"Total bets: {self.stats['total_bets']}")
        self.log(f"Wins: {self.stats['total_wins']}")
        self.log(f"Losses: {self.stats['total_losses']}")
        
        if self.stats['total_bets'] > 0:
            win_rate = (self.stats['total_wins'] / self.stats['total_bets']) * 100
            self.log(f"Win rate: {win_rate:.2f}%")
        
        profit = self.stats['current_balance'] - self.stats['starting_balance']
        self.log(f"Profit/Loss: {profit:+.6f}")
        self.log(f"Total claimed: {self.stats['total_claimed']:.2f}")
        self.log("=" * 60)
    
    def get_stats(self) -> dict:
        """Get current statistics"""
        return self.stats.copy()
