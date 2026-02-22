import requests
import time
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from core.config import BotConfig

# Load all credentials from encrypted config — nothing is hardcoded here
_cfg = BotConfig()
_cfg.load()

API_KEY = _cfg.get('api_key') or ""
CURRENCY = _cfg.get('currency') or "USDC"
TARGET_USD = float(_cfg.get('target_amount') or 20.5)
USDC_PRICE = 1.0
HOUSE_EDGE = float(_cfg.get('house_edge') or 0.03)
MIN_API_CHANCE = 0.01
MIN_BET_USDC = 0.001
ESTIMATED_FEE_USDC = 0.00001

# Browser headers built from config (cookie loaded from encrypted store)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "x-fingerprint": _cfg.get('fingerprint') or "",
    "Content-Type": "application/json",
    "Cookie": _cfg.get('cookie') or "",
}

def get_api_data(endpoint):
    """Generische Funktion für Bot-API Abfragen."""
    url = f"https://duckdice.io/bot-api/{endpoint}?api_key={API_KEY}&symbol={CURRENCY.upper()}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"API HTTP {response.status_code} für {endpoint}")
            return {}
        if not response.text:
            print(f"API leere Response für {endpoint}")
            return {}
        return response.json()
    except Exception as e:
        print(f"API Fehler bei {endpoint}: {e}")
        return {}

def get_current_balance():
    """Holt die Balances direkt über die Bot-API."""
    url = f"https://duckdice.io/api/bot/user-info?api_key={API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"User Info API Fehler: HTTP {response.status_code}")
            return {"main": 0.0, "faucet": 0.0}
        
        data = response.json()
        balances = data.get('balances', [])

        for balance_entry in balances:
            if balance_entry.get('currency') == CURRENCY.upper():
                main = balance_entry.get('main')
                faucet = balance_entry.get('faucet')
                main_f = float(main) if main is not None else 0.0
                faucet_f = float(faucet) if faucet is not None else 0.0
                return {"main": main_f, "faucet": faucet_f}

        return {"main": 0.0, "faucet": 0.0}
    except Exception as e:
        print(f"Balance Fehler: {e}")
        return {"main": 0.0, "faucet": 0.0}

