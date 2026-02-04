#!/usr/bin/env python3
"""
DiceBot Faucet Strategy Configurator
Interactive setup for faucet-aware adaptive dice strategy
"""

import os
import sys
from datetime import datetime

def print_header():
    """Print welcome header"""
    print("\n" + "="*60)
    print("🎰 FAUCET-AWARE ADAPTIVE DICE STRATEGY CONFIGURATOR")
    print("="*60)
    print("This tool will help you configure your DiceBot strategy")
    print("with personalized parameters.\n")

def get_float_input(prompt, default, min_val=None, max_val=None):
    """Get float input with validation"""
    while True:
        try:
            user_input = input(f"{prompt} (default: {default}): ").strip()
            if not user_input:
                return default
            
            value = float(user_input)
            
            if min_val is not None and value < min_val:
                print(f"❌ Value must be at least {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"❌ Value must be at most {max_val}")
                continue
            
            return value
        except ValueError:
            print("❌ Please enter a valid number")

def get_int_input(prompt, default, min_val=None, max_val=None):
    """Get integer input with validation"""
    while True:
        try:
            user_input = input(f"{prompt} (default: {default}): ").strip()
            if not user_input:
                return default
            
            value = int(user_input)
            
            if min_val is not None and value < min_val:
                print(f"❌ Value must be at least {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"❌ Value must be at most {max_val}")
                continue
            
            return value
        except ValueError:
            print("❌ Please enter a valid integer")

def get_yes_no(prompt, default=True):
    """Get yes/no input"""
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} ({default_str}): ").strip().lower()
        if not response:
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("❌ Please enter 'y' or 'n'")

def configure_basic_params():
    """Configure basic strategy parameters"""
    print("\n📋 BASIC PARAMETERS")
    print("-" * 60)
    
    params = {}
    
    params['TOTAL_FAUCETS'] = get_int_input(
        "Total faucets available per 24h",
        default=50,
        min_val=1,
        max_val=200
    )
    
    params['FAUCET_VALUE'] = get_float_input(
        "Value per faucet (USD)",
        default=0.21,
        min_val=0.01
    )
    
    params['MINBET'] = get_float_input(
        "Minimum bet amount",
        default=0.01,
        min_val=0.001
    )
    
    params['faucetsUsed'] = get_int_input(
        "Faucets already claimed today",
        default=0,
        min_val=0,
        max_val=params['TOTAL_FAUCETS']
    )
    
    return params

def configure_risk_modes():
    """Configure risk mode parameters"""
    print("\n⚡ RISK MODE CONFIGURATION")
    print("-" * 60)
    
    if not get_yes_no("Customize risk modes? (Advanced)", default=False):
        return None  # Use defaults
    
    print("\n🎯 ULTRA HUNT MODE (Most faucets left)")
    ultra = {}
    ultra['minFaucets'] = get_int_input("Min faucets for this mode", 40, 0, 50)
    ultra['baseChance'] = get_float_input("Base win chance (%)", 0.15, 0.01, 100)
    ultra['targetMultiplier'] = get_int_input("Target multiplier", 750, 2, 10000)
    ultra['baseBetPercent'] = get_float_input("Base bet (% of balance)", 0.5, 0.1, 10)
    
    print("\n🔥 AGGRESSIVE MODE")
    aggressive = {}
    aggressive['minFaucets'] = get_int_input("Min faucets for this mode", 25, 0, 50)
    aggressive['baseChance'] = get_float_input("Base win chance (%)", 0.5, 0.01, 100)
    aggressive['targetMultiplier'] = get_int_input("Target multiplier", 200, 2, 10000)
    aggressive['baseBetPercent'] = get_float_input("Base bet (% of balance)", 1.0, 0.1, 10)
    
    print("\n⚖️  BALANCED MODE")
    balanced = {}
    balanced['minFaucets'] = get_int_input("Min faucets for this mode", 10, 0, 50)
    balanced['baseChance'] = get_float_input("Base win chance (%)", 1.5, 0.01, 100)
    balanced['targetMultiplier'] = get_int_input("Target multiplier", 75, 2, 10000)
    balanced['baseBetPercent'] = get_float_input("Base bet (% of balance)", 1.5, 0.1, 10)
    
    print("\n🛡️  SAFE MODE (Few faucets left)")
    safe = {}
    safe['minFaucets'] = get_int_input("Min faucets for this mode", 0, 0, 50)
    safe['baseChance'] = get_float_input("Base win chance (%)", 7.5, 0.01, 100)
    safe['targetMultiplier'] = get_int_input("Target multiplier", 15, 2, 1000)
    safe['baseBetPercent'] = get_float_input("Base bet (% of balance)", 2.0, 0.1, 10)
    
    return {
        'ultra': ultra,
        'aggressive': aggressive,
        'balanced': balanced,
        'safe': safe
    }

def configure_advanced_params():
    """Configure advanced parameters"""
    print("\n🔧 ADVANCED SETTINGS")
    print("-" * 60)
    
    params = {}
    
    params['MAX_BET_PERCENT'] = get_float_input(
        "Max bet cap (% of balance)",
        default=10,
        min_val=1,
        max_val=50
    )
    
    params['SOFT_PROGRESS_EARLY'] = get_float_input(
        "Early loss progression multiplier",
        default=1.05,
        min_val=1.0,
        max_val=2.0
    )
    
    params['SOFT_PROGRESS_CONTINUED'] = get_float_input(
        "Continued loss progression multiplier",
        default=1.10,
        min_val=1.0,
        max_val=2.0
    )
    
    params['LOSS_STREAK_THRESHOLD'] = get_int_input(
        "Loss streak threshold for higher progression",
        default=3,
        min_val=1,
        max_val=20
    )
    
    params['RESET_STREAK_THRESHOLD'] = get_int_input(
        "Deep loss streak reset threshold",
        default=8,
        min_val=3,
        max_val=50
    )
    
    if get_yes_no("Enable daily profit target?", default=False):
        params['DAILY_PROFIT_TARGET'] = get_float_input(
            "Daily profit target (USD)",
            default=10.0,
            min_val=0.1
        )
    else:
        params['DAILY_PROFIT_TARGET'] = 0
    
    params['CHANCE_RANDOMIZE'] = get_float_input(
        "Chance randomization range (stealth)",
        default=0.01,
        min_val=0.0,
        max_val=1.0
    )
    
    return params

def generate_lua_script(basic_params, risk_modes, advanced_params):
    """Generate the Lua script with configured parameters"""
    
    # Build risk modes section
    if risk_modes:
        risk_modes_lua = f"""riskModes = {{
    ultraHunt = {{
        name = "Ultra Hunt",
        minFaucets = {risk_modes['ultra']['minFaucets']},
        maxFaucets = 50,
        baseChance = {risk_modes['ultra']['baseChance']},
        targetMultiplier = {risk_modes['ultra']['targetMultiplier']},
        baseBetPercent = {risk_modes['ultra']['baseBetPercent']}
    }},
    aggressive = {{
        name = "Aggressive",
        minFaucets = {risk_modes['aggressive']['minFaucets']},
        maxFaucets = {risk_modes['ultra']['minFaucets'] - 1},
        baseChance = {risk_modes['aggressive']['baseChance']},
        targetMultiplier = {risk_modes['aggressive']['targetMultiplier']},
        baseBetPercent = {risk_modes['aggressive']['baseBetPercent']}
    }},
    balanced = {{
        name = "Balanced",
        minFaucets = {risk_modes['balanced']['minFaucets']},
        maxFaucets = {risk_modes['aggressive']['minFaucets'] - 1},
        baseChance = {risk_modes['balanced']['baseChance']},
        targetMultiplier = {risk_modes['balanced']['targetMultiplier']},
        baseBetPercent = {risk_modes['balanced']['baseBetPercent']}
    }},
    safeMode = {{
        name = "Safe Mode",
        minFaucets = {risk_modes['safe']['minFaucets']},
        maxFaucets = {risk_modes['balanced']['minFaucets'] - 1},
        baseChance = {risk_modes['safe']['baseChance']},
        targetMultiplier = {risk_modes['safe']['targetMultiplier']},
        baseBetPercent = {risk_modes['safe']['baseBetPercent']}
    }}
}}"""
    else:
        risk_modes_lua = """riskModes = {
    ultraHunt = {
        name = "Ultra Hunt",
        minFaucets = 40,
        maxFaucets = 50,
        baseChance = 0.15,
        targetMultiplier = 750,
        baseBetPercent = 0.5
    },
    aggressive = {
        name = "Aggressive",
        minFaucets = 25,
        maxFaucets = 39,
        baseChance = 0.5,
        targetMultiplier = 200,
        baseBetPercent = 1.0
    },
    balanced = {
        name = "Balanced",
        minFaucets = 10,
        maxFaucets = 24,
        baseChance = 1.5,
        targetMultiplier = 75,
        baseBetPercent = 1.5
    },
    safeMode = {
        name = "Safe Mode",
        minFaucets = 0,
        maxFaucets = 9,
        baseChance = 7.5,
        targetMultiplier = 15,
        baseBetPercent = 2.0
    }
}"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lua_script = f"""-- ================================================================
-- FAUCET-AWARE ADAPTIVE DICE STRATEGY
-- ================================================================
-- Generated: {timestamp}
-- Strategy: Start aggressive with high variance, gradually reduce
-- risk as faucets are consumed. Protect capital at the end.
-- ================================================================

-- =========================
-- GLOBAL CONFIGURATION
-- =========================
TOTAL_FAUCETS = {basic_params['TOTAL_FAUCETS']}
faucetsUsed = {basic_params['faucetsUsed']}
MINBET = {basic_params['MINBET']}
FAUCET_VALUE = {basic_params['FAUCET_VALUE']}

-- =========================
-- STRATEGY PARAMETERS
-- =========================
MAX_BET_PERCENT = {advanced_params['MAX_BET_PERCENT']}
SOFT_PROGRESS_EARLY = {advanced_params['SOFT_PROGRESS_EARLY']}
SOFT_PROGRESS_CONTINUED = {advanced_params['SOFT_PROGRESS_CONTINUED']}
LOSS_STREAK_THRESHOLD = {advanced_params['LOSS_STREAK_THRESHOLD']}
RESET_STREAK_THRESHOLD = {advanced_params['RESET_STREAK_THRESHOLD']}
DAILY_PROFIT_TARGET = {advanced_params['DAILY_PROFIT_TARGET']}
CHANCE_RANDOMIZE = {advanced_params['CHANCE_RANDOMIZE']}

-- =========================
-- STATE VARIABLES
-- =========================
lossStreak = 0
startBalance = balance
sessionBets = 0
sessionWins = 0
sessionLosses = 0
totalProfit = 0

-- =========================
-- RISK MODE DEFINITIONS
-- =========================
{risk_modes_lua}

currentMode = nil

-- =========================
-- HELPER FUNCTIONS
-- =========================

function getFaucetsLeft()
    return TOTAL_FAUCETS - faucetsUsed
end

function faucetClaimed()
    faucetsUsed = faucetsUsed + 1
    print(string.format("🎁 Faucet claimed! Total used: %d/%d", faucetsUsed, TOTAL_FAUCETS))
end

function getRiskMode(faucetsLeft)
    if faucetsLeft >= riskModes.ultraHunt.minFaucets then
        return riskModes.ultraHunt
    elseif faucetsLeft >= riskModes.aggressive.minFaucets then
        return riskModes.aggressive
    elseif faucetsLeft >= riskModes.balanced.minFaucets then
        return riskModes.balanced
    else
        return riskModes.safeMode
    end
end

function randomizeChance(baseChance)
    local variance = (math.random() * 2 - 1) * CHANCE_RANDOMIZE
    return math.max(0.01, baseChance + variance)
end

function getBaseBet(mode)
    local baseBet = (balance * mode.baseBetPercent) / 100
    return math.max(MINBET, baseBet)
end

function applySafetyCap(betAmount)
    local maxBet = (balance * MAX_BET_PERCENT) / 100
    return math.min(betAmount, maxBet)
end

function calculateNextBet(currentBet, streak)
    if streak == 0 then
        return getBaseBet(currentMode)
    elseif streak >= RESET_STREAK_THRESHOLD then
        print("⚠️  Deep loss streak detected - resetting to base bet")
        return getBaseBet(currentMode)
    elseif streak >= LOSS_STREAK_THRESHOLD then
        return currentBet * SOFT_PROGRESS_CONTINUED
    else
        return currentBet * SOFT_PROGRESS_EARLY
    end
end

function emergencyProtection()
    local faucetsLeft = getFaucetsLeft()
    local remainingFaucetValue = faucetsLeft * FAUCET_VALUE
    
    if balance < (remainingFaucetValue * 0.5) then
        print("🚨 EMERGENCY: Switching to ultra-safe mode")
        chance = 25
        return true
    end
    return false
end

function printStats()
    local faucetsLeft = getFaucetsLeft()
    local profit = balance - startBalance
    local winRate = sessionBets > 0 and (sessionWins / sessionBets * 100) or 0
    
    print("========================================")
    print(string.format("Mode: %s | Faucets Left: %d/%d", currentMode.name, faucetsLeft, TOTAL_FAUCETS))
    print(string.format("Balance: %.4f | Profit: %.4f", balance, profit))
    print(string.format("Bets: %d | Wins: %d | Losses: %d", sessionBets, sessionWins, sessionLosses))
    print(string.format("Win Rate: %.2f%% | Loss Streak: %d", winRate, lossStreak))
    print("========================================")
end

-- =========================
-- INITIALIZATION
-- =========================
function initStrategy()
    local faucetsLeft = getFaucetsLeft()
    currentMode = getRiskMode(faucetsLeft)
    
    nextbet = getBaseBet(currentMode)
    nextbet = applySafetyCap(nextbet)
    
    chance = randomizeChance(currentMode.baseChance)
    
    print("🎰 Faucet-Aware Adaptive Strategy Initialized")
    print(string.format("Starting with %s mode", currentMode.name))
    printStats()
end

-- =========================
-- MAIN BETTING LOGIC (dobet)
-- =========================
function dobet()
    sessionBets = sessionBets + 1
    
    if DAILY_PROFIT_TARGET > 0 and (balance - startBalance) >= DAILY_PROFIT_TARGET then
        print(string.format("✅ Daily profit target reached: %.4f", balance - startBalance))
        stop()
        return
    end
    
    if win then
        sessionWins = sessionWins + 1
        lossStreak = 0
        
        local faucetsLeft = getFaucetsLeft()
        local newMode = getRiskMode(faucetsLeft)
        
        if newMode.name ~= currentMode.name then
            print(string.format("📊 Mode transition: %s → %s", currentMode.name, newMode.name))
            currentMode = newMode
        end
        
        nextbet = getBaseBet(currentMode)
        
    else
        sessionLosses = sessionLosses + 1
        lossStreak = lossStreak + 1
        
        nextbet = calculateNextBet(previousbet, lossStreak)
    end
    
    nextbet = applySafetyCap(nextbet)
    nextbet = math.max(MINBET, nextbet)
    
    if not emergencyProtection() then
        chance = randomizeChance(currentMode.baseChance)
    end
    
    if sessionBets % 50 == 0 then
        printStats()
    end
    
    if balance < (MINBET * 10) then
        print("⛔ Balance too low - stopping")
        stop()
    end
end

-- =========================
-- STRATEGY START
-- =========================
initStrategy()
"""
    
    return lua_script

def save_config(basic_params, risk_modes, advanced_params):
    """Save configuration to file for future reference"""
    import json
    
    config = {
        'timestamp': datetime.now().isoformat(),
        'basic': basic_params,
        'risk_modes': risk_modes,
        'advanced': advanced_params
    }
    
    config_file = 'strategy_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Configuration saved to: {config_file}")

def main():
    """Main configuration flow"""
    print_header()
    
    # Basic parameters
    basic_params = configure_basic_params()
    
    # Advanced parameters
    if get_yes_no("\nConfigure advanced parameters?", default=False):
        advanced_params = configure_advanced_params()
    else:
        # Use defaults
        advanced_params = {
            'MAX_BET_PERCENT': 10,
            'SOFT_PROGRESS_EARLY': 1.05,
            'SOFT_PROGRESS_CONTINUED': 1.10,
            'LOSS_STREAK_THRESHOLD': 3,
            'RESET_STREAK_THRESHOLD': 8,
            'DAILY_PROFIT_TARGET': 0,
            'CHANCE_RANDOMIZE': 0.01
        }
    
    # Risk modes
    risk_modes = configure_risk_modes()
    
    # Generate script
    print("\n⚙️  Generating Lua script...")
    lua_script = generate_lua_script(basic_params, risk_modes, advanced_params)
    
    # Save script
    output_file = 'faucet_adaptive_strategy.lua'
    with open(output_file, 'w') as f:
        f.write(lua_script)
    
    # Save config
    save_config(basic_params, risk_modes, advanced_params)
    
    # Summary
    print("\n" + "="*60)
    print("✅ CONFIGURATION COMPLETE!")
    print("="*60)
    print(f"📄 Lua script generated: {output_file}")
    print(f"📋 Total faucets: {basic_params['TOTAL_FAUCETS']}")
    print(f"🎯 Faucets used: {basic_params['faucetsUsed']}")
    print(f"💰 Faucet value: ${basic_params['FAUCET_VALUE']}")
    print(f"🎲 Min bet: {basic_params['MINBET']}")
    if advanced_params['DAILY_PROFIT_TARGET'] > 0:
        print(f"🎯 Daily profit target: ${advanced_params['DAILY_PROFIT_TARGET']}")
    print("\n📖 NEXT STEPS:")
    print("1. Open DiceBot")
    print("2. Go to Programmer Mode")
    print(f"3. Load the file: {output_file}")
    print("4. Start betting!")
    print("5. Call faucetClaimed() in the console after each faucet claim")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        # Always run interactive configuration on startup
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
