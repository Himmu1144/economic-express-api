import json, logging, math, threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
import requests
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from .models import TickerSnapshot

log = logging.getLogger(__name__)
_lock = threading.Lock()
SYMBOLS = {
    "SENSEX": "^BSESN",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDE": "CL=F",
    "USDINR": "INR=X",
}


def fallback():
    data = json.loads((Path(settings.BASE_DIR) / "seed/ticker.json").read_text())
    data["source"] = "static-fallback"
    data["stale"] = True
    return data


def fetch_symbol(pair):
    key, symbol = pair
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}",
        params={"range": "1d", "interval": "5m"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=4,
    )
    r.raise_for_status()
    chart = r.json()["chart"]["result"][0]
    meta = chart["meta"]
    closes = [
        float(x)
        for x in chart["indicators"]["quote"][0]["close"]
        if x is not None and math.isfinite(x)
    ]
    return key, (
        float(meta["regularMarketPrice"]),
        float(meta["chartPreviousClose"]),
        closes[-80:],
    )


def refresh():
    if not _lock.acquire(blocking=False):
        return
    close_old_connections()
    try:
        with ThreadPoolExecutor(max_workers=7) as pool:
            values = dict(pool.map(fetch_symbol, SYMBOLS.items()))
        template = fallback()
        items = []
        for item in template["items"]:
            key = item["key"]
            price, previous, spark = values[key]
            if key in {"GOLD", "SILVER"}:
                scale = (10 if key == "GOLD" else 1000) / 31.1035
                price *= values["USDINR"][0] * scale
                previous *= values["USDINR"][1] * scale
                spark = [v * values["USDINR"][0] * scale for v in spark]
            if not all(math.isfinite(x) and x > 0 for x in [price, previous]):
                raise ValueError("Invalid quote")
            item.update(
                price=round(price, 2),
                change=round(price - previous, 2),
                change_pct=round((price / previous - 1) * 100, 2),
                spark=spark,
            )
            items.append(item)
        TickerSnapshot.objects.update_or_create(
            pk=1,
            defaults={
                "data": {
                    "updated_at": timezone.now().isoformat(),
                    "delayed": True,
                    "items": items,
                    "source": "yahoo",
                    "stale": False,
                }
            },
        )
    except Exception:
        log.warning("Ticker refresh failed; retaining last good values", exc_info=True)
    finally:
        close_old_connections()
        _lock.release()


_last_attempt = None


def get_ticker():
    global _last_attempt
    try:
        row = TickerSnapshot.objects.filter(pk=1).first()
        stale = not row or row.updated_at < timezone.now() - timedelta(minutes=10)
        if (
            stale
            and not settings.TESTING
            and (
                _last_attempt is None
                or _last_attempt < timezone.now() - timedelta(minutes=10)
            )
        ):
            _last_attempt = timezone.now()
            threading.Thread(target=refresh, daemon=True).start()
        data = dict(row.data) if row else fallback()
        if stale:
            data["stale"] = True
        return data
    except Exception:
        log.exception("Ticker storage unavailable")
        return fallback()
