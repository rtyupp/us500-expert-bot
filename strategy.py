"""استراتيجيات صيد تحركات الحيتان وتدفقات الأوبشن لمؤشر SPX / US500 (Predictive Options Flow Strategies).

مبنية على استباق حركة صناع السوق والحيتان وليس اللحاق بالسعر:
1. [CALL_WALL_REJECT_PUT] بوت (PUT Short): اصطدام السعر بجدار الكول (Call Wall) أو قمة تدفق الشراء مع ظهور عقود بوت مؤسسية بملايين الدولارات.
2. [CALL_WALL_REBOUND] كول (CALL Rebound): ارتداد السعر من جدار البوت الرئيسي (Put Wall) مع امتصاص بيع الحيتان وتكوين قاع.
3. [GAMMA_CASCADE_PUT] بوت سريع (Short Gamma Cascade): السعر تحت منطقة الجاما السالبة الصافية وكسر دعم مع تدفق هبوطي مستمر.
4. [INSTITUTIONAL_SWEEP_CALL] كول انفجاري (Institutional Sweep): رصد تدفق شراء كول ضخم (Block/Sweep > 10M$) مع معنويات أفراد متخوفة.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

import config
from capital_trader import client
import options_intel

@dataclass
class StrategySpec:
    id: str
    name: str
    contract_type: str  # "CALL" or "PUT"
    timeframe: str
    rr: float
    description: str

SPECS: Dict[str, StrategySpec] = {
    "CALL_WALL_REBOUND": StrategySpec(
        "CALL_WALL_REBOUND",
        "قنص ارتداد الكول من جدار الدعم (Whale Put-Wall CALL)",
        "CALL",
        "4h/1h",
        2.5,
        "اقتناص عقود الكول عند وصول السعر لجدار البوت وتفريغ هبوط صناع السوق مع امتصاص السيولة"
    ),
    "CALL_WALL_REJECT_PUT": StrategySpec(
        "CALL_WALL_REJECT_PUT",
        "قنص عقود البوت من جدار الكول (Call-Wall PUT Dump)",
        "PUT",
        "4h/1h",
        2.5,
        "شراء عقود البوت قبل الجميع عند اصطدام السعر بجدار المقاومة الكبرى (Call Wall) ورصد كتل بيعية مؤسسية"
    ),
    "GAMMA_CASCADE_PUT": StrategySpec(
        "GAMMA_CASCADE_PUT",
        "ركوب تسارع الهبوط بالجاما السالبة (Short Gamma Cascade PUT)",
        "PUT",
        "1h",
        2.0,
        "شراء بوت سريع عندما تكون بيئة صانع السوق (-GEX) والسعر يكسر دعم لحظي مع تدفق سلبي"
    ),
    "INSTITUTIONAL_SWEEP_CALL": StrategySpec(
        "INSTITUTIONAL_SWEEP_CALL",
        "ركوب كتل الشراء المؤسسية الضخمة (Institutional Block CALL)",
        "CALL",
        "1h",
        2.0,
        "دخول كول استباقي فور رصد كتل شراء كول بأكثر من 15 مليون دولار من الحيتان"
    ),
}

@dataclass
class Signal:
    spec_id: str
    side: int  # 1 = BUY CALL / LONG, -1 = BUY PUT / SHORT
    contract_type: str  # "CALL" or "PUT"
    suggested_strike: float  # السترايك المقترح لعقد الأوبشن
    price: float
    stop_level: float
    target_level: float
    time: str
    reasons: List[str] = field(default_factory=list)

    @property
    def spec(self) -> StrategySpec:
        return SPECS[self.spec_id]

def compute_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = np.maximum(h - l, np.maximum(abs(h - c.shift(1)), abs(l - c.shift(1))))
    return tr.rolling(n).mean()

def scan_signals(df_1h: pd.DataFrame, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> List[Signal]:
    """فحص واستباق تحركات الحيتان وتدفقات الأوبشن لحظياً."""
    signals: List[Signal] = []

    # جلب تدفقات الأوبشن اللحظية من CBOE
    intel = options_intel.get_options_intel()
    if not intel.get("ok"):
        return signals

    cur_spot = intel["spot"]
    call_wall = intel.get("tactical_call_wall") or intel.get("call_wall") or (cur_spot * 1.02)
    put_wall = intel.get("tactical_put_wall") or intel.get("put_wall") or (cur_spot * 0.98)
    net_gex = intel.get("net_gex", 0.0)
    flow_bias = intel.get("flow_bias", 0.0)
    top_blocks = intel.get("top_blocks", [])

    # قراءة الشموع الفنية اللحظية لـ US500
    atr_1h = float(compute_atr(df_1h, 14).iloc[-1])
    cur_1h = df_1h.iloc[-1]
    prev_1h = df_1h.iloc[-2]
    cur_price = float(cur_1h["close"])
    time_str = str(cur_1h["time"])

    # معنويات المتداولين في Capital.com (عكس اتجاه القطيع)
    sent = client.get_sentiment(config.EPIC)
    retail_long_pct = sent.get("long_pct", 50.0) if sent else 50.0

    # 1. إشارة [CALL_WALL_REJECT_PUT]: اصطدام بجدار الكول أو قمة مع رصد كتل بوت
    dist_to_call_wall = (call_wall - cur_price)
    has_large_put_block = any(b["type"] == "P" and b["premium"] >= 15_000_000 for b in top_blocks)
    
    if (-15.0 <= dist_to_call_wall <= 25.0) and (flow_bias <= -0.15 or has_large_put_block) and (cur_1h["close"] < cur_1h["open"]):
        stop_px = round(max(call_wall, cur_price) + 1.2 * atr_1h, 1)
        target_px = round(cur_price - 2.5 * abs(stop_px - cur_price), 1)
        strike_put = round(cur_price / 10) * 10
        signals.append(Signal(
            spec_id="CALL_WALL_REJECT_PUT",
            side=-1,
            contract_type="PUT",
            suggested_strike=strike_put,
            price=cur_price,
            stop_level=stop_px,
            target_level=target_px,
            time=time_str,
            reasons=[
                f"السعر يصطدم بجدار الكول المؤسسي الأقوى (Call Wall: {call_wall:,.0f})",
                f"رصد تدفقات هبوطية للحيتان (Flow Bias: {flow_bias:+.2f}) مع كتل بوت نشطة",
                "إغلاق شمعة انعكاسية هابطة على فريم الساعة تؤكد دفاع صناع السوق عن الجدار",
                f"عقد الأوبشن المقترح: SPX {strike_put:,.0f} PUT"
            ]
        ))

    # 2. إشارة [CALL_WALL_REBOUND]: ارتداد كول من جدار البوت الرئيسي
    dist_to_put_wall = (cur_price - put_wall)
    has_large_call_block = any(b["type"] == "C" and b["premium"] >= 15_000_000 for b in top_blocks)

    if (-25.0 <= dist_to_put_wall <= 30.0) and (cur_1h["close"] > cur_1h["open"]) and (flow_bias >= 0.05 or has_large_call_block or retail_long_pct < 40.0):
        stop_px = round(min(put_wall, cur_price) - 1.2 * atr_1h, 1)
        target_px = round(cur_price + 2.5 * abs(cur_price - stop_px), 1)
        strike_call = round(cur_price / 10) * 10
        signals.append(Signal(
            spec_id="CALL_WALL_REBOUND",
            side=1,
            contract_type="CALL",
            suggested_strike=strike_call,
            price=cur_price,
            stop_level=stop_px,
            target_level=target_px,
            time=time_str,
            reasons=[
                f"السعر يلامس جدار البوت المؤسسي (Put Wall: {put_wall:,.0f}) مع امتصاص البيع",
                "ارتداد صاعد مع شمعة ارتدادية خضراء تدل على انتهاء موجة التصريف",
                "صناع السوق مجبرون على شراء المؤشر لتغطية ��لتا الجاما المفتوحة",
                f"عقد الأوبشن المقترح: SPX {strike_call:,.0f} CALL"
            ]
        ))

    # 3. إشارة [GAMMA_CASCADE_PUT]: تسارع هبوط بالجاما السالبة (Short Gamma Cascade)
    if net_gex < -15_000_000_000 and flow_bias < -0.25 and (cur_1h["close"] < prev_1h["low"]) and (cur_1h["close"] < cur_1h["open"]):
        stop_px = round(prev_1h["high"] + 0.8 * atr_1h, 1)
        target_px = round(cur_price - 2.0 * abs(stop_px - cur_price), 1)
        strike_put = round((cur_price - 10) / 10) * 10
        signals.append(Signal(
            spec_id="GAMMA_CASCADE_PUT",
            side=-1,
            contract_type="PUT",
            suggested_strike=strike_put,
            price=cur_price,
            stop_level=stop_px,
            target_level=target_px,
            time=time_str,
            reasons=[
                f"بيئة غاما سالبة عنيفة (-GEX: {options_intel.format_money(net_gex)}) تجبر صانع السوق على بيع المؤشر مع كل هبوط",
                f"كسر قاع الشمعة السابقة مع تدفق كتل بيعية صافية بنسبة {flow_bias:+.2f}",
                "تسارع هبوطي حر مع ضعف طلبات الشراء المؤسسية",
                f"عقد الأوبشن المقترح: SPX {strike_put:,.0f} PUT"
            ]
        ))

    # 4. إشارة [INSTITUTIONAL_SWEEP_CALL]: رصد كتل شراء كول ضخمة
    if has_large_call_block and flow_bias > 0.30 and (cur_1h["close"] > cur_1h["open"]):
        stop_px = round(cur_1h["low"] - 1.0 * atr_1h, 1)
        target_px = round(cur_price + 2.0 * abs(cur_price - stop_px), 1)
        top_c = next(b for b in top_blocks if b["type"] == "C")
        strike_call = top_c["strike"]
        signals.append(Signal(
            spec_id="INSTITUTIONAL_SWEEP_CALL",
            side=1,
            contract_type="CALL",
            suggested_strike=strike_call,
            price=cur_price,
            stop_level=stop_px,
            target_level=target_px,
            time=time_str,
            reasons=[
                f"رصد كتل شراء CALL مؤسسية ضخمة بقيمة {options_intel.format_money(top_c['premium'])} عند سترايك {top_c['strike']:,.0f}",
                f"سيطرة تدفقات الشراء الصريحة للحيتان (Flow Bias: {flow_bias:+.2f})",
                f"عقد الأوبشن المقترح المستهدف من الحيتان: SPX {strike_call:,.0f} CALL"
            ]
        ))

    return signals
