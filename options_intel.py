"""رادار تدفقات الأوبشن المؤسسية لـ SPX من CBOE (Institutional Options Flow & Whale Radar).

يجلب ويحلل مباشرة:
1. الجاما الصافية (Net GEX): تحديد بيئة صانع السوق (Short Gamma = تسارع هبوطي، Long Gamma = تذبذب هادئ).
2. الجدران الرئيسية (Call Wall و Put Wall) وجدران الأسبوع المباشرة (Weekly Key Strikes).
3. تدفق صفقات الحيتان الكبيرة (Block Trades & Sweeps) بحجم يفوق 1 مليون دولار كاش.
4. حساب نسبة Put/Call Ratio ومعنويات المتداولين الكبار مقارنة بالأفراد.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from typing import Any, Dict, List, Optional
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
_SYM = re.compile(r"^(SPXW?|SPY)(\d{6})([CP])(\d{8})$")
_CACHE: dict[str, tuple[float, dict]] = {}
BLOCK_MIN_PREMIUM = 500_000.0  # صفقات 500k$ فأكثر

log = logging.getLogger("options_flow")

def _parse_contract(o: dict, today: dt.date) -> Optional[dict]:
    m = _SYM.match(o.get("option", ""))
    if not m:
        return None
    exp = dt.datetime.strptime(m.group(2), "%y%m%d").date()
    bid, ask = float(o.get("bid") or 0), float(o.get("ask") or 0)
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else float(o.get("last_trade_price") or 0)
    last = float(o.get("last_trade_price") or mid)
    side = 0
    if bid > 0 and ask > bid:
        pos = (last - bid) / (ask - bid)
        side = 1 if pos >= 0.6 else (-1 if pos <= 0.4 else 0)

    return {
        "sym": o["option"],
        "root": m.group(1),
        "exp": exp,
        "dte": (exp - today).days,
        "t": m.group(3),  # 'C' or 'P'
        "k": int(m.group(4)) / 1000.0,
        "oi": float(o.get("open_interest") or 0),
        "vol": float(o.get("volume") or 0),
        "gamma": float(o.get("gamma") or 0),
        "iv": float(o.get("iv") or 0),
        "mid": mid,
        "last": last,
        "side": side,
    }

def get_options_intel(force: bool = False) -> Dict[str, Any]:
    """تحليل شامل وفوري لسلسلة أوبشن SPX من CBOE."""
    now = time.time()
    hit = _CACHE.get("cboe")
    if hit and not force and (now - hit[0]) < 180:
        return hit[1]

    try:
        r = requests.get(CBOE_URL, headers=UA, timeout=20)
        r.raise_for_status()
        d = r.json().get("data") or {}
    except Exception as e:
        log.warning(f"تعذر جلب أوبشن CBOE: {e}")
        return {"ok": False, "error": str(e)}

    spot = float(d.get("current_price") or 0)
    raw_opts = d.get("options") or []
    if spot <= 0 or not raw_opts:
        return {"ok": False, "error": "سلسلة الأوبشن فارغة"}

    today = dt.datetime.now(dt.timezone.utc).date()
    parsed = []
    for o in raw_opts:
        c = _parse_contract(o, today)
        if c and c["dte"] >= 0:
            parsed.append(c)

    # 1. العقود القريبة حتى 35 يوم و 10% حول السعر
    near = [c for c in parsed if c["dte"] <= 35 and abs(c["k"] / spot - 1) <= 0.10]
    front_week = [c for c in parsed if c["dte"] <= 7 and abs(c["k"] / spot - 1) <= 0.05]

    # الجدران المفتوحة الكلية والأسبوعية
    call_oi: dict[float, float] = {}
    put_oi: dict[float, float] = {}
    weekly_call_oi: dict[float, float] = {}
    weekly_put_oi: dict[float, float] = {}

    gex_k: dict[float, float] = {}
    total_call_prem = 0.0
    total_put_prem = 0.0
    total_call_vol = 0.0
    total_put_vol = 0.0

    for c in near:
        k = c["k"]
        prem = c["vol"] * c["mid"] * 100
        if c["t"] == "C":
            call_oi[k] = call_oi.get(k, 0) + c["oi"]
            total_call_prem += prem
            total_call_vol += c["vol"]
        else:
            put_oi[k] = put_oi.get(k, 0) + c["oi"]
            total_put_prem += prem
            total_put_vol += c["vol"]

        # حساب تعرض الجاما بالدولار
        g = c["gamma"] * c["oi"] * 100 * spot * spot * 0.01
        gex_k[k] = gex_k.get(k, 0) + (g if c["t"] == "C" else -g)

    for c in front_week:
        k = c["k"]
        if c["t"] == "C":
            weekly_call_oi[k] = weekly_call_oi.get(k, 0) + c["oi"]
        else:
            weekly_put_oi[k] = weekly_put_oi.get(k, 0) + c["oi"]

    # جدران المقاومة والدعم
    call_wall = max((k for k in call_oi if k >= spot), key=call_oi.get, default=spot * 1.02)
    put_wall = max((k for k in put_oi if k <= spot), key=put_oi.get, default=spot * 0.98)
    
    # الجدران الأقرب للأسبوع الحالي (Tactical Walls)
    tactical_call_wall = max((k for k in weekly_call_oi if k >= spot), key=weekly_call_oi.get, default=call_wall)
    tactical_put_wall = max((k for k in weekly_put_oi if k <= spot), key=weekly_put_oi.get, default=put_wall)

    # نقطة تحول الجاما (Gamma Flip Level)
    flip_level = None
    cum_gex = 0.0
    for k in sorted(gex_k):
        prev = cum_gex
        cum_gex += gex_k[k]
        if (prev < 0 <= cum_gex) or (prev > 0 >= cum_gex):
            if abs(k / spot - 1) <= 0.06:
                flip_level = k
                break

    net_gex = sum(gex_k.values())

    # صفقات الحيتان الكبيرة (Block Trades)
    blocks = []
    for c in near:
        p = c["vol"] * c["mid"] * 100
        if p >= BLOCK_MIN_PREMIUM and c["vol"] >= max(c["oi"] * 0.2, 50):
            # اتجاه الصفقة: Call شراء (+1) أو Put شراء (-1)
            dir_ = (1 if c["t"] == "C" else -1) * (c["side"] if c["side"] != 0 else 1)
            blocks.append({
                "strike": c["k"],
                "type": c["t"],
                "dte": c["dte"],
                "premium": p,
                "direction": dir_,
                "iv": round(c["iv"] * 100, 1),
                "mid": c["mid"],
            })
    blocks.sort(key=lambda b: -b["premium"])

    bullish_flow = sum(b["premium"] for b in blocks if b["direction"] > 0)
    bearish_flow = sum(b["premium"] for b in blocks if b["direction"] < 0)
    flow_total = bullish_flow + bearish_flow
    flow_bias = (bullish_flow - bearish_flow) / flow_total if flow_total > 0 else 0.0

    pcr_vol = round(total_put_vol / (total_call_vol + 1e-9), 2)
    pcr_prem = round(total_put_prem / (total_call_prem + 1e-9), 2)

    # تشخيص البيئة المؤسسية
    if net_gex < -10_000_000_000:
        regime = "غاما سالبة حادة (-GEX): صانع السوق يزيد الهبوط تذبذب عالي وهبوط سريع 🔴"
        action_bias = "PUT_FAVORED"
    elif net_gex > 10_000_000_000:
        regime = "غاما موجبة (+GEX): صانع السوق يخمد التذبذب هدوء وارتداد من القيعان 🟢"
        action_bias = "CALL_FAVORED"
    else:
        regime = "غاما متوازنة (Neutral GEX): تذبذب محصور بين الجدران ⚖️"
        action_bias = "RANGE_BOUND"

    res = {
        "ok": True,
        "spot": spot,
        "net_gex": net_gex,
        "regime": regime,
        "action_bias": action_bias,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "tactical_call_wall": tactical_call_wall,
        "tactical_put_wall": tactical_put_wall,
        "flip_level": flip_level,
        "pcr_vol": pcr_vol,
        "pcr_prem": pcr_prem,
        "flow_bias": round(flow_bias, 2),
        "bullish_flow_usd": bullish_flow,
        "bearish_flow_usd": bearish_flow,
        "top_blocks": blocks[:6],
        "ts": now,
    }
    _CACHE["cboe"] = (now, res)
    return res

def format_money(val: float) -> str:
    a = abs(val)
    if a >= 1e9: return f"{'-' if val < 0 else ''}${a/1e9:.2f}B"
    if a >= 1e6: return f"{'-' if val < 0 else ''}${a/1e6:.1f}M"
    if a >= 1e3: return f"{'-' if val < 0 else ''}${a/1e3:.0f}K"
    return f"{'-' if val < 0 else ''}${a:.0f}"
