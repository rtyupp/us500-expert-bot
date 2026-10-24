"""فحص استراتيجية الاتجاه المؤسسي الصاعد النقي (Long Only above EMA200)."""
import pandas as pd
import numpy as np

df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]
ma20 = c4.rolling(20).mean(); std20 = c4.rolling(20).std()
bb_up = ma20 + 2.0 * std20

tenkan = (h4.rolling(9).max() + l4.rolling(9).min()) / 2
kijun = (h4.rolling(26).max() + l4.rolling(26).min()) / 2
span_a = ((tenkan + kijun) / 2).shift(26)
span_b = ((h4.rolling(52).max() + l4.rolling(52).min()) / 2).shift(26)
e200 = c4.ewm(span=200, adjust=False).mean()

# شراء فقط وفوق متوسط 200 (Long ONLY above EMA200)
buy_j = (c4 > bb_up) & (c4 > span_a) & (c4 > span_b) & (c4 > e200)

start_dt = pd.to_datetime("2026-07-23 00:00:00+00:00")
df_4h["time"] = pd.to_datetime(df_4h["ts"])

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
        if buy_j.iloc[i] and not buy_j.iloc[i-1]:
            in_pos = True; ep = c4.iloc[i]; ep_t = str(t)[:10]; cur_m = m_idx
    else:
        if c4.iloc[i] < ma20.iloc[i]:
            ret = (c4.iloc[i] - ep) / ep * 100
            pnl = (c4.iloc[i] - ep) * 0.003
            month_trades[cur_m].append({"date": ep_t, "ret": ret, "pnl": pnl})
            in_pos = False

print("═════════════════════════════════════════════════════════════════")
print("👑 النتائج التفصيلية لآخر 3 شهور (استراتيجية الاتجاه المؤسسي الصاعد):")
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
        print(f"   ▫️ صفقة {t['date']}: ربح {t['ret']:+.1f}% في البيتكوين = {t['pnl']:+.2f}$ دولار")
    print(f" • صافي ربح الشهر: {m_pnl:+.2f}$ دولار")
    print(f" • نسبة العائد: {pct:+.1f}%")
    print(f" • رصيد المحفظة بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 ملخص الثلاثة أشهر كاملة على رأس مال 40 دولار:")
print(f"• الرصيد الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي بيدك: ${cum_bal:,.2f} دولار")
print(f"• صافي الأرباح الإجمالية: {cum_bal - 40.0:+.2f}$ دولار (نمو كلي {(cum_bal-40)/40*100:+.1f}%)!")
print("═════════════════════════════════════════════════════════════════")
