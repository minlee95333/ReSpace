import unittest

from engine.contracts import ContractError, Window, load_inputs
from engine.corridor import generate
from engine.daylight import evaluate, window_length_mm
from engine.daylight import _segment_on_rect
from engine.egress import compute
from engine.grid import gridify
from engine.place import place

DATA = "data"


def run(building_dir, strategy="supply"):
    inp = load_inputs(building_dir, DATA)
    grid = gridify(inp.floors[0], inp.rules)
    corridor = generate(inp.floors[0], grid, inp.rules, inp.units)
    em = compute(inp.floors[0], grid, inp.rules, inp.building)
    pr = place(grid, corridor, em, inp.rules, inp.units, strategy)
    return inp, pr, evaluate(inp.floors[0], inp.rules, inp.units, pr)


class TestSegmentGeometry(unittest.TestCase):
    def test_수평창은_사각형_아래위_변에만_걸린다(self):
        w = Window((0, 0), (36000, 0), 900, 1500)
        self.assertEqual(_segment_on_rect(w, (0, 0, 3000, 6000)), 3000)     # 아래변
        self.assertEqual(_segment_on_rect(w, (0, 600, 3000, 6000)), 0)      # 떨어짐

    def test_수직창(self):
        w = Window((0, 0), (0, 21000), 900, 1500)
        self.assertEqual(_segment_on_rect(w, (0, 0, 3000, 6000)), 6000)     # 좌변
        self.assertEqual(_segment_on_rect(w, (3000, 0, 3000, 6000)), 0)

    def test_부분_겹침(self):
        w = Window((30000, 21000), (30600, 21000), 900, 1500)
        self.assertEqual(_segment_on_rect(w, (30000, 15000, 3000, 6000)), 600)

    def test_대각선_창은_명시적으로_실패한다(self):
        # 조용히 0 을 돌려주면 유닛이 부당하게 탈락한다.
        w = Window((0, 0), (3000, 3000), 900, 1500)
        with self.assertRaises(ContractError):
            _segment_on_rect(w, (0, 0, 3000, 6000))


class TestG3(unittest.TestCase):
    """채광 탈락 두 경로를 만드는 평면."""

    def setUp(self):
        self.inp, self.pr, self.dl = run("tests/golden/G3")

    def test_탈락_건수(self):
        self.assertEqual(self.pr.count, 24)
        self.assertEqual(self.dl.kept, 17)
        self.assertEqual(len(self.dl.rejected), 7)

    def test_두_사유가_모두_나온다(self):
        reasons = {}
        for r in self.dl.rejected:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        self.assertEqual(reasons, {"no_window": 6, "daylight_short": 1})

    def test_창면적_부족_유닛의_수치(self):
        short = [r for r in self.dl.rejected if r.reason == "daylight_short"]
        self.assertEqual(len(short), 1)
        # 창 600mm × 높이 1500mm = 0.9㎡ < 필요 1.8㎡ (18㎡의 1/10)
        self.assertIn("0.90", short[0].detail)
        self.assertIn("1.80", short[0].detail)

    def test_통과_유닛은_모두_기준_이상(self):
        for u in self.dl.units:
            self.assertGreaterEqual(u.daylight_ratio, 0.1)
            self.assertGreater(u.window_len_mm, 0)
            self.assertIsNotNone(u.depth_from_window_m)


class TestRatio(unittest.TestCase):
    def test_모서리_유닛은_두_면에서_창을_받는다(self):
        inp, _, dl = run("tests/golden/G2")
        corner = [u for u in dl.units if u.rect_mm[:2] == (0, 0)]
        self.assertEqual(len(corner), 1)
        # 아래변 3000 + 좌변 6000
        self.assertEqual(corner[0].window_len_mm, 9000)
        self.assertEqual(corner[0].daylight_ratio, 0.75)

    def test_중간_유닛은_한_면만(self):
        inp, _, dl = run("tests/golden/G2")
        mid = [u for u in dl.units if u.rect_mm[0] == 15000 and u.rect_mm[1] == 0]
        self.assertTrue(mid)
        self.assertEqual(mid[0].window_len_mm, 3000)
        self.assertEqual(mid[0].daylight_ratio, 0.25)


class TestFacadeAnchor(unittest.TestCase):
    """⑤ 가 유닛을 외벽에 붙이므로 창에 면하는 유닛이 나온다."""

    def test_에스키스는_전부_통과한다(self):
        _, pr, dl = run("data/buildings/esquisse-gasan")
        self.assertEqual(pr.count, dl.kept)
        self.assertEqual(len(dl.rejected), 0)

    def test_유닛이_외벽에_닿는다(self):
        inp, _, dl = run("data/buildings/esquisse-gasan")
        for u in dl.units:
            self.assertGreater(window_length_mm(inp.floors[0], u.rect_mm), 0)


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_판정(self):
        a = run("tests/golden/G3")[2]
        b = run("tests/golden/G3")[2]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
