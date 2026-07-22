import requests
from config import settings

ALPACA_HEADERS = {
    "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
}


# ──────────────────────────────────────────────
# Account
# ──────────────────────────────────────────────

def get_account() -> dict:
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/account",
            headers=ALPACA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


# ──────────────────────────────────────────────
# Assets / Market Data
# ──────────────────────────────────────────────

def search_assets(query: str = "", asset_class: str = "us_equity", status: str = "active", limit: int = 50) -> list[dict]:
    params = {
        "status": status,
        "asset_class": asset_class,
        "limit": limit,
    }
    if query:
        params["q"] = query
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/assets",
            headers=ALPACA_HEADERS,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_asset(symbol: str) -> dict:
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/assets/{symbol}",
            headers=ALPACA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def get_snapshots(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    try:
        symbols_csv = ",".join(symbols)
        resp = requests.get(
            f"{settings.ALPACA_DATA_URL}/v2/stocks/snapshots",
            headers=ALPACA_HEADERS,
            params={"symbols": symbols_csv},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def get_bars(symbol: str, timeframe: str = "1Day", limit: int = 30) -> list[dict]:
    try:
        resp = requests.get(
            f"{settings.ALPACA_DATA_URL}/v2/stocks/{symbol}/bars",
            headers=ALPACA_HEADERS,
            params={"timeframe": timeframe, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("bars") or []
    except Exception as e:
        print(f"[ALPACA] get_bars failed for {symbol}: {e}")
        return []


def get_crypto_snapshots(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    try:
        symbols_csv = ",".join(f"{s}/USD" for s in symbols)
        resp = requests.get(
            f"{settings.ALPACA_DATA_URL}/v1beta3/crypto/snapshots",
            headers=ALPACA_HEADERS,
            params={"symbols": symbols_csv},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("snapshots", {})
    except Exception:
        return []


# ──────────────────────────────────────────────
# Trading
# ──────────────────────────────────────────────

def place_order(symbol: str, notional: float, side: str = "buy", order_type: str = "market", time_in_force: str = "day") -> dict:
    payload = {
        "symbol": symbol,
        "notional": str(notional),
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }
    try:
        resp = requests.post(
            f"{settings.ALPACA_BASE_URL}/v2/orders",
            headers=ALPACA_HEADERS,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        error_body = e.response.json() if e.response else {}
        return {"error": True, "message": error_body.get("message", str(e)), "code": error_body.get("code", 0)}
    except Exception as e:
        return {"error": True, "message": str(e), "code": 0}


def get_orders(status: str = "all", limit: int = 50) -> list[dict]:
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/orders",
            headers=ALPACA_HEADERS,
            params={"status": status, "limit": limit, "direction": "desc"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_positions() -> list[dict]:
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/positions",
            headers=ALPACA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ALPACA] get_positions failed: {e}")
        return []


def get_position(symbol: str) -> dict:
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/positions/{symbol}",
            headers=ALPACA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


# ──────────────────────────────────────────────
# Strategy Config
# ──────────────────────────────────────────────

STRATEGY_QUERIES = {
    "aggressive": ["TQQQ", "SOXL", "ARKK", "UPRO", "TNA", "UDOW", "SSO", "QLD", "FNGU", "BULZ"],
    "growth": ["QQQ", "VGT", "SCHG", "VUG", "IWF", "ARKG", "SMH", "XLY", "XLK", "IBUY"],
    "balanced": ["VTI", "VOO", "SPY", "IVV", "SCHX", "VT", "BND", "AGG", "VTEB", "MUB"],
    "conservative": ["BND", "AGG", "TLT", "VGSH", "SHY", "IEF", "LQD", "VCSH", "SCHR", "GOVT"],
    "income": ["VYM", "SCHD", "HDV", "SPHD", "DIV", "SDY", "DVY", "FDL", "DHS", "PFF"],
}

STRATEGY_META = {
    "aggressive": {
        "label": "Aggressive",
        "description": "High-risk, high-reward growth stocks and leveraged ETFs",
        "risk_level": "high",
    },
    "growth": {
        "label": "Growth",
        "description": "Capital appreciation through tech and growth equities",
        "risk_level": "medium-high",
    },
    "balanced": {
        "label": "Balanced",
        "description": "Diversified mix of stocks and bonds for steady returns",
        "risk_level": "medium",
    },
    "conservative": {
        "label": "Conservative",
        "description": "Capital preservation with bonds and low-volatility assets",
        "risk_level": "low",
    },
    "income": {
        "label": "Income",
        "description": "Dividend-focused equities and income-generating assets",
        "risk_level": "low-medium",
    },
}
