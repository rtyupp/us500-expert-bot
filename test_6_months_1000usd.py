"""فحص واختبار أداء البوت واستراتيجيات الحيتان على آخر 6 شهور كاملة (23 أبريل - 23 أكتوبر 2026).
رأس المال الابتدائي: 1,000 دولار.
حجم العقد المعتمد: يتناسب مع رأس مال 1,000$ (0.05 BTC بهامش 200$ برافعة 1:20 آمنة 20% من المحفظة).
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

# جلب البيانات التاريخية
df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
df_4h["time"] = pd.to_datetime(df_4h["ts"])
df_1d = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1d.csv")
df_1d["time"] = pd.to_datetime(df_1d["ts"])

# تحديد بداية الـ 6 شهور (23 أبريل 2026 حتى 23 أكتوبر 2026)
start_6m = pd.to_datetime("2026-04-23 00:00:00+00:00")
end_6m = pd.to_datetime("2026-10-23 00:00:00+00:00")

# فترات الأشهر الستة:
months = [
    ("الشهر الأول (23 أبريل - 23 مايو 2026)", pd.to_datetime("2026-04-23 00:00:00+00:00"), pd.to_datetime("2026-05-23 00:00:00+00:00")),
    ("الشهر الثاني (23 مايو - 23 يونيو 2026)", pd.to_datetime("2026-05-23 00:00:00+00:00"), pd.to_datetime("2026-06-23 00:00:00+00:00")),
    ("الشهر الثالث (23 يونيو - 23 يوليو 2026)", pd.to_datetime("2026-06-23 00:00:00+00:00"), pd.to_datetime("2026-07-23 00:00:00+00:00")),
    ("الشهر الرابع (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الخامس (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر السادس (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]; o4 = df_4h["open"]; v4 = df_4h["volume"]
tr4 = np.maximum(h4 - l4, np.maximum(abs(h4 - c4.shift(1)), abs(l4 - c4.shift(1))))
atr4 = tr4.rolling(14).mean()

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

# فلتر الدايفرجنس السلبي MFI
highest_mfi_20 = mfi.rolling(20).max().shift(1)
is_mfi_divergence = (c4 > h4.rolling(20).max().shift(1)) & (mfi < highest_mfi_20 - 5.0)

# 1. إشارة الترند المؤسسي الصاعد (Jesse 4H)
jesse_buy = (c4 > bb_up) & (c4 > span_a) & (c4 > span_b) & (c4 > e200) & (er >= 0.35) & (mfi >= 50) & (~is_mfi_divergence)

# 2. إشارات رادار الحيتان (Whale Shadow)
whale_dump = (h4 >= bb_up) & (mfi < 48) & (c4 < o4)
whale_pump = (l4 <= bb_lo) & (mfi > 52) & (c4 > o4)

# حجم العقد: 0.05 BTC (يعادل 4,000$ حجم تداول بهامش 200$ فقط في كابيتال)
CONTRACT_SIZE = 0.05

month_trades = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}
slots = {"JESSE": None, "WHALE": None}

for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < start_6m or t > end_6m:
        continue

    # تحديد رقم الشهر من 0 إلى 5
    m_idx = 5
    for idx_m, (_, s_m, e_m) in enumerate(months):
        if s_m <= t < e_m:
            m_idx = idx_m
            break

    # متابعة الصفقات
    tr_j = slots["JESSE"]
    if tr_j is not None:
        if c4.iloc[i] < ma20.iloc[i]:
            ret = (c4.iloc[i] - tr_j["ep"]) / tr_j["ep"] * 100
            pnl = (c4.iloc[i] - tr_j["ep"]) * CONTRACT_SIZE
            month_trades[tr_j["m_idx"]].append({
                "strat": "موجة الترند المؤسسي [B]", "time": tr_j["time"], "exit_time": str(t)[:10],
                "entry": tr_j["ep"], "exit": c4.iloc[i], "ret": ret, "pnl": pnl
            })
            slots["JESSE"] = None

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
            ret = side_w * (exit_w - tr_w["ep"]) / tr_w["ep"] * 100
            pnl = side_w * (exit_w - tr_w["ep"]) * CONTRACT_SIZE
            month_trades[tr_w["m_idx"]].append({
                "strat": "رادار الحيتان [D]", "time": tr_w["time"], "exit_time": str(t)[:10],
                "entry": tr_w["ep"], "exit": exit_w, "ret": ret, "pnl": pnl
            })
            slots["WHALE"] = None

    # فتح صفقات جديدة
    if slots["JESSE"] is None and jesse_buy.iloc[i] and not jesse_buy.iloc[i-1]:
        slots["JESSE"] = {"ep": c4.iloc[i], "time": str(t)[:10], "m_idx": m_idx}

    if slots["WHALE"] is None:
        s_w = 0
        if whale_pump.iloc[i] and not whale_pump.iloc[i-1]: s_w = 1
        elif whale_dump.iloc[i] and not whale_dump.iloc[i-1]: s_w = -1
        if s_w != 0:
            slots["WHALE"] = {
                "side": s_w, "ep": c4.iloc[i],
                "sp": c4.iloc[i] - s_w * 1.5 * atr4.iloc[i],
                "tp": c4.iloc[i] + s_w * 2.5 * atr4.iloc[i],
                "time": str(t)[:10], "m_idx": m_idx
            }

print("═════════════════════════════════════════════════════════════════")
print("💰 نتائج اختبار الـ 6 شهور الماضية بالكامل على رأس مال 1,000 دولار:")
print("═════════════════════════════════════════════════════════════════\n")

cum_bal = 1000.0
total_trades_count = 0
total_wins_count = 0

for i, (m_title, _, _) in enumerate(months):
    m_list = month_trades[i]
    m_pnl = sum(t["pnl"] for t in m_list)
    pct = (m_pnl / cum_bal) * 100
    cum_bal += m_pnl
    total_trades_count += len(m_list)
    total_wins_count += len([t for t in m_list if t["pnl"] > 0])

    print(f"📅 {m_title}:")
    print(f" • عدد الصفقات: {len(m_list)}")
    if m_list:
        for t in m_list:
            st = "✅ ربح" if t["pnl"] > 0 else "❌ وقف"
            print(f"   ▫️ [{t['time']}] {t['strat']}: {t['ret']:+.1f}% = {t['pnl']:+,.2f}$ ({st})")
    else:
        print("   ▫️ لا توجد صفقات منفذة (السوق كان خارج شروط الأمان المؤسسي)")
    print(f" • صافي ربح الشهر: {m_pnl:+,.2f}$ دولار ({pct:+.1f}%)")
    print(f" • رصيد المحفظة بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 ملخص الأداء الإجمالي لآخر 6 شهور:")
print(f"• رأس المال الابتدائي: $1,000.00 دولار")
print(f"• الرصيد النهائي الصافي بيدك: ${cum_bal:,.2f} دولار")
print(f"• إجمالي صافي الأرباح: {cum_bal - 1000.0:+,.2f}$ دولار")
print(f"• نسبة النمو الإجمالي للمحفظة: {(cum_bal - 1000.0)/1000.0 * 100:+.1f}%!")
print(f"• إجمالي عدد الصفقات: {total_trades_count} صفقة (نسبة الفوز: {total_wins_count/total_trades_count*100:.1f}%)" if total_trades_count > 0 else "")
print("═════════════════════════════════════════════════════════════════")
