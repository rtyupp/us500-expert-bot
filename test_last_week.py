"""محاكاة كاملة ودقيقة لاختبار أداء البوت في الأسبوع الماضي (16 - 23 أكتوبر 2026)."""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
from capital_trader import client
import strategy as S
import pandas as pd
import numpy as np

c_1h = client.get_prices("BTCUSD", resolution="HOUR", max_candles=250)
c_4h = client.get_prices("BTCUSD", resolution="HOUR_4", max_candles=150)
c_1d = client.get_prices("BTCUSD", resolution="DAY", max_candles=100)

df_1h = pd.DataFrame(c_1h)
df_4h = pd.DataFrame(c_4h)
df_1d = pd.DataFrame(c_1d)

df_1h["time"] = pd.to_datetime(df_1h["time"])
df_4h["time"] = pd.to_datetime(df_4h["time"])
df_1d["time"] = pd.to_datetime(df_1d["time"])

start_date = pd.to_datetime("2026-10-16 00:00:00")

print("═════════════════════════════════════════════════════════════════")
print("📊 فحص الصفقات المنفذة في الأسبوع الماضي (16 إلى 23 أكتوبر 2026)")
print("═════════════════════════════════════════════════════════════════\n")

slots = {"A": None, "B": None, "C": None, "D": None}
finished_trades = []

for idx in range(30, len(df_1h)):
    curr_t = df_1h.iloc[idx]["time"]
    if curr_t < start_date:
        continue

    slice_1h = df_1h.iloc[:idx+1]
    slice_4h = df_4h[df_4h["time"] <= curr_t]
    slice_1d = df_1d[df_1d["time"] <= curr_t]

    if len(slice_4h) < 25 or len(slice_1d) < 25:
        continue

    high_now = df_1h.iloc[idx]["high"]
    low_now = df_1h.iloc[idx]["low"]

    # 1. تحديث الصفقات النشطة
    for s_id in list(slots.keys()):
        tr = slots[s_id]
        if tr is not None:
            side = tr["side"]
            entry = tr["entry"]
            stop = tr["stop"]
            tp = tr["tp"]
            initial_risk = tr["initial_risk"]

            floating_gain = (high_now - entry) if side == 1 else (entry - low_now)
            # تأمين الصفقة مبكراً عند +0.8R
            if not tr["moved_be"] and floating_gain >= 0.8 * initial_risk:
                tr["stop"] = entry
                tr["moved_be"] = True
                print(f"   🔒 [تأمين الصفقة] نقل الوقف إلى نقطة الدخول ${entry:,.1f} [{s_id}] عند {curr_t}")

            hit = None
            if side == 1:
                if low_now <= tr["stop"]: hit = "STOP"
                elif high_now >= tp: hit = "TARGET"
            else:
                if high_now >= tr["stop"]: hit = "STOP"
                elif low_now <= tp: hit = "TARGET"

            if hit:
                res_r = tr["rr"] if hit == "TARGET" else (0.0 if tr["moved_be"] else -1.0)
                status = "✅ جني ربح كامل" if hit == "TARGET" else ("⚪ خروج برأس المال (تأمين)" if tr["moved_be"] else "❌ ضرب وقف خسارة")
                print(f"   └─> نتيجة [{s_id} - {tr['name']}]: {status} ({res_r:+.2f}R) عند {curr_t}\n")
                finished_trades.append({
                    "id": s_id, "name": tr["name"], "result": res_r, "win": res_r > 0, "be": tr["moved_be"] and res_r == 0
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
                "time": curr_t
            }
            side_str = "🟢 شراء (BUY)" if sig.side == 1 else "🔴 بيع (SELL)"
            print(f"[{curr_t}] {side_str} [{s_id} - {sig.spec.name}]")
            print(f"      سعر الدخول: ${sig.price:,.1f} | الوقف: ${sig.stop_level:,.1f} | الهدف: ${sig.target_level:,.1f} (1:{rr})")

# تفقد إذا كان هناك صفقات ما زالت مستمرة حتى الآن
still_active = [v for v in slots.values() if v is not None]

print("═════════════════════════════════════════════════════════════════")
print(f"📊 ملخص أداء الأسبوع الماضي (16 - 23 أكتوبر 2026):")
print(f"• إجمالي الصفقات التي تم فتحها: {len(finished_trades) + len(still_active)}")
print(f"• الصفقات المنتهية: {len(finished_trades)}")
if finished_trades:
    wins = [t for t in finished_trades if t["win"]]
    be = [t for t in finished_trades if t["be"]]
    losses = [t for t in finished_trades if t["result"] < 0]
    net_r = sum(t["result"] for t in finished_trades)
    print(f"• الصفقات الرابحة: {len(wins)} ({len(wins)/len(finished_trades)*100:.1f}%)")
    print(f"• الصفقات المتعادلة برأس المال (Break-Even): {len(be)}")
    print(f"• الصفقات الخاسرة: {len(losses)}")
    print(f"• نسبة النجاة من الخسارة (فوز + تأمين): {(len(wins)+len(be))/len(finished_trades)*100:.1f}%")
    print(f"• صافي العائد المحقق: {net_r:+.2f} R")

if still_active:
    print(f"\n• الصفقات المستمرة حالياً:")
    for sa in still_active:
        print(f"   ▫️ [{sa['id']}] {sa['name']} مفتوحة عند ${sa['entry']:,.1f}")
print("═════════════════════════════════════════════════════════════════")
