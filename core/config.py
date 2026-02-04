"""
FaucetPlay Bot - Configuration Management
Handles secure storage and retrieval of settings
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet


class BotConfig:
    """Manages bot configuration and secure credential storage"""
    
    def __init__(self):
        self.config_dir = Path.home() / '.faucetplay_bot'
        self.config_file = self.config_dir / 'config.json'
        self.key_file = self.config_dir / '.key'
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize encryption
        self.cipher = self._get_cipher()
        
        # Default settings
        self.settings = {
            'api_key': '',
            'cookie': '',
            'currency': 'USDC',
            'target_amount': 20.0,
            'house_edge': 0.03,
            'min_bet': 0.001,
            'auto_cashout': False,
            'cashout_threshold': 10.0,
            'auto_withdrawal': False,
            'withdrawal_address': '',
            'withdrawal_amount': 50.0,
            'scheduler_enabled': False,
            'schedules': []
        }
    
    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set file permissions to user-only
            if os.name != 'nt':
                os.chmod(self.key_file, 0o600)
        
        return Fernet(key)
    
    def _encrypt(self, value: str) -> str:
        """Encrypt a string value"""
        if not value:
            return ""
        return self.cipher.encrypt(value.encode()).decode()
    
    def _decrypt(self, value: str) -> str:
        """Decrypt a string value"""
        if not value:
            return ""
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except Exception:
            return ""
    
    def load(self) -> bool:
        """Load configuration from file"""
        if not self.config_file.exists():
            return False
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            # Decrypt sensitive fields
            if 'api_key' in data:
                data['api_key'] = self._decrypt(data['api_key'])
            if 'cookie' in data:
                data['cookie'] = self._decrypt(data['cookie'])
            
            self.settings.update(data)
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False
    
    def save(self) -> bool:
        """Save configuration to file"""
        try:
            data = self.settings.copy()
            
            # Encrypt sensitive fields
            data['api_key'] = self._encrypt(self.settings['api_key'])
            data['cookie'] = self._encrypt(self.settings['cookie'])
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Set file permissions to user-only
            if os.name != 'nt':
                os.chmod(self.config_file, 0o600)
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value"""
        self.settings[key] = value
    
    def get_all(self) -> Dict:
        """Get all settings"""
        return self.settings.copy()
    
    def update(self, settings: Dict) -> None:
        """Update multiple settings"""
        self.settings.update(settings)
