#!/usr/bin/env python3
"""
Download Chart.js into frontend/resources/vendor so the charts work with no
internet connection.

Run once, on a machine that is online:

    python tools/vendor_chartjs.py

Until you do, the screens fall back to loading Chart.js from the CDN, which
means blank charts whenever the office connection is down.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"
TARGET = Path(__file__).resolve().parents[1] / "frontend" / "resources" / "vendor" / "chart.umd.min.js"

MIN_BYTES = 150_000        # the real file is around 200 KB; anything much
                           # smaller means a truncated or error response


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  failed: {exc}")
        print("\nIf this machine has no internet access, download the file on")
        print("another machine and copy it to:")
        print(f"  {TARGET}")
        return 1

    if len(data) < MIN_BYTES:
        print(f"  refused: got only {len(data):,} bytes, expected at least "
              f"{MIN_BYTES:,}. That is a truncated or error response, not the library.")
        return 2

    if b"Chart.js" not in data[:2000]:
        print("  refused: the downloaded file does not look like Chart.js.")
        return 3

    TARGET.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()[:16]
    print(f"  saved {len(data):,} bytes to {TARGET}")
    print(f"  sha256 (first 16): {digest}")
    print("\nCharts will now work with no internet connection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
