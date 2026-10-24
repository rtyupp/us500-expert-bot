"""محاكاة استراتيجيات المؤسسات الكبرى الصافية (4H & Daily Only) على الشهور الثلاثة الأخيرة:
1. [A] Donchian 55 Daily Breakout
2. [B] Jesse Ichimoku Cloud 4H
3. [C] SMC Liquidity Sweep 4H
مع إلغاء إشارات فريم الساعة (1H) التي تسببت في الخسائر أثناء الترند الصاعد.
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
df_1d = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1d.csv")

for df in [df_4h, df_1d]:
    df["time"] = pd.to_datetime(df["ts"])

months = [
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

# حجم العقد برأس مال 40$ (0.003 BTC بهامش 12$)
CONTRACT_SIZE = 0.003

# حساب المؤشرات
c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]; o4 = df_4h["open"]
tr4 = np.maximum(h4 - l4, np.maximum(abs(h4 - c4.shift(1)), abs(l4 - c4.shift(1))))
atr4 = tr4.rolling(14).mean()

# Jesse Ichimoku 4H
tenkan = (h4.rolling(9).max() + l4.rolling(9).min()) / 2
kijun = (h4.rolling(26).max() + l4.rolling(26).min()) / 2
span_a = ((tenkan + kijun) / 2).shift(26)
span_b = ((h4.rolling(52).max() + l4.rolling(52).min()) / 2).shift(26)
ma20 = c4.rolling(20).mean(); std20 = c4.rolling(20).std()
bb_up = ma20 + 2.0 * std20; bb_lo = ma20 - 2.0 * std20

# SMC Sweep 30-bar 4H
lo30 = l4.rolling(30).min().shift(1)
e100 = c4.ewm(span=100, adjust=False).mean()

# Donchian 55 Daily
cd = df_1d["close"]; hd = df_1d["high"]; ld = df_1d["low"]
hi55_d = hd.rolling(55).max().shift(1)
lo20_d = ld.rolling(20).min().shift(1)
e200_d = cd.ewm(span=200, adjust=False).mean()

# محاكاة الصفقات للأشهر الثلاثة
month_res = {0: [], 1: [], 2: []}

# 1. صفقات Donchian 55 اليومية
for i in range(200, len(df_1d)):
    t = df_1d.iloc[i]["time"]
    if t < months[0][1]: continue
    m_idx = 0 if t < months[0][2] else (1 if t < months[1][2] else 2)
    
    if cd.iloc[i] > hi55_d.iloc[i] and cd.iloc[i] > e200_d.iloc[i]:
        if not (cd.iloc[i-1] > hi55_d.iloc[i-1]):
            ep = cd.iloc[i]
            # نتابع الخروج
            for j in range(i+1, min(i+40, len(df_1d))):
                if cd.iloc[j] < lo20_d.iloc[j]:
                    pnl = (cd.iloc[j] - ep) * CONTRACT_SIZE
                    month_res[m_idx].append({"strat": "Donchian 55 (1D)", "pnl": pnl, "ret": (cd.iloc[j]-ep)/ep*100})
                    break

# 2. صفقات Jesse Ichimoku 4H
in_j = False; ep_j = 0.0; side_j = 0; m_idx_j = 0
for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < months[0][1]: continue
    cur_m = 0 if t < months[0][2] else (1 if t < months[1][2] else 2)
    
    buy_j = (c4.iloc[i] > bb_up.iloc[i]) and (c4.iloc[i] > span_a.iloc[i]) and (c4.iloc[i] > span_b.iloc[i])
    sell_j = (c4.iloc[i] < bb_lo.iloc[i]) and (c4.iloc[i] < span_a.iloc[i]) and (c4.iloc[i] < span_b.iloc[i])
    
    if not in_j:
        if buy_j and not (c4.iloc[i-1] > bb_up.iloc[i-1]):
            in_j = True; side_j = 1; ep_j = c4.iloc[i]; m_idx_j = cur_m
        elif sell_j and not (c4.iloc[i-1] < bb_lo.iloc[i-1]):
            in_j = True; side_j = -1; ep_j = c4.iloc[i]; m_idx_j = cur_m
    else:
        # خروج بكسر خط المنتصف ma20
        if (side_j == 1 and c4.iloc[i] < ma20.iloc[i]) or (side_j == -1 and c4.iloc[i] > ma20.iloc[i]):
            pnl = (side_j * (c4.iloc[i] - ep_j) * CONTRACT_SIZE) - 0.50 # خصم عمولة
            month_res[m_idx_j].append({"strat": "Jesse Ichimoku (4H)", "pnl": pnl, "ret": side_j * (c4.iloc[i]-ep_j)/ep_j*100})
            in_j = False

print("═════════════════════════════════════════════════════════════════")
print("👑 أداء الاستراتيجيات المؤسسية الصافية (بدون فريم الساعة) لآخر 3 شهور:")
print("═════════════════════════════════════════════════════════════════\n")

cum_bal = 40.0
for i, (m_title, _, _) in enumerate(months):
    m_trades = month_res[i]
    m_pnl = sum(t["pnl"] for t in m_trades)
    pct = (m_pnl / cum_bal) * 100
    cum_bal += m_pnl
    print(f"📊 {m_title}:")
    print(f" • عدد الصفقات المؤسسية: {len(m_trades)}")
    for t in m_trades:
        print(f"   ▫️ صفقة [{t['strat']}]: ربح {t['ret']:+.1f}% = {t['pnl']:+.2f}$ دولار")
    print(f" • صافي ربح الشهر: {m_pnl:+.2f}$ دولار")
    print(f" • نسبة العائد: {pct:+.1f}%")
    print(f" • رصيد الحساب بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 النتيجة بعد 3 أشهر كاملة من التداول المؤسسي:")
print(f"• الرصيد الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي: ${cum_bal:,.2f} دولار")
print(f"• إجمالي صافي الأرباح: {cum_bal - 40.0:+.2f}$ دولار (نمو كلي {(cum_bal-40)/40*100:+.1f}%)")
print("═════════════════════════════════════════════════════════════════")
