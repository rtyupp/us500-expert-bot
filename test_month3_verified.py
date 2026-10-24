"""فحص واختبار استراتيجيات البوت ورادار الحيتان على الشهر الماضي تحديداً (من 23 سبتمبر إلى 23 أكتوبر 2026).
يحسب كل صفقة بالتوقيت، السعر، النتيجة، والأرباح بالدولار على رأس مال 40$.
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
import pandas as pd
import numpy as np

# جلب بيانات الشموع الحقيقية
df_4h = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_4h.csv")
df_4h["time"] = pd.to_datetime(df_4h["ts"])
df_1d = pd.read_csv("C:/Users/lsyry/projects/bitcoin-expert-bot/btc_1d.csv")
df_1d["time"] = pd.to_datetime(df_1d["ts"])

# الشهر الماضي: من 23 سبتمبر 2026 إلى 23 أكتوبر 2026
start_dt = pd.to_datetime("2026-09-23 00:00:00+00:00")
end_dt = pd.to_datetime("2026-10-23 00:00:00+00:00")

sub_4h = df_4h[(df_4h["time"] >= start_dt) & (df_4h["time"] <= end_dt)].reset_index(drop=True)

print("═════════════════════════════════════════════════════════════════")
print("📊 اختبار أداء البوت ورادار الحيتان على الشهر الماضي (23 سبتمبر - 23 أكتوبر 2026)")
print("═════════════════════════════════════════════════════════════════")
print(f"• بداية الشهر: {sub_4h.iloc[0]['time']} بسعر ${sub_4h.iloc[0]['open']:,.1f}")
print(f"• قمة الشهر: ${sub_4h['high'].max():,.1f} بتاريخ {sub_4h.loc[sub_4h['high'].idxmax()]['time']}")
print(f"• قاع الشهر: ${sub_4h['low'].min():,.1f} بتاريخ {sub_4h.loc[sub_4h['low'].idxmin()]['time']}")
print(f"• نهاية الشهر: {sub_4h.iloc[-1]['time']} بسعر ${sub_4h.iloc[-1]['close']:,.1f}")
chg = (sub_4h.iloc[-1]["close"] - sub_4h.iloc[0]["open"]) / sub_4h.iloc[0]["open"] * 100
print(f"• حركة السوق الصافية: {chg:+.1f}% (شهر هابط ومتذبذب بمدى تذبذب يفوق 7,400 دولار)\n")

# حساب المؤشرات
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

# فلتر الدايفرجنس السلبي: السعر يخترق قمة لكن MFI هابط
highest_mfi_20 = mfi.rolling(20).max().shift(1)
is_mfi_divergence = (c4 > h4.rolling(20).max().shift(1)) & (mfi < highest_mfi_20 - 5.0)

# الإشارات المؤسسية المعتمدة في البوت:
# [B] الترند المؤسسي
jesse_buy = (c4 > bb_up) & (c4 > span_a) & (c4 > span_b) & (c4 > e200) & (er >= 0.35) & (mfi >= 50) & (~is_mfi_divergence)

# [C] كنس السيولة SMC 30
lo30 = l4.rolling(30).min().shift(1)
smc_buy = (l4 < lo30) & (c4 > lo30) & (c4 > o4) & (c4 > e100_4h if 'e100_4h' in locals() else c4 > c4.ewm(span=100, adjust=False).mean())

# [D] رادار حركة الحيتان
whale_dump = (h4 >= bb_up) & (mfi < 48) & (c4 < o4)
whale_pump = (l4 <= bb_lo) & (mfi > 52) & (c4 > o4)

# محاكاة الصفقات المحددة للشهر الماضي فقط
CONTRACT_SIZE = 0.003
trades = []
slots = {"B": None, "C": None, "D": None}

for i in range(100, len(df_4h)):
    t = df_4h.iloc[i]["time"]
    if t < start_dt or t > end_dt:
        continue

    # 1. متابعة الصفقات المفتوحة
    # فحص B
    tr_b = slots["B"]
    if tr_b is not None:
        if c4.iloc[i] < ma20.iloc[i]:
            ret = (c4.iloc[i] - tr_b["ep"]) / tr_b["ep"] * 100
            pnl = (c4.iloc[i] - tr_b["ep"]) * CONTRACT_SIZE
            trades.append({"name": "الترند المؤسسي [B]", "time": tr_b["time"], "exit_time": str(t)[:16], "entry": tr_b["ep"], "exit": c4.iloc[i], "ret": ret, "pnl": pnl})
            slots["B"] = None

    # فحص D (رادار الحيتان)
    tr_d = slots["D"]
    if tr_d is not None:
        side_d = tr_d["side"]
        hit_d = None
        exit_d = tr_d["ep"]
        if side_d == 1:
            if l4.iloc[i] <= tr_d["sp"]: hit_d = "STOP"; exit_d = tr_d["sp"]
            elif h4.iloc[i] >= tr_d["tp"]: hit_d = "TARGET"; exit_d = tr_d["tp"]
        else:
            if h4.iloc[i] >= tr_d["sp"]: hit_d = "STOP"; exit_d = tr_d["sp"]
            elif l4.iloc[i] <= tr_d["tp"]: hit_d = "TARGET"; exit_d = tr_d["tp"]

        if hit_d:
            ret = side_d * (exit_d - tr_d["ep"]) / tr_d["ep"] * 100
            pnl = side_d * (exit_d - tr_d["ep"]) * CONTRACT_SIZE
            trades.append({"name": "رادار الحيتان [D]", "time": tr_d["time"], "exit_time": str(t)[:16], "entry": tr_d["ep"], "exit": exit_d, "ret": ret, "pnl": pnl})
            slots["D"] = None

    # 2. فتح صفقات جديدة
    if slots["B"] is None and jesse_buy.iloc[i] and not jesse_buy.iloc[i-1]:
        slots["B"] = {"ep": c4.iloc[i], "time": str(t)[:16]}
        print(f"[{str(t)[:16]}] 🟢 فتح صفقة شراء [الترند المؤسسي B] عند ${c4.iloc[i]:,.1f}")

    if slots["D"] is None:
        s_d = 0
        if whale_pump.iloc[i] and not whale_pump.iloc[i-1]: s_d = 1
        elif whale_dump.iloc[i] and not whale_dump.iloc[i-1]: s_d = -1
        if s_d != 0:
            sp_d = c4.iloc[i] - s_d * 1.5 * atr4.iloc[i]
            tp_d = c4.iloc[i] + s_d * 2.5 * atr4.iloc[i]
            slots["D"] = {"side": s_d, "ep": c4.iloc[i], "sp": sp_d, "tp": tp_d, "time": str(t)[:16]}
            s_name = "شراء مع تجميع الحيتان 🟢" if s_d == 1 else "بيع مع تصريف الحيتان 🔴"
            print(f"[{str(t)[:16]}] 🐋 فتح صفقة {s_name} عند ${c4.iloc[i]:,.1f}")

print("\n═════════════════════════════════════════════════════════════════")
print("📋 الصفقات المغلقة في الشهر الماضي:")
print("═════════════════════════════════════════════════════════════════")
for tr in trades:
    st = "✅ ربح" if tr["pnl"] > 0 else "❌ وقف"
    print(f"• [{tr['time']}] {tr['name']} -> الدخول: ${tr['entry']:,.1f} | الخروج: ${tr['exit']:,.1f} | {st} ({tr['ret']:+.1f}% = {tr['pnl']:+.2f}$)")

still_open = [k for k, v in slots.items() if v is not None]
if still_open:
    print(f"\n• صفقات لا تزال مفتوحة بنهاية الشهر: {still_open}")

tot_profit = sum(t["pnl"] for t in trades)
print("\n═════════════════════════════════════════════════════════════════")
print(f"🏆 ملخص أداء الشهر الماضي (23 سبتمبر - 23 أكتوبر 2026):")
print(f"• رصيد البداية: $40.00 دولار")
print(f"• إجمالي الصفقات: {len(trades)} صفقة")
wins = [t for t in trades if t["pnl"] > 0]
losses = [t for t in trades if t["pnl"] <= 0]
print(f"• الصفقات الرابحة: {len(wins)}")
print(f"• الصفقات الخاسرة: {len(losses)}")
print(f"• صافي الربح الصافي بالدولار: {tot_profit:+.2f}$ دولار")
print(f"• نسبة نمو المحفظة في هذا الشهر الهابط: {tot_profit/40*100:+.1f}%")
print(f"• الرصيد بنهاية الشهر: ${40.0 + tot_profit:,.2f} دولار")
print("═════════════════════════════════════════════════════════════════")
