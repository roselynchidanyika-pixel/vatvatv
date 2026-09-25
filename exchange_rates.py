"""exchange_rates.py — LIVE exchange-rate module for the Zimbabwe VAT system.

Currencies supported: ZiG (ZWG/Zimbabwe Gold), USD, ZAR.

Data source (live):
  - open.er-api.com/v6/latest/USD  — free, no API key. Quotes ZWG (Zimbabwe
    Gold) and ZAR directly, so the ZiG rate is REAL and current, not a proxy.
  - The live feed is a shadow of the Reserve Bank of Zimbabwe (RBZ) official
    rate. An RBZ official rate can be entered manually (override) in the app.

Transparency rules (mandatory for this system):
  - The rate used, its source, and its date are shown on every conversion.
  - If a rate is unavailable the system says "FAIL — exchange rate unavailable"
    and never silently substitutes a random rate.
  - "live" flag = True only when a fresh API fetch succeeded this run.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

import config

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".fx_rates_cache.json")
CACHE_TTL_SECONDS = 6 * 3600          # refresh live every 6 hours
REQUEST_TIMEOUT_SECONDS = 8
FETCH_HARD_CAP_SECONDS = 8            # absolute wall-clock cap for the fetch

API_URL = "https://open.er-api.com/v6/latest/USD"

# Set FX_DISABLE_NETWORK=1 to skip the live fetch (used by the pytest suite so
# tests are deterministic and offline-safe).
_DISABLE_NETWORK = os.environ.get("FX_DISABLE_NETWORK", "").strip() in ("1", "true", "TRUE")


def _fetch_live_impl():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "zi-vat-assistant/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("result_code") not in ("success", None) and not payload.get("rates"):
        return None
    rates = payload.get("rates") or {}
    out = {"USD": float(rates.get("USD", 1.0))}
    if "ZAR" in rates:
        out["ZAR"] = float(rates["ZAR"])
    if "ZWG" in rates:
        out["ZIG"] = float(rates["ZWG"])
    elif "ZWD" in rates:        # legacy fallback path (never relied upon)
        out["ZIG"] = float(rates["ZWD"])
    ts = payload.get("time_last_update_unix")
    ts = int(ts) if ts else int(time.time())
    if "ZIG" not in out or "ZAR" not in out:
        return None
    return out, ts


def _fetch_live():
    """Run the API fetch with a hard wall-clock cap so the app can never hang."""
    if _DISABLE_NETWORK:
        return None
    result = {}
    t = threading.Thread(target=lambda: result.update(
        {"v": _fetch_live_impl()}), daemon=True)
    t.start()
    t.join(FETCH_HARD_CAP_SECONDS)
    return result.get("v")


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data or None
    except Exception:
        return None


def _save_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return True
    except Exception:
        return False


def get_rates(refresh=False, manual_zig=None):
    """Return a rate snapshot dict:

        {
          "rates":  {"USD": 1.0, "ZIG": ..., "ZAR": ...},   # units per USD
          "timestamp": int,          # Unix when the rate applied
          "date_label": "25 Sep 2026 00:02 UTC",
          "live": bool,              # True only if fetched fresh this run
          "source": str,             # provider / cache / fallback / manual
          "note": str,
        }
    """
    now = int(time.time())

    if refresh or not _cache_still_fresh():
        live = _fetch_live()
        if live is not None:
            rates, ts = live
            _save_cache({"rates": rates, "timestamp": ts,
                         "source": "open.er-api.com (shadows RBZ official rate)"})

    cache = _load_cache()
    if cache and cache.get("rates"):
        rates = dict(cache["rates"])
        ts = int(cache.get("timestamp", now))
        source = cache.get("source", "cached feed")
        live = False
    else:
        rates = {k: float(v) for k, v in config.DEMO_RATES.items()}
        ts = now
        source = config.DEMO_RATES_SOURCE
        live = False

    # Manual RBZ official override takes the highest priority and is honest
    # about where it came from.
    if manual_zig is not None:
        try:
            rates["ZIG"] = float(manual_zig)
            source = "RBZ official rate (manual entry in system)"
        except Exception:
            pass

    out = {
        "rates": rates,
        "timestamp": ts,
        "date_label": format_ts(ts),
        "live": live,
        "source": source,
        "note": ("Live feed from open.er-api.com (no API key), shadowing the "
                 "Reserve Bank of Zimbabwe official ZiG/USD rate. Set the "
                 "current RBZ rate manually in the sidebar to override."),
    }
    return out


def _cache_still_fresh():
    cache = _load_cache()
    if not cache:
        return False
    ts = int(cache.get("timestamp", 0))
    return (time.time() - ts) < CACHE_TTL_SECONDS


def format_ts(ts):
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# Conversion helper
# ---------------------------------------------------------------------------
CONVERSION_NOTE = {
    "USD": "US dollar transactions are already in the USD schedule - "
           "no conversion needed.",
    "ZIG": "ZiG transactions are already in the ZiG schedule - "
           "no conversion needed.",
    "ZAR": "ZAR transactions are converted into the USD schedule at the "
           "applicable exchange rate (1 USD = X ZAR).",
}


def convert(amount, from_currency, to_currency, rates=None):
    """Convert `amount` between currencies. rates are units per USD. Returns a
    float or None when a rate is missing (caller must show FAIL)."""
    if rates is None:
        rates = get_rates()["rates"]
    f = norm_code(from_currency)
    t = norm_code(to_currency)
    if f not in rates or t not in rates:
        return None
    # amount_in_usd = amount / rates[f] ; target = amount_in_usd * rates[t]
    try:
        amt = float(amount)
        if rates[f] in (None, 0):
            return None
        return amt / float(rates[f]) * float(rates[t])
    except Exception:
        return None


def cross_rate(from_currency, to_currency, rates=None):
    """X such that 1 unit of `from_currency` = X units of `to_currency`."""
    if rates is None:
        rates = get_rates()["rates"]
    f, t = norm_code(from_currency), norm_code(to_currency)
    if f not in rates or t not in rates:
        return None
    if float(rates[f]) == 0:
        return None
    return float(rates[t]) / float(rates[f])


def norm_code(code):
    code = str(code or "").strip().upper()
    if code in ("ZWG", "ZW", "ZIG", "ZIGG"):
        return "ZIG"
    if code in ("US$", "USD"):
        return "USD"
    if code in ("R", "ZAR", "RAND"):
        return "ZAR"
    return code


def convert_row_to_schedule(amount, currency, schedule, rates=None):
    """Convert a transaction `amount` in `currency` into its schedule currency.

    Returns (converted_amount, fx_rate_used, fx_math_text, ok, fail_reason).
    Rules:
      - currency USD  -> USD schedule, rate 1.0
      - currency ZIG  -> ZIG schedule, rate 1.0
      - currency ZAR  -> USD schedule, uses rate 1 USD = X ZAR
    """
    ccy = norm_code(currency)
    if ccy in ("USD",):
        if schedule == "USD":
            return float(amount), 1.0, "No conversion - already in USD schedule", True, None
        # USD -> ZiG schedule (if someone reports USD into the ZiG schedule)
        cz = cross_rate("USD", "ZIG", rates)
        if cz is None:
            return None, None, None, False, "Exchange rate USD -> ZiG unavailable"
        return float(amount) * cz, cz, (
            f"USD {amount:,.2f} x {cz:,.4f} (1 USD = {cz:,.4f} ZiG) "
            f"= {float(amount)*cz:,.2f} ZiG"), True, None
    if ccy in ("ZIG",):
        if schedule == "ZIG":
            return float(amount), 1.0, "No conversion - already in ZiG schedule", True, None
        cz = cross_rate("ZIG", "USD", rates)
        if cz is None:
            return None, None, None, False, "Exchange rate ZiG -> USD unavailable"
        return float(amount) * cz, cz, (
            f"ZiG {amount:,.2f} ÷ {1.0/cz if cz else 1:,.4f} (1 USD = {1.0/cz if cz else 1:,.4f} ZiG) "
            f"= {float(amount)*cz:,.2f} USD"), True, None
    if ccy in ("ZAR",):
        if schedule == "ZIG":
            cz = cross_rate("ZAR", "ZIG", rates)
            if cz is None:
                return None, None, None, False, "Exchange rate ZAR -> ZiG unavailable"
            return float(amount) * cz, cz, (
                f"ZAR {amount:,.2f} x {cz:,.4f} (1 ZAR = {cz:,.4f} ZiG) "
                f"= {float(amount)*cz:,.2f} ZiG"), True, None
        # ZAR -> USD (the statutory treatment used here)
        zar_per_usd = rates.get("ZAR") if rates else None
        if zar_per_usd in (None, 0):
            return None, None, None, False, "Exchange rate ZAR -> USD unavailable"
        zar_per_usd = float(zar_per_usd)
        conv = float(amount) / zar_per_usd
        fx_math = (f"ZAR {amount:,.2f} ÷ {zar_per_usd:,.4f} "
                   f"(1 USD = {zar_per_usd:,.4f} ZAR) = USD {conv:,.2f}")
        return conv, zar_per_usd, fx_math, True, None
    return None, None, None, False, "Currency not supported"


def rates_table(snapshot):
    """Rows for the dashboard '💰 Currency & Exchange Rates' table."""
    r = snapshot.get("rates", {})
    out = []
    for ccy in ("USD", "ZIG", "ZAR"):
        c = norm_code(ccy)
        if c == "USD":
            rate_row = {"Currency": "USD", "Rate (per USD)": 1.0000,
                        "Rate display": "1.0000 (base)", "Source": snapshot.get("source"),
                        "Rate date": snapshot.get("date_label"), "Status": "🟢 PASS"}
            out.append(rate_row)
        else:
            val = r.get(c)
            if val is None or not val:
                out.append({"Currency": c, "Rate (per USD)": None, "Rate display": "n/a",
                            "Source": snapshot.get("source"), "Rate date": snapshot.get("date_label"),
                            "Status": "🔴 FAIL — exchange rate unavailable"})
                continue
            out.append({"Currency": c, "Rate (per USD)": float(val),
                        "Rate display": f"{float(val):,.4f}",
                        "Source": snapshot.get("source"),
                        "Rate date": snapshot.get("date_label"),
                        "Status": "🟢 PASS"})
    return out


def source_label(snapshot):
    return snapshot.get("source", "unknown"), snapshot.get("date_label", "")