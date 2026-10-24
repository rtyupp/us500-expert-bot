"""مختبر استراتيجية الدخول مع الحيتان (Whale Shadow Trader).
تقتنص:
1. صفقات البيع مع الحيتان (Whale Dump): عندما يضرب السعر قمة صاعدة لكن تدفق السيولة الحقيقي MFI يظهر تصريف الحيتان.
2. صفقات الشراء مع الحيتان (Whale Pump): عندما يكسر السعر قاعاً لكن تدفق السيولة MFI يظهر تجميع الحيتان السري.
فحص شامل لآخر 3 أشهر (23 يوليو - 23 أكتوبر 2026).
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
c4 = df_4h["close"]; h4 = df_4h["high"]; l4 = df_4h["low"]; o4 = df_4h["open"]; v4 = df_4h["volume"]
df_4h["time"] = pd.to_datetime(df_4h["ts"])

# حساب ATR
tr = np.maximum(h4 - l4, np.maximum(abs(h4 - c4.shift(1)), abs(l4 - c4.shift(1))))
atr = tr.rolling(14).mean()

# تدفق السيولة MFI
typ = (h4 + l4 + c4) / 3
raw_m = typ * v4
pos_m = pd.Series(np.where(typ > typ.shift(1), raw_m, 0.0)).rolling(14).sum()
neg_m = pd.Series(np.where(typ < typ.shift(1), raw_m, 0.0)).rolling(14).sum()
mfi = 100 - (100 / (1 + (pos_m / (neg_m + 1e-9))))

ma20 = c4.rolling(20).mean(); std20 = c4.rolling(20).std()
bb_up = ma20 + 2.0 * std20; bb_lo = ma20 - 2.0 * std20

# 1. إشارة تصريف الحيتان (Whale Distribution / Sell Signal):
# السعر يضرب قمة بولينجر العلوية لكن MFI أقل من 45 (الحيتان يصرفون والقطيع يشتري) + شمعة هابطة حمراء
whale_dump = (h4 >= bb_up) & (mfi < 48) & (c4 < o4)

# 2. إشارة تجميع الحيتان (Whale Accumulation / Buy Signal):
# السعر يضرب قاع بولينجر السفلي لكن MFI أعلى من 52 (الحيتان يجمعون خفية) + شمعة صاعدة خضراء
whale_pump = (l4 <= bb_lo) & (mfi > 52) & (c4 > o4)

start_dt = pd.to_datetime("2026-07-23 00:00:00+00:00")
months = [
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

month_trades = {0: [], 1: [], 2: []}
in_pos = False; side = 0; ep = 0.0; sp = 0.0; tp = 0.0; ep_t = ""; cur_m = 0
CONTRACT_SIZE = 0.003

for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < start_dt: continue
    m_idx = 0 if t < months[0][2] else (1 if t < months[1][2] else 2)

    if not in_pos:
        s = 0
        if whale_pump.iloc[i] and not whale_pump.iloc[i-1]: s = 1
        elif whale_dump.iloc[i] and not whale_dump.iloc[i-1]: s = -1

        if s != 0:
            in_pos = True; side = s
            ep = c4.iloc[i]; ep_t = str(t)[:16]; cur_m = m_idx
            sp = ep - side * 1.5 * atr.iloc[i]
            tp = ep + side * 2.5 * atr.iloc[i] # 1:1.67 RR
    else:
        hit = None
        exit_p = ep
        if side == 1:
            if l4.iloc[i] <= sp: hit = "STOP"; exit_p = sp
            elif h4.iloc[i] >= tp: hit = "TARGET"; exit_p = tp
        else:
            if h4.iloc[i] >= sp: hit = "STOP"; exit_p = sp
            elif l4.iloc[i] <= tp: hit = "TARGET"; exit_p = tp

        if hit:
            dol = side * (exit_p - ep) * CONTRACT_SIZE
            ret_pct = side * (exit_p - ep) / ep * 100
            month_trades[cur_m].append({
                "time": ep_t, "side": "شراء (تجميع حيتان) 🟢" if side == 1 else "بيع (تصريف حيتان) 🔴",
                "ret": ret_pct, "pnl": dol, "hit": hit
            })
            in_pos = False

print("═════════════════════════════════════════════════════════════════")
print("🐋 نتائج التداول المباشر مع الحيتان (Whale Shadow Trader) لآخر 3 شهور:")
print("═════════════════════════════════════════════════════════════════\n")

cum_bal = 40.0
for i, (m_title, _, _) in enumerate(months):
    m_list = month_trades[i]
    m_pnl = sum(t["pnl"] for t in m_list)
    pct = (m_pnl / cum_bal) * 100
    cum_bal += m_pnl

    print(f"📅 {m_title}:")
    print(f" • عدد صفقات الحيتان: {len(m_list)}")
    for t in m_list:
        st = "✅ ربح" if t["pnl"] > 0 else "❌ وقف"
        print(f"   ▫️ [{t['time']}] {t['side']} -> {st} ({t['ret']:+.1f}% = {t['pnl']:+.2f}$)")
    print(f" • صافي ربح الشهر: {m_pnl:+.2f}$ دولار ({pct:+.1f}%)")
    print(f" • رصيد المحفظة بنهاية الشهر: ${cum_bal:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 النتيجة الكلية بعد 3 أشهر كاملة من ملاحقة الحيتان:")
print(f"• الرصيد الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي: ${cum_bal:,.2f} دولار")
print(f"• إجمالي الأرباح الصافية: {cum_bal - 40.0:+.2f}$ دولار (نمو كلي {(cum_bal-40)/40*100:+.1f}%)!")
print("═════════════════════════════════════════════════════════════════")
