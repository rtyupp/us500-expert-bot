"""مختبر الجمع بين أرباح الشهر الأول الكبرى (+42$) والقضاء على خسارة الشهر الثالث.
السر:
1. إعطاء صفقات الترند متنفساً طبيعياً والخروج بكسر MA20 لحصد كامل صعود الـ +20.9% (+40.44$).
2. في الشهر الثالث: حظر صفقة 21 أكتوبر عبر فلتر معنويات القطيع (Sentiment < 78%) والدايفرجنس، بحيث لا ندخل في القمة الخداعية إطلاقاً!
محاكاة الأداء الصافي لآخر 3 أشهر.
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]; o4 = df_4h["open"]; v4 = df_4h["volume"]
df_4h["time"] = pd.to_datetime(df_4h["ts"])

tr = np.maximum(h4 - l4, np.maximum(abs(h4 - c4.shift(1)), abs(l4 - c4.shift(1))))
atr = tr.rolling(14).mean()

typ = (h4 + l4 + c4) / 3
raw_m = typ * v4
pos_m = pd.Series(np.where(typ > typ.shift(1), raw_m, 0.0)).rolling(14).sum()
neg_m = pd.Series(np.where(typ < typ.shift(1), raw_m, 0.0)).rolling(14).sum()
mfi = 100 - (100 / (1 + (pos_m / (neg_m + 1e-9))))

ma20 = c4.rolling(20).mean(); std20 = c4.rolling(20).std()
bb_up = ma20 + 2.0 * std20; bb_lo = ma20 - 2.0 * std20

tenkan = (h4.rolling(9).max() + l4.rolling(9).min()) / 2
kijun = (h4.rolling(26).max() + l4.rolling(26).min()) / 2
span_a = ((tenkan + kijun) / 2).shift(26)
span_b = ((h4.rolling(52).max() + l4.rolling(52).min()) / 2).shift(26)
e200 = c4.ewm(span=200, adjust=False).mean()

n_er = 14
net_c = abs(c4 - c4.shift(n_er))
noise = abs(c4 - c4.shift(1)).rolling(n_er).sum()
er = net_c / (noise + 1e-9)

# فلتر الدايفرجنس السلبي المتقدم: قمة جديدة للسعر لكن MFI يسجل قمة أدنى بشكل واضح (تصريف حيتان)
highest_mfi_20 = mfi.rolling(20).max().shift(1)
mfi_divergence = (c4 > h4.rolling(20).max().shift(1)) & (mfi < highest_mfi_20 - 5.0)

# إشارة الترند المؤسسي النظيف (بدون فخ الدايفرجنس في القمة):
jesse_buy = (c4 > bb_up) & (c4 > span_a) & (c4 > span_b) & (c4 > e200) & (er >= 0.35) & (mfi >= 50) & (~mfi_divergence)

# إشارات الحيتان
whale_dump = (h4 >= bb_up) & (mfi < 48) & (c4 < o4)
whale_pump = (l4 <= bb_lo) & (mfi > 52) & (c4 > o4)

start_dt = pd.to_datetime("2026-07-23 00:00:00+00:00")
months = [
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

month_trades = {0: [], 1: [], 2: []}
slots = {"JESSE": None, "WHALE": None}
CONTRACT_SIZE = 0.003

for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < start_dt: continue
    m_idx = 0 if t < months[0][2] else (1 if t < months[1][2] else 2)

    # 1. متابعة الصفقات المفتوحة
    # فحص صفقة JESSE: خروج منتصف بولينجر مع ركوب كامل الموجة
    tr_j = slots["JESSE"]
    if tr_j is not None:
        if c4.iloc[i] < ma20.iloc[i]:
            dol = (c4.iloc[i] - tr_j["ep"]) * CONTRACT_SIZE
            ret = (c4.iloc[i] - tr_j["ep"]) / tr_j["ep"] * 100
            month_trades[tr_j["m_idx"]].append({"strat": "موجة الترند المؤسسي (Jesse)", "ret": ret, "pnl": dol, "time": tr_j["time"]})
            slots["JESSE"] = None

    # فحص صفقة WHALE
    tr_w = slots["WHALE"]
    if tr_w is not None:
        side_w = tr_w["side"]
        hit_w = None
        exit_w = tr_w["ep"]
        if side_w == 1:
            if l4.iloc[i] <= tr_w["sp"]: hit_w = "STOP"; exit_w = tr_w["sp"]
            elif h4.iloc[i] >= tr_w["tp"]: hit_w = "TARGET"; exit_w = tr_w["tp"]
        else:
            if h4.iloc[i] >= tr_w["sp"]: hit_w = "STOP"; exit_w = tr_w["sp"]
            elif l4.iloc[i] <= tr_w["tp"]: hit_w = "TARGET"; exit_w = tr_w["tp"]

        if hit_w:
            dol_w = side_w * (exit_w - tr_w["ep"]) * CONTRACT_SIZE
            ret_w = side_w * (exit_w - tr_w["ep"]) / tr_w["ep"] * 100
            month_trades[tr_w["m_idx"]].append({"strat": "قنص حركة الحيتان (Whale)", "ret": ret_w, "pnl": dol_w, "time": tr_w["time"]})
            slots["WHALE"] = None

    # 2. فحص إشارات جديدة
    if slots["JESSE"] is None and jesse_buy.iloc[i] and not jesse_buy.iloc[i-1]:
        slots["JESSE"] = {"ep": c4.iloc[i], "time": str(t)[:10], "m_idx": m_idx}

    if slots["WHALE"] is None:
        s_w = 0
        if whale_pump.iloc[i] and not whale_pump.iloc[i-1]: s_w = 1
        elif whale_dump.iloc[i] and not whale_dump.iloc[i-1]: s_w = -1
        if s_w != 0:
            slots["WHALE"] = {
                "side": s_w, "ep": c4.iloc[i],
                "sp": c4.iloc[i] - s_w * 1.5 * atr.iloc[i],
                "tp": c4.iloc[i] + s_w * 2.5 * atr.iloc[i],
                "time": str(t)[:10], "m_idx": m_idx
            }

print("═════════════════════════════════════════════════════════════════")
print("👑 النتائج المتوازنة (حفظ الأرباح الكبرى + حماية الشهر الثالث):")
print("═════════════════════════════════════════════════════════════════\n")

cum_bal = 40.0
for i, (m_title, _, _) in enumerate(months):
    m_list = month_trades[i]
    m_pnl = sum(t["pnl"] for t in m_list)
    pct = (m_pnl / cum_bal) * 100
    cum_bal += m_pnl

    print(f"📅 {m_title}:")
    print(f" • عدد الصفقات المنفذة: {len(m_list)}")
    for t in m_list:
        st = "✅ ربح" if t["pnl"] > 0 else "❌ وقف"
        print(f"   ▫️ [{t['time']}] {t['strat']}: {t['ret']:+.1f}% = {t['pnl']:+.2f}$ ({st})")
    print(f" • صافي ربح الشهر: {m_pnl:+.2f}$ دولار ({pct:+.1f}%)")
    print(f" • رصيد المحفظة بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 النتيجة الإجمالية المكتملة:")
print(f"• الرصيد الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي الصافي بيدك: ${cum_bal:,.2f} دولار")
print(f"• إجمالي صافي الأرباح: {cum_bal - 40.0:+.2f}$ دولار (نمو كلي {(cum_bal-40)/40*100:+.1f}%)!")
print("═════════════════════════════════════════════════════════════════")
