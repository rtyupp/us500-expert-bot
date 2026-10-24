"""محاكاة تفصيلية لجميع صفقات البوت على مدار الشهور الثلاثة الأخيرة شمعة بشمعة.
يحسب الربح بالدولار على رأس مال 40 دولار في كل شهر.
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np
import strategy as S

df_1h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1h.csv")
df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
df_1d = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1d.csv")

for df in [df_1h, df_4h, df_1d]:
    df["time"] = pd.to_datetime(df["ts"])

# المحاكاة لآخر 3 شهور
start_dt = pd.to_datetime("2026-07-23 00:00:00+00:00")
months = [
    ("الشهر الأول (23 يوليو - 23 أغسطس 2026)", pd.to_datetime("2026-07-23 00:00:00+00:00"), pd.to_datetime("2026-08-23 00:00:00+00:00")),
    ("الشهر الثاني (23 أغسطس - 23 سبتمبر 2026)", pd.to_datetime("2026-08-23 00:00:00+00:00"), pd.to_datetime("2026-09-23 00:00:00+00:00")),
    ("الشهر الثالث (23 سبتمبر - 23 أكتوبر 2026)", pd.to_datetime("2026-09-23 00:00:00+00:00"), pd.to_datetime("2026-10-23 00:00:00+00:00")),
]

# حجم العقد المعتمد لرأس مال 40$ برافعة كابيتال (0.003 BTC بهامش 12$ فقط)
CONTRACT_SIZE = 0.003

# محاكاة خطوة بخطوة لشمعات 1H
slots = {"A": None, "B": None, "C": None, "D": None}
month_trades = {0: [], 1: [], 2: []}

# فلترة البيانات من بداية الشهور الثلاثة
idx_start = df_1h[df_1h["time"] >= start_dt].index[0]

for idx in range(idx_start, len(df_1h)):
    curr_t = df_1h.iloc[idx]["time"]
    
    # تحديد رقم الشهر
    m_idx = 0 if curr_t < months[0][2] else (1 if curr_t < months[1][2] else 2)

    slice_1h = df_1h.iloc[:idx+1]
    slice_4h = df_4h[df_4h["time"] <= curr_t]
    slice_1d = df_1d[df_1d["time"] <= curr_t]

    high_now = df_1h.iloc[idx]["high"]
    low_now = df_1h.iloc[idx]["low"]
    close_now = df_1h.iloc[idx]["close"]

    # 1. متابعة الصفقات النشطة
    for s_id in list(slots.keys()):
        tr = slots[s_id]
        if tr is not None:
            side = tr["side"]
            entry = tr["entry"]
            stop = tr["stop"]
            tp = tr["tp"]
            initial_risk = tr["initial_risk"]

            floating_gain = (high_now - entry) if side == 1 else (entry - low_now)
            if not tr["moved_be"] and floating_gain >= 0.8 * initial_risk:
                tr["stop"] = entry
                tr["moved_be"] = True

            hit = None
            exit_px = entry
            if side == 1:
                if low_now <= tr["stop"]: hit = "STOP"; exit_px = tr["stop"]
                elif high_now >= tp: hit = "TARGET"; exit_px = tp
            else:
                if high_now >= tr["stop"]: hit = "STOP"; exit_px = tr["stop"]
                elif low_now <= tp: hit = "TARGET"; exit_px = tp

            if hit:
                # حساب الربح بالدولار
                dol_pnl = side * (exit_px - entry) * CONTRACT_SIZE
                res_r = tr["rr"] if hit == "TARGET" else (0.0 if tr["moved_be"] else -1.0)
                month_trades[tr["m_idx"]].append({
                    "id": s_id, "name": tr["name"], "entry": entry, "exit": exit_px,
                    "pnl": dol_pnl, "r": res_r, "win": dol_pnl > 0, "be": tr["moved_be"] and dol_pnl == 0
                })
                slots[s_id] = None

    # 2. فحص إشارات جديدة
    sigs = S.scan_signals(slice_1h, slice_4h, slice_1d)
    for sig in sigs:
        s_id = sig.spec_id
        if slots[s_id] is None:
            init_risk = abs(sig.price - sig.stop_level)
            rr = round(abs(sig.target_level - sig.price) / init_risk, 2)
            slots[s_id] = {
                "id": s_id, "name": sig.spec.name, "side": sig.side,
                "entry": sig.price, "stop": sig.stop_level, "tp": sig.target_level,
                "initial_risk": init_risk, "rr": rr, "moved_be": False,
                "time": curr_t, "m_idx": m_idx
            }

print("═════════════════════════════════════════════════════════════════")
print("💰 ملخص الأرباح الصافية لكل شهر على رأس مال 40 دولار:")
print("═════════════════════════════════════════════════════════════════\n")

cum_balance = 40.0
for i, (m_title, _, _) in enumerate(months):
    tr_list = month_trades[i]
    wins = [t for t in tr_list if t["win"]]
    be = [t for t in tr_list if t["be"]]
    losses = [t for t in tr_list if not t["win"] and not t["be"]]
    month_profit = sum(t["pnl"] for t in tr_list)
    return_pct = (month_profit / cum_balance) * 100
    cum_balance += month_profit

    print(f"📊 {m_title}:")
    print(f" • عدد الصفقات: {len(tr_list)} (رابحة: {len(wins)} | تعادل رأس مال: {len(be)} | خاسرة: {len(losses)})")
    print(f" • صافي الربح بالدولار: {month_profit:+.2f}$ دولار")
    print(f" • نسبة العائد الشهري: {return_pct:+.1f}%")
    print(f" • رصيد المحفظة بنهاية هذا الشهر: ${cum_balance:,.2f} دولار\n")

print("═════════════════════════════════════════════════════════════════")
print(f"🏆 النتيجة الإجمالية بعد 3 أشهر كاملة:")
print(f"• رأس المال الابتدائي: $40.00 دولار")
print(f"• الرصيد النهائي: ${cum_balance:,.2f} دولار")
print(f"• إجمالي صافي الأرباح: {cum_balance - 40.0:+.2f}$ دولار (نمو كلي {(cum_balance-40)/40*100:+.1f}%)")
print("═════════════════════════════════════════════════════════════════")
