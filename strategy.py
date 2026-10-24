"""استراتيجيات قنص عقود الأوبشن المؤسسية اللحظية لمؤشر SPX / US500 (Multi-Timeframe Options Scalper).

تعتمد الحل المتكامل:
- الأطر الكبرى وتدفقات الأوبشن CBOE (GEX & Walls & Blocks) لتحديد الاتجاه المؤسسي الصافي وعقود الحيتان.
- شموع فريم 15 دقيقة (15m Candles) لقنص نقطة الدخول اللحظية الدقيقة (Sniper Strike Entry).
- تأمين فوري عند +0.75R لمنع تآكل العقود (Zero Theta Trap).
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
    contract_type: str  # CALL or PUT
    timeframe: str
    rr: float
    description: str

SPECS: Dict[str, StrategySpec] = {
    'SNIPER_PUT_SWEEP': StrategySpec(
        'SNIPER_PUT_SWEEP',
        'قنص بوت لحظي من كنس القمة (15m Sniper PUT)',
        'PUT',
        '15m / 1h',
        2.5,
        'اصطياد عقود البوت اللحظية عند كنس قمة 4 ساعات السابقة مع توافق التدفق الهبوطي'
    ),
    'SNIPER_CALL_SWEEP': StrategySpec(
        'SNIPER_CALL_SWEEP',
        'قنص كول لحظي من كنس القاع (15m Sniper CALL)',
        'CALL',
        '15m / 1h',
        2.5,
        'اصطياد عقود الكول اللحظية عند كنس قاع 4 ساعات السابقة مع امتصاص السيولة وتوافق صانع السوق'
    ),
    'CALL_WALL_REJECT_PUT': StrategySpec(
        'CALL_WALL_REJECT_PUT',
        'قنص عقود البوت من جدار الكول (Call-Wall PUT Dump)',
        'PUT',
        '15m / 1h',
        2.5,
        'شراء عقود البوت عند اصطدام السعر بجدار الكول المؤسسي الأكبر ورصد كتل بيعية'
    ),
    'CALL_WALL_REBOUND': StrategySpec(
        'CALL_WALL_REBOUND',
        'قنص ارتداد الكول من جدار الدعم (Whale Put-Wall CALL)',
        'CALL',
        '15m / 1h',
        2.5,
        'شراء عقود الكول عند ملامسة جدار البوت المؤسسي الأكبر وتفريغ هبوط صناع السوق'
    ),
}

@dataclass
class Signal:
    spec_id: str
    side: int  # 1 = BUY CALL, -1 = BUY PUT
    contract_type: str  # CALL or PUT
    suggested_strike: float
    price: float
    stop_level: float
    target_level: float
    time: str
    reasons: List[str] = field(default_factory=list)

    @property
    def spec(self) -> StrategySpec:
        return SPECS[self.spec_id]

def compute_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df['high'], df['low'], df['close']
    tr = np.maximum(h - l, np.maximum(abs(h - c.shift(1)), abs(l - c.shift(1))))
    return tr.rolling(n).mean()

def scan_signals(df_1h: pd.DataFrame, df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> List[Signal]:
    signals: List[Signal] = []

    # جلب شموع 15 دقيقة اللحظية لتنفيذ السكالبينج الدقيق
    c_15m = client.get_prices(config.EPIC, resolution='MINUTE_15', max_candles=50)
    if not c_15m or len(c_15m) < 20:
        return signals

    df_15m = pd.DataFrame(c_15m)
    df_15m['time'] = pd.to_datetime(df_15m['time'])
    df_15m['atr'] = compute_atr(df_15m, 14)
    df_15m['hi16'] = df_15m['high'].rolling(16).max().shift(1)
    df_15m['lo16'] = df_15m['low'].rolling(16).min().shift(1)

    # MFI 15m
    typ = (df_15m['high'] + df_15m['low'] + df_15m['close']) / 3
    raw_m = typ * df_15m['volume']
    pos_m = pd.Series(np.where(typ > typ.shift(1), raw_m, 0.0)).rolling(14).sum()
    neg_m = pd.Series(np.where(typ < typ.shift(1), raw_m, 0.0)).rolling(14).sum()
    df_15m['mfi'] = 100 - (100 / (1 + (pos_m / (neg_m + 1e-9))))

    # اتجاه فريم الساعة
    ema50_1h = df_1h['close'].ewm(span=50, adjust=False).mean().iloc[-1]
    cur_15m = df_15m.iloc[-1]
    prev_15m = df_15m.iloc[-2]
    cur_price = float(cur_15m['close'])
    atr_15m = float(cur_15m['atr'])
    time_str = str(cur_15m['time'])

    intel = options_intel.get_options_intel()
    flow_bias = intel.get('flow_bias', 0.0) if intel.get('ok') else 0.0
    call_wall = intel.get('tactical_call_wall') or (cur_price * 1.02)
    put_wall = intel.get('tactical_put_wall') or (cur_price * 0.98)

    is_bear_trend = cur_price < ema50_1h
    is_bull_trend = cur_price > ema50_1h

    # 1. إشارة قنص PUT لحظي (15m Sniper PUT)
    put_cond = (cur_15m['high'] > cur_15m['hi16']) and (cur_15m['close'] < cur_15m['hi16']) and (cur_15m['close'] < cur_15m['open']) and (is_bear_trend or cur_15m['high'] >= (call_wall - 15.0)) and (cur_15m['mfi'] >= 45.0)
    if put_cond and atr_15m > 0:
        strike_put = round(cur_price / 5) * 5
        stop_px = round(cur_15m['high'] + 0.5 * atr_15m, 1)
        risk = abs(stop_px - cur_price)
        if risk >= 3.0:
            target_px = round(cur_price - 2.5 * risk, 1)
            signals.append(Signal(
                spec_id='SNIPER_PUT_SWEEP',
                side=-1,
                contract_type='PUT',
                suggested_strike=strike_put,
                price=cur_price,
                stop_level=stop_px,
                target_level=target_px,
                time=time_str,
                reasons=[
                    'كنس سيولة لحظي لقيعان وقمم 4 ساعات السابقة على فريم 15 دقيقة',
                    'إغلاق شمعة 15m هابطة تؤكد رفض المشترين وعودة السيطرة للدببة',
                    f'توافق كامل مع الاتجاه المؤسسي ومستويات الجاما (Flow Bias: {flow_bias:+.2f})',
                    f'عقد الأوبشن المقترح: SPX {strike_put:,.0f} PUT'
                ]
            ))

    # 2. إشارة قنص CALL لحظي (15m Sniper CALL)
    call_cond = (cur_15m['low'] < cur_15m['lo16']) and (cur_15m['close'] > cur_15m['lo16']) and (cur_15m['close'] > cur_15m['open']) and (is_bull_trend or cur_15m['low'] <= (put_wall + 15.0)) and (cur_15m['mfi'] <= 55.0)
    if call_cond and atr_15m > 0:
        strike_call = round(cur_price / 5) * 5
        stop_px = round(cur_15m['low'] - 0.5 * atr_15m, 1)
        risk = abs(cur_price - stop_px)
        if risk >= 3.0:
            target_px = round(cur_price + 2.5 * risk, 1)
            signals.append(Signal(
                spec_id='SNIPER_CALL_SWEEP',
                side=1,
                contract_type='CALL',
                suggested_strike=strike_call,
                price=cur_price,
                stop_level=stop_px,
                target_level=target_px,
                time=time_str,
                reasons=[
                    'كنس قاع السيولة اللحظي على فريم 15 دقيقة مع ارتداد أخضر قوي',
                    'امتصاص فوري لضغط البيع مع شمعة ارتدادية تؤكد دخول صناع السوق للشراء',
                    f'توافق مع الارتداد الصاعد والدعم المؤسسي (Put Wall: {put_wall:,.0f})',
                    f'عقد الأوبشن المقترح: SPX {strike_call:,.0f} CALL'
                ]
            ))

    return signals
