import dataclasses as dc
import unittest

from engine.contracts import load_inputs
from engine.pipeline import analyze

DATA = "data"
G2 = "tests/golden/G2"


def load(path=G2, **building_overrides):
    inp = load_inputs(path, DATA)
    if building_overrides:
        inp = dc.replace(inp, building=dc.replace(inp.building, **building_overrides))
    return inp


class TestThreshold(unittest.TestCase):
    def test_기준_미만이면_아무것도_빼지_않는다(self):
        """공고: 50세대 이상일 때 의무. 미만이면 커뮤니티 면적이 0 이다."""
        inp = load(floors_residential=(1, 2))
        a = analyze(inp, "supply")
        self.assertLess(a.community.households_before, 50)
        self.assertEqual(a.community.required_m2, 0.0)
        self.assertEqual(a.community.removed_count, 0)
        self.assertEqual(len(a.units), a.community.households_before)

    def test_기준_이상이면_세대를_전환한다(self):
        a = analyze(load(), "supply")
        self.assertGreaterEqual(a.community.households_before, 50)
        self.assertGreater(a.community.removed_count, 0)


class TestFixedPoint(unittest.TestCase):
    """세대수가 면적을 정하고 면적이 세대수를 줄이는 순환. 고정점까지 간다."""

    def test_확보면적이_필요면적_이상에서_멈춘다(self):
        a = analyze(load(), "supply")
        c = a.community
        self.assertTrue(c.satisfied)
        self.assertGreaterEqual(c.provided_m2, c.required_m2)

    def test_한_세대_덜_빼면_모자란다(self):
        """정확히 최소 개수만 뺐는지 — 과도하게 빼면 세대수를 부당하게 깎는다."""
        a = analyze(load(), "supply")
        c = a.community
        unit_m2 = c.provided_m2 / c.removed_count
        one_less_provided = c.provided_m2 - unit_m2
        one_less_required = (c.households + 1) * 1.0
        self.assertLess(one_less_provided, one_less_required)

    def test_손으로_검산한_값(self):
        """80세대 × 21.6㎡ 유닛. 4세대 전환 → 확보 86.4㎡ ≥ 필요 76㎡."""
        a = analyze(load(), "supply")
        c = a.community
        self.assertEqual(c.households_before, 80)
        self.assertEqual(c.removed_count, 4)
        self.assertEqual(c.provided_m2, 86.4)
        self.assertEqual(c.required_m2, 76.0)
        self.assertEqual(c.households, 76)
        self.assertEqual(len(a.units), 76)


class TestPlacement(unittest.TestCase):
    def test_가장_낮은_주거층에서_뺀다(self):
        """공고 '마. 지상 1층을 원칙으로 하되'."""
        a = analyze(load(), "supply")
        self.assertEqual(a.community.floor, min(f.floor for f in a.floors))

    def test_전환된_자리는_사유가_남는다(self):
        a = analyze(load(), "supply")
        low = min(a.floors, key=lambda f: f.floor)
        tagged = [c for c in low.commons if c.reason == "community"]
        self.assertEqual(len(tagged), a.community.removed_count)
        self.assertIn("주민공동시설", tagged[0].label)
        self.assertIn("공고", tagged[0].detail)

    def test_다른_층은_그대로다(self):
        a = analyze(load(), "supply")
        counts = {f.floor: len(f.units) for f in a.floors}
        low = min(counts)
        others = {k: v for k, v in counts.items() if k != low}
        self.assertEqual(len(set(others.values())), 1)
        self.assertLess(counts[low], next(iter(others.values())))


class TestOffices(unittest.TestCase):
    def test_세대수에_따라_경비실_관리사무소_의무가_생긴다(self):
        a = analyze(load(), "supply")
        self.assertIn("경비실", a.community.offices)      # 80세대 ≥ 50
        self.assertNotIn("관리사무소", a.community.offices)  # 150 미만

    def test_면적을_지어내지_않는다(self):
        """공고가 경비실·관리사무소 면적 기준을 제시하지 않는다. 설치 여부만 낸다."""
        a = analyze(load(), "supply")
        q = a.quantities["community"]
        self.assertEqual(q["offices"], ["경비실"])
        self.assertNotIn("office_area", q)


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_세대가_빠진다(self):
        a = analyze(load(), "supply")
        b = analyze(load(), "supply")
        self.assertEqual(a.units, b.units)
        self.assertEqual(a.community, b.community)


if __name__ == "__main__":
    unittest.main()
