import MetaTrader5 as mt5
import requests
import time
from datetime import datetime, timezone

# Symbol mapping: canonical name -> broker-specific name
SYMBOL_MAP = {
    "EURUSD": "EURUSDm",
    "GBPUSD": "GBPUSDm",
    "USDJPY": "USDJPYm",
    "USDCHF": "USDCHFm",
    "AUDUSD": "AUDUSDm",
    "USDCAD": "USDCADm",
}

BACKEND_URL = "http://127.0.0.1:8000/api/v1/ticks"
POLL_INTERVAL_SECONDS = 0.5

def send_tick(canonical_symbol, broker_symbol, bid, ask):
    payload = {
        "symbol": canonical_symbol,
        "broker_symbol": broker_symbol,
        "bid": bid,
        "ask": ask,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "mt5_exness"
    }
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=5)
        if response.status_code in (201, 202):
            resp_json = response.json()
            if resp_json.get("status") == "stored":
                print(f"[OK] {canonical_symbol} bid={bid} ask={ask}")
            else:
                print(f"[QUARANTINED] {canonical_symbol}: {resp_json.get('reason')}")
        else:
            print(f"[ERROR] Backend returned {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not reach backend: {e}")

def main():
    if not mt5.initialize():
        print("MT5 initialize() failed, error code =", mt5.last_error())
        return

    print("Subscribing to symbols in Market Watch...")
    for canonical, broker_symbol in SYMBOL_MAP.items():
        selected = mt5.symbol_select(broker_symbol, True)
        if selected:
            print(f"[OK] Subscribed: {broker_symbol}")
        else:
            print(f"[ERROR] Could not subscribe: {broker_symbol}, error = {mt5.last_error()}")

    print("Connected to MT5. Starting price feed loop...")
    print(f"Sending data to {BACKEND_URL} every {POLL_INTERVAL_SECONDS}s per symbol")

    last_seen = {symbol: None for symbol in SYMBOL_MAP}

    try:
        while True:
            for canonical, broker_symbol in SYMBOL_MAP.items():
                tick = mt5.symbol_info_tick(broker_symbol)
                if tick is not None:
                    if tick.time_msc != last_seen[canonical]:
                        last_seen[canonical] = tick.time_msc
                        send_tick(canonical, broker_symbol, tick.bid, tick.ask)
                else:
                    print(f"[WARN] No tick data for {broker_symbol}")
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping price feed...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()