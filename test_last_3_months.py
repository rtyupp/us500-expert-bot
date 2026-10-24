"""محاكاة أداء البوت واستراتيجياته على آخر 3 شهور (من يوليو 2026 إلى أكتوبر 2026).
يحسب الصفقات والأرباح الصافية لكل شهر على حدة (بالدولار على رأس مال 40$).
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

# جلب البيانات التاريخية
df_1h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1h.csv")
df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
df_1d = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1d.csv")

for df in [df_1h, df_4h, df_1d]:
    df["time"] = pd.to_datetime(df["ts"])

# تحديد بداية الأشهر الثلاثة الأخيرة (من 23 يوليو 2026 حتى 23 أكتوبر 2026)
start_3m = pd.to_datetime("2026-07-23 00:00:00+00:00")
print("═════════════════════════════════════════════════════════════════")
print("📊 اختبار أداء البوت على آخر 3 شهور (من 23 يوليو إلى 23 أكتوبر 2026)")
print("═════════════════════════════════════════════════════════════════\n")

# الشهور الثلاثة:
# الشهر 1: 23 يوليو إلى 23 أغسطس 2026
# الشهر 2: 23 أغسطس إلى 23 سبتمبر 2026
# الشهر 3: 23 سبتمبر إلى 23 أكتوبر 2026

# فحص أسعار البداية والنهاية لكل شهر
for m_idx, (m_name, s_dt, e_dt) in enumerate([
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", "2026-07-23", "2026-08-23"),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", "2026-08-23", "2026-09-23"),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", "2026-09-23", "2026-10-23"),
], 1):
    sub = df_1d[(df_1d["time"] >= s_dt) & (df_1d["time"] < e_dt)]
    if len(sub) > 0:
        o_p = sub.iloc[0]["open"]
        c_p = sub.iloc[-1]["close"]
        h_p = sub["high"].max()
        l_p = sub["low"].min()
        chg = (c_p - o_p) / o_p * 100
        print(f"📅 {m_name}:")
        print(f"   افتتاح: ${o_p:,.0f} | إغلاق: ${c_p:,.0f} | أعلى: ${h_p:,.0f} | أدنى: ${l_p:,.0f} | تغير السوق: {chg:+.1f}%\n")
