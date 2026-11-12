#!/usr/bin/env python3
"""Fetch XAUUSD spot from Swissquote-sourced public feed (via XAUAD)."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

XAUAD_URL = "https://xauad.com/gold-price-today.html"
USER_AGENT = "Mozilla/5.0 (compatible; GOLD-FUNDAMENTAL-ANALYSIS/1.0)"


def fetch_swissquote_sourced_spot() -> dict:
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
    um = re.search(r"Updated\s+([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}[^\n<]*)", html)
    if um:
        updated = um.group(1).strip()

    return {
        "source": "Swissquote (via XAUAD)",
        "symbol": "XAUUSD",
        "spot": spot,
        "updated": updated,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "url": XAUAD_URL,
        "note": "Primary spot feed for plans. Confirm fills on your broker.",
    }


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
