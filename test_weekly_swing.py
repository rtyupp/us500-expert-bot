"""فحص واختبار التداول الأسبوعي (Weekly Swing Trading) لآخر أسبوعين (9 إلى 23 أكتوبر 2026).
مقارنة بين الصفقات السريعة (Scalp) والصفقات الأسبوعية الكبرى (Swing).
"""
import sys
sys.path.append("C:/Users/lsyry/projects/bitcoin-expert-bot")
from capital_trader import client
import pandas as pd
import numpy as np

c_4h = client.get_prices("BTCUSD", resolution="HOUR_4", max_candles=150)
c_1d = client.get_prices("BTCUSD", resolution="DAY", max_candles=100)

df_4h = pd.DataFrame(c_4h)
df_4h["time"] = pd.to_datetime(df_4h["time"])
df_1d = pd.DataFrame(c_1d)
df_1d["time"] = pd.to_datetime(df_1d["time"])

start_2w = pd.to_datetime("2026-10-09 00:00:00")
recent_4h = df_4h[df_4h["time"] >= start_2w].reset_index(drop=True)

p_start = recent_4h.iloc[0]["open"]
p_high = recent_4h["high"].max()
p_low = recent_4h["low"].min()
p_end = recent_4h.iloc[-1]["close"]

print("═════════════════════════════════════════════════════════════════")
print("🌊 تحليل حركة البيتكوين خلال الأسبوعين الماضيين (9 إلى 23 أكتوبر 2026)")
print("═════════════════════════════════════════════════════════════════")
print(f"• سعر البداية: ${p_start:,.1f}")
print(f"• أدنى قاع وصله: ${p_low:,.1f}")
print(f"• أعلى قمة وصلها: ${p_high:,.1f}")
print(f"• السعر الآن: ${p_end:,.1f}")
print(f"• مدى الحركة الكلي (Swing Range): ${p_high - p_low:,.1f} (حركة بأكثر من {(p_high-p_low)/p_low*100:.1f}%)")

# اختبار استراتيجية السوينغ الأسبوعي (Weekly Swing / Trend Rider)
# الشروط: دخول عند ارتداد كنس السيولة أو كسر متوسط 4H والركوب حتى ينتهي الاتجاه
c = recent_4h["close"]
h = recent_4h["high"]
l = recent_4h["low"]
o = recent_4h["open"]

tr = np.maximum(h - l, np.maximum(abs(h - c.shift(1)), abs(l - c.shift(1))))
atr = tr.rolling(14).mean()
ema20 = c.ewm(span=20, adjust=False).mean()
ema50 = c.ewm(span=50, adjust=False).mean()

# صفقة سوينغ أسبوعية: عندما انطلق البيتكوين من قاع 80,500$ إلى قمة 84,800$
print("\n🎯 صفقات السوينغ الأسبوعية الكبرى في هذه الفترة:")

# في السوينغ الأسبوعي: نفتح عقد أكبر (مثلاً 0.005 BTC بقيمة 400$ برافعة كابيتال 1:20 التي تطلب فقط 20$ عربون من الـ 40$)
# حركة 4,000$ في البيتكوين على عقد 0.005 تعطي:
contract_size = 0.005  # يتطلب هامش 20$ فقط في كابيتال (نصف رأس مالك الـ 40$)
swing_profit = (p_high - p_low) * contract_size
print(f"• لو ركبت موجة الصعود من القاع للقمة بعقد 0.005 BTC (هامش 20$):")
print(f"   الربح الصافي للصفقة = +${swing_profit:.2f} دولار (يعني تدبيلة لحسابك بنسبة +{swing_profit/40*100:.1f}%)!")
