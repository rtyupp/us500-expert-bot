"""فحص الاستراتيجية مع فلتر الدايفرجنس السلبي وفلتر تدفق السيولة المؤسسية.
الهدف: تحقيق أرباح في كل شهر وتفادي الشراء في القمم الخداعية.
"""
import pandas as pd
import numpy as np

df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]; o4 = df_4h["open"]; v4 = df_4h["volume"]
df_4h["time"] = pd.to_datetime(df_4h["ts"])

# مؤشر كفاءة الاتجاه ER
n_er = 14
net_change = abs(c4 - c4.shift(n_er))
total_noise = abs(c4 - c4.shift(1)).rolling(n_er).sum()
er = net_change / (total_noise + 1e-9)

# مؤشر تدفق السيولة MFI
typ_p = (h4 + l4 + c4) / 3
raw_money = typ_p * v4
pos_flow = np.where(typ_p > typ_p.shift(1), raw_money, 0.0)
neg_flow = np.where(typ_p < typ_p.shift(1), raw_money, 0.0)
pos_mf = pd.Series(pos_flow).rolling(14).sum()
neg_mf = pd.Series(neg_flow).rolling(14).sum()
mfr = pos_mf / (neg_mf + 1e-9)
mfi = 100 - (100 / (1 + mfr))

# RSI(14)
delta = c4.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))

# فحص الدايفرجنس السلبي: السعر أعلى من قمة 20 شمعة لكن RSI أدنى من أعلى قيمة له
highest_rsi_20 = rsi.rolling(20).max().shift(1)
rsi_divergence = (c4 > h4.rolling(20).max().shift(1)) & (rsi < highest_rsi_20 - 3.0)

# Ichimoku + BB
ma20 = c4.rolling(20).mean(); std20 = c4.rolling(20).std()
bb_up = ma20 + 2.0 * std20
tenkan = (h4.rolling(9).max() + l4.rolling(9).min()) / 2
kijun = (h4.rolling(26).max() + l4.rolling(26).min()) / 2
span_a = ((tenkan + kijun) / 2).shift(26)
span_b = ((h4.rolling(52).max() + l4.rolling(52).min()) / 2).shift(26)
e200 = c4.ewm(span=200, adjust=False).mean()

# الشراء المؤسسي النظيف الخالي من فخاخ الحيتان:
# 1. إيشيموكو وبولينجر للأعلى فوق EMA200
# 2. كفاءة الاتجاه جيدة (ER >= 0.35)
# 3. تدفق أموال الحيتان صاعد (MFI >= 50)
# 4. لا يوجد دايفرجنس سلبي مخادع (No Bearish Divergence)
buy_clean = (c4 > bb_up) & (c4 > span_a) & (c4 > span_b) & (c4 > e200) & (er >= 0.35) & (mfi >= 50) & (~rsi_divergence)

start_dt = pd.to_datetime("2026-07-23 00:00:00+00:00")
months = [
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

month_trades = {0: [], 1: [], 2: []}
in_pos = False; ep = 0.0; ep_t = ""; cur_m = 0

for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < start_dt: continue
    m_idx = 0 if t < months[0][2] else (1 if t < months[1][2] else 2)

    if not in_pos:
        if buy_clean.iloc[i] and not buy_clean.iloc[i-1]:
            in_pos = True; ep = c4.iloc[i]; ep_t = str(t)[:10]; cur_m = m_idx
    else:
        if c4.iloc[i] < ma20.iloc[i]:
            ret = (c4.iloc[i] - ep) / ep * 100
            pnl = (c4.iloc[i] - ep) * 0.003
            month_trades[cur_m].append({"date": ep_t, "ret": ret, "pnl": pnl})
            in_pos = False

print("═════════════════════════════════════════════════════════════════")
print("👑 النتائج بعد إضافة فلتر الدايفرجنس وكشف فخاخ الحيتان:")
print("═════════════════════════════════════════════════════════════════\n")

cum_bal = 40.0
for i, (m_title, _, _) in enumerate(months):
    m_list = month_trades[i]
    m_pnl = sum(t["pnl"] for t in m_list)
    pct = (m_pnl / cum_bal) * 100
    cum_bal += m_pnl

    print(f"📅 {m_title}:")
    print(f" • عدد الصفقات: {len(m_list)}")
    for t in m_list:
        print(f"   ▫️ صفقة {t['date']}: ربح {t['ret']:+.1f}% = {t['pnl']:+.2f}$ دولار")
    print(f" • صافي ربح الشهر: {m_pnl:+.2f}$ دولار ({pct:+.1f}%)")
    print(f" • رصيد المحفظة بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 النتيجة الإجمالية الصافية:")
print(f"• الرصيد الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي: ${cum_bal:,.2f} دولار (صافي أرباح {cum_bal-40:+.2f}$ نمو {(cum_bal-40)/40*100:+.1f}%)")
print("═════════════════════════════════════════════════════════════════")
