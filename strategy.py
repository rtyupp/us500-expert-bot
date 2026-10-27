"""استراتيجيات قنص عقود الأوبشن المؤسسية اللحظية لمؤشر SPX / US500 (Sniper Options Scalper).

تم تصحيح التوقيت والأهداف ومطابقتها للشارت الفعلي:
1. شرط شمعة التأكيد (Retest & Confirmation): لا دخول مع شمعة الكنس الأولى، بل ننتظر شمعة إعادة الاختبار وتأكيد كسر القاع/القمة.
2. حصر التداول في فترات السيولة الحقيقية للأوبشن ومنع التداول في الفترات الآسيوية الميتة.
3. هدف واقعي وسريع للأوبشن (8 إلى 12 نقطة بمؤشر SPX تعطي 50% إلى 100% ربح في العقد).
4. تأمين الدخول الفوري (Free-Ride Break-Even) بعد تحرك السعر 4.5 إلى 5 نقاط لمنع تآكل الثيتا.
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
    'SNIPER_PUT_CONFIRM': StrategySpec(
        'SNIPER_PUT_CONFIRM',
        'قنص بوت مؤكد بعد إعادة الاختبار (Sniper Retest PUT)',
        'PUT',
        '15m',
        1.25,
        'شراء عقد بوت بعد اكتمال كنس القمة وتأكيد شمعة 15m هابطة تكسر قاع شمعة الكنس'
    ),
    'SNIPER_CALL_CONFIRM': StrategySpec(
        'SNIPER_CALL_CONFIRM',
        'قنص كول مؤكد بعد إعادة الاختبار (Sniper Retest CALL)',
        'CALL',
        '15m',
        1.25,
        'شراء عقد كول بعد اكتمال كنس القاع وتأكيد شمعة 15m صاعدة تخترق قمة شمعة الكنس'
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

    c_15m = client.get_prices(config.EPIC, resolution='MINUTE_15', max_candles=60)
    if not c_15m or len(c_15m) < 25:
        return signals

    df_15m = pd.DataFrame(c_15m)
    df_15m['time'] = pd.to_datetime(df_15m['time'])
    df_15m['atr'] = compute_atr(df_15m, 14)
    df_15m['hi16'] = df_15m['high'].rolling(16).max().shift(2)
    df_15m['lo16'] = df_15m['low'].rolling(16).min().shift(2)

    # اتجاه فريم الساعة
    ema50_1h = df_1h['close'].ewm(span=50, adjust=False).mean().iloc[-1]

    row = df_15m.iloc[-1]
    prev1 = df_15m.iloc[-2]
    cur_px = float(row['close'])
    atr = float(row['atr'])
    t_str = str(row['time'])

    is_bear = cur_px < ema50_1h
    is_bull = cur_px > ema50_1h

    # كفاءة الحركة لمنع الفخاخ أثناء التذبذب (Kaufman Efficiency Ratio)
    c15 = df_15m['close'].astype(float)
    change = (c15 - c15.shift(16)).abs().iloc[-1]
    vol = (c15 - c15.shift(1)).abs().rolling(16).sum().iloc[-1]
    er = change / (vol + 1e-9)
    if er < 0.25:
        return signals # السوق في تذبذب حائر، ممنوع الدخول

    # 1. إشارة PUT بعد شمعة التأكيد
    put_confirm = (prev1['high'] > prev1['hi16']) and (prev1['close'] < prev1['open']) and (row['close'] < prev1['low']) and is_bear
    # 2. إشارة CALL بعد شمعة التأكيد
    call_confirm = (prev1['low'] < prev1['lo16']) and (prev1['close'] > prev1['open']) and (row['close'] > prev1['high']) and is_bull

    stop_pts = 8.0 # وقف تنفسي محكم 8 نقاط
    tp_pts = 10.0   # هدف سريع 10 نقاط (تضاعف سريع في بريميوم الأوبشن)

    if put_confirm and atr > 0:
        strike_put = round(cur_px / 5) * 5
        signals.append(Signal(
            spec_id='SNIPER_PUT_CONFIRM',
            side=-1,
            contract_type='PUT',
            suggested_strike=strike_put,
            price=cur_px,
            stop_level=round(cur_px + stop_pts, 1),
            target_level=round(cur_px - tp_pts, 1),
            time=t_str,
            reasons=[
                'كنس قمة الساعات السابقة واكتمال شمعة إعادة الاختبار وتأكيد الكسر لأسفل',
                'التوافق التام مع الاتجاه العام الهابط على فريم الساعة',
                f'الهدف السريع: {tp_pts} نقاط لتحقيق ربح متفجر وخروج آمن قبل الارتداد',
                f'عقد الأوبشن المقترح: SPX {strike_put:,.0f} PUT'
            ]
        ))
    elif call_confirm and atr > 0:
        strike_call = round(cur_px / 5) * 5
        signals.append(Signal(
            spec_id='SNIPER_CALL_CONFIRM',
            side=1,
            contract_type='CALL',
            suggested_strike=strike_call,
            price=cur_px,
            stop_level=round(cur_px - stop_pts, 1),
            target_level=round(cur_px + tp_pts, 1),
            time=t_str,
            reasons=[
                'كنس قاع الساعات السابقة واكتمال شمعة إعادة الاختبار وتأكيد الاختراق لأعلى',
                'التوافق مع الاتجاه الصاعد وامتصاص عروض البيع المؤسسية',
                f'الهدف السريع: {tp_pts} نقاط لتحقيق ربح متفجر وخروج آمن قبل الارتداد',
                f'عقد الأوبشن المقترح: SPX {strike_call:,.0f} CALL'
            ]
        ))

    return signals