def play_dice(amount, chance, is_high=True):
    """Führt eine Wette über die Bot-API aus."""
    url = f"https://duckdice.io/api/dice/play?api_key={API_KEY}"
    payload = {
        "symbol": CURRENCY.upper(),
        "amount": str(amount),
        "chance": str(chance),
        "isHigh": is_high,
        "faucet": True  # Wir nutzen immer das Faucet-Guthaben für diese Strategie
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Play Dice API Fehler: HTTP {response.status_code} - {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        print(f"Play Dice Fehler: {e}")
        return None

def claim_faucet():
    """Browser-basierter Claim."""
    url = "https://duckdice.io/api/faucet"
    try:
        res = requests.post(url, headers=BROWSER_HEADERS, json={"symbol": CURRENCY.upper(), "results": []})
        return res.status_code == 200
    except:
        return False

def countdown_timer(seconds, message="Warte"):
    """Display a countdown timer."""
    for remaining in range(int(seconds), 0, -1):
        sys.stdout.write(f"\r{message}: {remaining}s   ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write(f"\r{message}: Fertig!     \n")
    sys.stdout.flush()

def run_strategy():
    target_usdc = TARGET_USD / USDC_PRICE
    print(f"--- BOT GESTARTET ---")
    print(f"Ziel: {TARGET_USD}$ (~{target_usdc:.6f} USDC) mit ONE ALL-IN ROLL")
    
    last_claim_time = 0  # Track when we last claimed
    CLAIM_COOLDOWN = 60  # 60 seconds cooldown

    while True:
        balance_info = get_current_balance()
        main_balance = balance_info.get('main', 0.0)
        faucet_balance = balance_info.get('faucet', 0.0)

        # Stop condition: above $20 in any case
        if faucet_balance > 20.0:
            print(f"!!! STOP: Balance über $20 erreicht: {faucet_balance} USDC !!!")
            break
        
        # Ziel erreicht wenn faucet wallet den Betrag enthält
        if faucet_balance >= target_usdc:
            print(f"!!! ZIEL ERREICHT: {faucet_balance} USDC !!!")
            break

        # --- CLAIM LOGIK ---
        # Wenn Faucet Balance zu gering ist für eine Mindestwette
        if faucet_balance < (MIN_BET_USDC + ESTIMATED_FEE_USDC):
            # Check if enough time has passed since last claim
            time_since_claim = time.time() - last_claim_time
            
            if time_since_claim < CLAIM_COOLDOWN:
                wait_time = CLAIM_COOLDOWN - time_since_claim
                print(f"[{time.strftime('%H:%M:%S')}] Faucet Balance zu leer ({faucet_balance:.8f} USDC).")
                countdown_timer(wait_time, "Cooldown")
            
            print(f"[{time.strftime('%H:%M:%S')}] Versuche Claim...")
            if claim_faucet():
                last_claim_time = time.time()  # Record claim time
                print(f"Claim erfolgreich! Cooldown startet jetzt (60s)")
                time.sleep(10)  # Wait for sync
            else:
                print("Claim fehlgeschlagen. Warte 10s und versuche erneut...")
                time.sleep(10)
            continue

        # --- STRATEGIE LOGIK ---
        # All-in Strategie: Berechne die notwendige Chance für 20$ basierend auf aktuellem Balance
        
        # All-in: setze die verfügbare `faucet` Balance als Einsatz
        bet_amount = faucet_balance
        balance_usd = bet_amount * USDC_PRICE

        # Netto-Einsatz nach Gebühren
        net_bet = bet_amount - ESTIMATED_FEE_USDC
        
        # Sicherheitscheck: Sollte durch Claim-Logik oben bereits abgefangen sein, aber zur Sicherheit:
        if net_bet < MIN_BET_USDC:
            print(f"Einsatz immer noch zu klein ({net_bet:.9f} USDC). Warte 10s...")
            time.sleep(10)
            continue

        # Berechne die Gewinnchance basierend auf dem effektiven net_bet
        multiplier_needed = target_usdc / net_bet
        raw_chance = (100.0 * (1.0 - HOUSE_EDGE)) / multiplier_needed if multiplier_needed > 0 else 0.0

        # Runde auf 2 Dezimalstellen (API erwartet Prozent-String wie "77.77")
        # und beachte das minimale/ maximale API-Limit
        MAX_API_CHANCE = 99.0
        if raw_chance <= 0:
            chance_needed = MIN_API_CHANCE
        else:
            # round to 2 decimals
            chance_needed = round(raw_chance, 2)
            if chance_needed < MIN_API_CHANCE:
                chance_needed = MIN_API_CHANCE
            elif chance_needed > MAX_API_CHANCE:
                chance_needed = MAX_API_CHANCE

        print(f"[{time.strftime('%H:%M:%S')}] Faucet Balance: {faucet_balance:.8f} USDC, Main: {main_balance:.8f} USDC (~${balance_usd:.2f})")
        print(f"  → Multiplier benötigt: {multiplier_needed:.2f}x")
        print(f"  → Gewinnchance erforderlich (raw): {raw_chance:.6f}%")
        print(f"  → Gewinnchance verwendet: {chance_needed:.2f}%")
        print(f"  → ALL-IN BET: {bet_amount:.8f} USDC")

        # Wette über SDK
        try:
            # Format chance with two decimals as SDK expects percent string like "77.77"
            chance_str = f"{chance_needed:.2f}"

            # Prepare amount representations for logging
            amount_usdc = round(net_bet, 9)

            print("Sende Wette -> payload:")
            print(f"  symbol: {CURRENCY.upper()}")
            print(f"  amount (USDC): {amount_usdc:.9f}")
            print(f"  chance: {chance_str}%")

            # Call Custom Play Dice Function
            result = play_dice(
                amount=amount_usdc,
                chance=chance_str,
                is_high=True
            )
            
            if not result:
                print("Wette konnte nicht ausgeführt werden.")
                time.sleep(5)
                continue

            # API response structure handling
            data = result.get('data', {})
            new_balance = data.get('balance', {}).get('faucet', 0)
            win = data.get('win', False)
            
            if win:
                print(f"🎉 GEWONNEN! Neue Faucet Balance: {new_balance:.8f} USDC (~${float(new_balance) * USDC_PRICE:.2f})")
                print(f"!!! STOPPING SCRIPT AFTER WIN !!!")
                break
            else:
                print(f"❌ Verloren. Neue Faucet Balance: {new_balance:.8f} USDC (~${float(new_balance) * USDC_PRICE:.2f})")
                
                # Calculate remaining cooldown time after bet
                time_since_claim = time.time() - last_claim_time
                if time_since_claim < CLAIM_COOLDOWN:
                    remaining_cooldown = CLAIM_COOLDOWN - time_since_claim
                    countdown_timer(remaining_cooldown, "Verbleibende Cooldown")
                else:
                    print("Cooldown bereits abgelaufen, mache sofort weiter...")
                    time.sleep(2)  # Short pause to avoid rate limiting
        except Exception as e:
            # Try to surface HTTP response details when available
            err_msg = f"Wett-Fehler: {e}"
            try:
                # many SDK wrappers attach the Response on the exception
                resp = getattr(e, 'response', None)
                if resp is not None:
                    err_msg += f" | HTTP {resp.status_code}: {getattr(resp, 'text', '')}"
            except Exception:
                pass
            print(err_msg)
            time.sleep(5)

if __name__ == "__main__":
    run_strategy()
