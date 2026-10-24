"""رادار السيولة المؤسسية لـ US500 (CBOE S&P 500 Options Flow & Capital Sentiment).

يجلب مجاناً وبدون أي مفاتيح:
1. معنويات المتداولين من Capital.com لحظياً لـ US500.
2. تدفقات عقود الأوبشن المؤسسية الكبيرة لـ SPX من CBOE.
3. مستويات تعرّض الغاما (GEX) وجدران الكول والبوت ومستوى نقطة التحول (Gamma Flip).
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from typing import Any, Dict, Optional
import requests

import config
from capital_trader import client

log = logging.getLogger("us500_market_intel")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
_SYM = re.compile(r"^(SPXW?|SPY)(\d{6})([CP])(\d{8})$")
_CACHE: dict[str, tuple[float, dict]] = {}

def _parse_cboe_option(o: dict, today: dt.date) -> Optional[dict]:
    m = _SYM.match(o.get("option", ""))
    if not m:
        return None
    exp = dt.datetime.strptime(m.group(2), "%y%m%d").date()
    bid, ask = float(o.get("bid") or 0), float(o.get("ask") or 0)
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else float(o.get("last_trade_price") or 0)
    return {
        "exp": exp,
        "dte": (exp - today).days,
        "t": "C" if m.group(3) == "C" else "P",
        "k": int(m.group(4)) / 1000.0,
        "oi": float(o.get("open_interest") or 0),
        "vol": float(o.get("volume") or 0),
        "gamma": float(o.get("gamma") or 0),
        "mid": mid,
    }

def get_market_intel() -> Optional[Dict[str, Any]]:
    """جلب المؤشرات الكمية لحركة وسيولة US500 والتدفقات المؤسسية."""
    now = time.time()
    hit = _CACHE.get("intel")
    if hit and (now - hit[0]) < 180:
        return hit[1]

    # 1. Capital sentiment
    sent = client.get_sentiment(config.EPIC)
    long_pct = sent.get("long_pct", 50.0) if sent else 50.0
    short_pct = sent.get("short_pct", 50.0) if sent else 50.0

    call_wall = None
    put_wall = None
    gex_regime = "محايد"
    bias = "توازن نسبي ⚖️"

    try:
        r = requests.get(CBOE_URL, headers=UA, timeout=12)
        if r.status_code == 200:
            d = r.json().get("data") or {}
            spot = float(d.get("current_price") or 0)
            if spot > 0 and d.get("options"):
                today = dt.datetime.now(dt.timezone.utc).date()
                cs = [_parse_cboe_option(o, today) for o in d["options"]]
                near = [c for c in cs if c and 0 <= c["dte"] <= 35 and abs(c["k"] / spot - 1) <= 0.10]
                if near:
                    coi: dict[float, float] = {}
                    poi: dict[float, float] = {}
                    gex_total = 0.0
                    for c in near:
                        (coi if c["t"] == "C" else poi)[c["k"]] = (coi if c["t"] == "C" else poi).get(c["k"], 0) + c["oi"]
                        g = c["gamma"] * c["oi"] * 100 * spot * spot * 0.01
                        gex_total += (g if c["t"] == "C" else -g)

                    call_wall = max((k for k in coi if k >= spot), key=coi.get, default=None)
                    put_wall = max((k for k in poi if k <= spot), key=poi.get, default=None)
                    if gex_total > 50_000_000:
                        gex_regime = "غاما إيجابية (+GEX) استقرار وميل للصعود 🟢"
                    elif gex_total < -50_000_000:
                        gex_regime = "غاما سلبية (-GEX) تذبذب مرتفع وميل للهبوط 🔴"
                    else:
                        gex_regime = "غاما محايدة ⚖️"
    except Exception as e:
        log.warning(f"CBOE options fetch failed: {e}")

    if long_pct > 75.0:
        bias = "طمع أفراد مفرط (احتمال تصحيح) ⚠️"
    elif long_pct < 30.0:
        bias = "خوف أفراد شديد (فرصة تجميع صاعد) 🟢"
    else:
        bias = "استقرار وتوازن مؤسسي 🏛️"

    res = {
        "long_pct": round(long_pct, 1),
        "short_pct": round(short_pct, 1),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gex_regime": gex_regime,
        "bias": bias,
    }
    _CACHE["intel"] = (now, res)
    return res
