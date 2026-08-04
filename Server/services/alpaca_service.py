from threading import Lock
from time import monotonic

import requests
from config import settings

ALPACA_HEADERS = {
    "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
}

_ASSET_CACHE_TTL_SECONDS = 300
_ASSET_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_ASSET_CACHE_LOCK = Lock()


def _normalize_asset(asset: dict) -> dict:
    """Expose Alpaca's reserved ``class`` field under our API's asset_class name."""
    normalized = dict(asset)
    normalized["asset_class"] = asset.get("asset_class") or asset.get("class", "")
    return normalized


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
    # Alpaca's list-assets endpoint supports status and asset_class filters,
    # but not free-text q or limit parameters. Fetch the filtered catalogue
    # and apply those two controls locally so ticker/name searches are reliable.
    params = {"status": status, "asset_class": asset_class}
    try:
        cache_key = (status, asset_class)
        with _ASSET_CACHE_LOCK:
            cached_at, cached_assets = _ASSET_CACHE.get(cache_key, (0.0, []))
            if cached_assets and monotonic() - cached_at < _ASSET_CACHE_TTL_SECONDS:
                assets = cached_assets
            else:
                resp = requests.get(
                    f"{settings.ALPACA_BASE_URL}/v2/assets",
                    headers=ALPACA_HEADERS,
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                assets = [_normalize_asset(asset) for asset in resp.json()]
                _ASSET_CACHE[cache_key] = (monotonic(), assets)
        if status:
            assets = [asset for asset in assets if asset.get("status") == status]
        if asset_class:
            assets = [asset for asset in assets if asset.get("asset_class") == asset_class]

        needle = query.strip().casefold()
        if needle:
            assets = [
                asset for asset in assets
                if needle in str(asset.get("symbol", "")).casefold()
                or needle in str(asset.get("name", "")).casefold()
            ]
            assets.sort(key=lambda asset: (
                str(asset.get("symbol", "")).casefold() != needle,
                not str(asset.get("symbol", "")).casefold().startswith(needle),
                str(asset.get("symbol", "")).casefold(),
            ))
        return assets[:max(0, limit)]
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
        return _normalize_asset(resp.json())
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


def get_bars(
    symbol: str,
    timeframe: str = "1Day",
    limit: int = 30,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    try:
        params = {"timeframe": timeframe, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = requests.get(
            f"{settings.ALPACA_DATA_URL}/v2/stocks/{symbol}/bars",
            headers=ALPACA_HEADERS,
            params=params,
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


def get_order(order_id: str) -> dict:
    """Fetch one order so asynchronous fills can be reconciled safely."""
    try:
        resp = requests.get(
            f"{settings.ALPACA_BASE_URL}/v2/orders/{order_id}",
            headers=ALPACA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


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
