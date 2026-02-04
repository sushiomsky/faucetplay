-- ================================================================
-- FAUCET-AWARE ADAPTIVE DICE STRATEGY
-- ================================================================
-- Generated: 2026-01-27 20:33:24
-- Strategy: Start aggressive with high variance, gradually reduce
-- risk as faucets are consumed. Protect capital at the end.
-- ================================================================

-- =========================
-- GLOBAL CONFIGURATION
-- =========================
TOTAL_FAUCETS = 50
faucetsUsed = 5
MINBET = 0.01
FAUCET_VALUE = 0.21

-- =========================
-- STRATEGY PARAMETERS
-- =========================
MAX_BET_PERCENT = 10
SOFT_PROGRESS_EARLY = 1.05
SOFT_PROGRESS_CONTINUED = 1.1
LOSS_STREAK_THRESHOLD = 3
RESET_STREAK_THRESHOLD = 8
DAILY_PROFIT_TARGET = 0
CHANCE_RANDOMIZE = 0.01

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
riskModes = {
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
}

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
