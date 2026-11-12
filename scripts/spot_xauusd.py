#!/usr/bin/env python3
"""Fetch XAUUSD spot from Swissquote public feed (direct), with XAUAD fallback."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

SWISSQUOTE_URL = (
    "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
)
XAUAD_URL = "https://xauad.com/gold-price-today.html"
USER_AGENT = "Mozilla/5.0 (compatible; GOLD-FUNDAMENTAL-ANALYSIS/1.0)"

# Prefer tighter institutional profiles when present.
_PROFILE_PREF = ("elite", "prime", "premium", "standard")


def _mid(bid: float, ask: float) -> float:
    return round((bid + ask) / 2.0, 3)


def fetch_swissquote_direct() -> dict:
    req = urllib.request.Request(
        SWISSQUOTE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8", "replace"))

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Empty Swissquote feed")

    # Prefer SwissquoteLtd platform when available.
    block = None
    for item in payload:
        topo = item.get("topo") or {}
        if topo.get("platform") == "SwissquoteLtd":
            block = item
            break
    if block is None:
        block = payload[0]

    prices = block.get("spreadProfilePrices") or []
    if not prices:
        raise RuntimeError("No Swissquote spread profiles")

    by_name = {p.get("spreadProfile"): p for p in prices if "bid" in p and "ask" in p}
    chosen = None
    for name in _PROFILE_PREF:
        if name in by_name:
            chosen = by_name[name]
            break
    if chosen is None:
        chosen = prices[0]

    bid = float(chosen["bid"])
    ask = float(chosen["ask"])
    spot = _mid(bid, ask)

    ts_ms = block.get("ts")
    updated = None
    if isinstance(ts_ms, (int, float)):
        updated = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).isoformat()

    return {
        "source": "Swissquote direct",
        "symbol": "XAUUSD",
        "spot": spot,
        "bid": bid,
        "ask": ask,
        "spread_profile": chosen.get("spreadProfile"),
        "platform": (block.get("topo") or {}).get("platform"),
        "updated": updated,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "url": SWISSQUOTE_URL,
        "note": "Primary spot feed for plans. Confirm fills on your broker.",
    }


def fetch_swissquote_via_xauad() -> dict:
    req = urllib.request.Request(
        XAUAD_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "replace")

    spot = None
    m = re.search(r"spot at ([0-9]+(?:\.[0-9]+)?) USD", html, re.I)
    if m:
        spot = float(m.group(1))
    else:
        m = re.search(r"Per ounce \(USD\)[^$]*\$([0-9,]+\.[0-9]+)", html)
        if m:
            spot = float(m.group(1).replace(",", ""))

    if spot is None:
        raise RuntimeError("Could not parse Swissquote-sourced spot from XAUAD")

    updated = None
    um = re.search(
        r"Updated\s+([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}[^\n<]*)", html
    )
    if um:
        updated = um.group(1).strip()

    return {
        "source": "Swissquote (via XAUAD fallback)",
        "symbol": "XAUUSD",
        "spot": spot,
        "updated": updated,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "url": XAUAD_URL,
        "note": "Fallback spot feed. Confirm fills on your broker.",
    }


def fetch_swissquote_sourced_spot() -> dict:
    try:
        return fetch_swissquote_direct()
    except Exception as direct_exc:  # noqa: BLE001
        data = fetch_swissquote_via_xauad()
        data["direct_error"] = str(direct_exc)
        return data


def main() -> int:
    try:
        data = fetch_swissquote_sourced_spot()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
