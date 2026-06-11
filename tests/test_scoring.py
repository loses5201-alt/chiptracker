"""
評分引擎單元測試 — 鎖住 s1~s6 與潛伏/做空評分的關鍵行為。

為什麼要有這份:評分是整個系統的核心,之後每次依回測調權重,
跑一次測試就知道有沒有把「已驗證的行為」改壞(例如連續化、防飽和、退中性)。

執行:python -m unittest discover -s tests -v
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetcher import scoring  # noqa: E402


class TestS1Institutional(unittest.TestCase):
    """s1 法人:tanh 連續化(2026-06 修正:原線性 4.6% 即滿分,discrim=0)。"""

    def test_缺資料回零(self):
        self.assertEqual(scoring.score_institutional({}, 1000)[0], 0)
        self.assertEqual(scoring.score_institutional({"total": 100}, 0)[0], 0)

    def test_中性點(self):
        s, _ = scoring.score_institutional({"total": 0}, 1000)
        self.assertEqual(s, 11.0)   # 無買賣超 = 中性 11

    def test_連續性不飽和(self):
        """不同買超強度必須拿到不同分數(這就是 discrim=0 的修正)。"""
        ratios = [0.01, 0.03, 0.046, 0.06, 0.12]
        got = [scoring.score_institutional({"total": r * 1000}, 1000)[0] for r in ratios]
        self.assertEqual(got, sorted(got))           # 單調遞增
        self.assertEqual(len(set(got)), len(got))    # 各不相同(舊版 0.046 起全 22)
        self.assertLess(got[-1], 22)                 # 12% 都還沒頂滿

    def test_賣超對稱遞減(self):
        s, _ = scoring.score_institutional({"total": -30}, 1000)
        self.assertLess(s, 11)
        self.assertGreaterEqual(s, 0)

    def test_外資投信同買註記(self):
        _, note = scoring.score_institutional({"total": 50, "foreign": 30, "trust": 20}, 1000)
        self.assertEqual(note, "外資投信同買")


class TestS3Fundamental(unittest.TestCase):
    """s3 基本面:tanh 防飽和(2026-06 修正:原 yoy≥50% 即滿分,mean 19.65/20)。"""

    def test_缺資料退中性(self):
        self.assertEqual(scoring.score_fundamental(None)[0], 8)

    def test_零成長即中性(self):
        self.assertEqual(scoring.score_fundamental({"yoy": 0})[0], 8.0)

    def test_高成長仍分得出高下(self):
        s50 = scoring.score_fundamental({"yoy": 50})[0]
        s100 = scoring.score_fundamental({"yoy": 100})[0]
        s200 = scoring.score_fundamental({"yoy": 200})[0]
        self.assertLess(s50, s100)
        self.assertLess(s100, s200)
        self.assertLess(s200, 20)   # 200% 也不頂滿

    def test_衰退不歸零(self):
        s, _ = scoring.score_fundamental({"yoy": -40})
        self.assertGreater(s, 0)    # 保留鑑別度,不一路扣死


class TestS5TopicNews(unittest.TestCase):
    def test_無題材退中性(self):
        self.assertEqual(scoring.score_topic_news(None, 99)[0], 6)

    def test_熱與爆熱分得開(self):
        s6_ = scoring.score_topic_news("AI", 6)[0]
        s17 = scoring.score_topic_news("AI", 17)[0]
        s30 = scoring.score_topic_news("AI", 30)[0]
        self.assertLess(s6_, s17)
        self.assertLess(s17, s30)


class TestS2Margin(unittest.TestCase):
    def test_缺資料退中性(self):
        self.assertEqual(scoring.score_margin_short({}, {})[0], 4)

    def test_散戶獨推扣分(self):
        """融資暴增(>10%)但法人沒買 = 散戶獨推,要低於中性。"""
        mg = {"margin_bal": 1200, "margin_prev": 1000, "short_bal": 0, "short_prev": 0}
        s, note = scoring.score_margin_short(mg, {"total": -10})
        self.assertLess(s, 4)
        self.assertIn("散戶獨推", note)


class TestS6Momentum(unittest.TestCase):
    def test_無歷史退中性(self):
        s, rsi, pos, _ = scoring.score_momentum([], 0, None)
        self.assertEqual(s, 8)

    def test_多頭排列拿高分(self):
        closes = [100 + i for i in range(30)]   # 連漲:站上雙均線、均線多頭
        s, _, _, _ = scoring.score_momentum(closes, 2000, 1000)
        self.assertGreaterEqual(s, 10)


class TestStealthAndShort(unittest.TestCase):
    def test_潛伏_高位追高要扣分(self):
        """60日區間位置 >80 的高位股,潛伏分要低(不追高是潛伏核心)。"""
        rising = [100 + i * 2 for i in range(70)]    # 一路漲到區間頂
        base = [100 + (i % 5) * 0.3 for i in range(70)]  # 低位盤整打底
        s_hi, _ = scoring.score_stealth({"total": 50}, {}, rising, 1500, 1000)
        s_lo, _ = scoring.score_stealth({"total": 50}, {}, base, 1500, 1000)
        self.assertLess(s_hi, s_lo)

    def test_做空_乖離高且營收衰退加分(self):
        closes = [100] * 40 + [100 + i * 3 for i in range(20)]   # 急拉乖離大
        s, reasons = scoring.score_short({"total": -50}, {}, closes, 1000, 800,
                                         {"yoy": -15}, topic=None)
        self.assertGreaterEqual(s, 45)
        self.assertTrue(any("乖離" in r or "營收" in r for r in reasons))

    def test_分數界線(self):
        self.assertEqual(scoring.grade(70), "strong")
        self.assertEqual(scoring.grade(55), "mid")
        self.assertEqual(scoring.grade(54), "watch")
        self.assertEqual(scoring.stealth_grade(55), "strong")
        self.assertEqual(scoring.short_grade(60), "strong")


if __name__ == "__main__":
    unittest.main()
