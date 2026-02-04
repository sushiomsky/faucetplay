# FaucetPlay Bot

🎰 **Automated DuckDice Faucet Claiming & Betting Bot**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/yourusername/faucetplay)

> **⚠️ Disclaimer**: This bot is for educational purposes only. Gambling involves financial risk. Use at your own risk.

---

A cross-platform desktop application for automated cryptocurrency faucet claiming, betting, and withdrawal on DuckDice.io.

## ✨ Features

- 🖥️ **Modern GUI** - Easy-to-use graphical interface
- ⏰ **Smart Scheduler** - Set up automated betting sessions
- 💱 **Multi-Currency** - Support for all DuckDice currencies (BTC, ETH, USDC, DOGE, LTC, TRX, SOL, etc.)
- 🎯 **Target-Based Betting** - Set profit targets and let the bot work
- 💰 **Auto Cashout** - Automatically move profits from faucet to main wallet
- 📤 **Auto Withdrawal** - Withdraw to external wallet when target reached
- 🔒 **Secure Storage** - Encrypted credential storage
- 🪟 **Windows Executable** - Standalone .exe for easy installation
- 🌍 **Cross-Platform** - Windows, Linux, macOS

## 🚀 Quick Start

### For Windows Users (Easy Way)

1. Download the latest `FaucetPlayBot.exe` from [Releases](https://github.com/yourusername/faucetplay/releases)
2. Run `FaucetPlayBot.exe`
3. Enter your credentials
4. Set your target amount
5. Click Start!

### For Developers (Python)

```bash
# Clone repository
git clone https://github.com/yourusername/faucetplay.git
cd faucetplay

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python faucetplay_bot.py
```

## 📋 Requirements

- Python 3.8+
- DuckDice.io account
- API Key (get from DuckDice settings)
- Browser Cookie (for faucet claiming)

## 🛠️ Configuration

1. **API Key**: Get from DuckDice.io → Settings → API
2. **Cookie**: Open DuckDice in browser → F12 → Application → Cookies
3. **Withdrawal Address**: Your external wallet address (optional)

## 📖 Usage

### Basic Setup

1. Launch the application
2. Enter your **API Key** and **Cookie**
3. Select your preferred **Currency**
4. Set your **Target Amount**
5. Click **Start Bot**

### Scheduled Betting

1. Go to **Scheduler** tab
2. Set start time and end time
3. Configure daily/weekly schedule
4. Bot will run automatically at scheduled times

### Auto Withdrawal

1. Enable **Auto Withdrawal** in settings
2. Enter your withdrawal address
3. Set minimum withdrawal amount
4. Bot will automatically withdraw when target is reached

## 🏗️ Project Structure

```
faucetplay/
├── faucetplay_bot.py      # Main GUI application
├── core/
│   ├── api.py             # DuckDice API wrapper
│   ├── bot.py             # Bot logic
│   ├── config.py          # Configuration management
│   ├── scheduler.py       # Scheduling system
│   └── withdrawal.py      # Withdrawal handler
├── gui/
│   ├── main_window.py     # Main GUI window
│   ├── settings.py        # Settings dialog
│   └── scheduler_ui.py    # Scheduler interface
├── requirements.txt       # Python dependencies
├── build_exe.py          # PyInstaller build script
└── README.md             # This file
```

## ⚠️ Disclaimer

This bot is for educational purposes only. Use at your own risk. Gambling involves financial risk. Never bet more than you can afford to lose.

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Made with ❤️ for the DuckDice community**
