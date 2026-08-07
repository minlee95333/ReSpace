import dataclasses as dc
import unittest

from engine.caps import compute as compute_caps, verdict
from engine.contracts import ContractError, load_inputs
from engine.pipeline import analyze, residential_floors
from engine.place import new_wall_length_mm

DATA = "data"


def load(building_dir, **rule_overrides):
    inp = load_inputs(building_dir, DATA)
    if rule_overrides:
        inp = dc.replace(inp, rules=dc.replace(inp.rules, **rule_overrides))
    return inp


#: 3축이 모두 도는 상태를 만들기 위한 가상 원단위. 실제 값이 아니다.
SEPTIC = {"septic_persons_per_unit": 1.5, "septic_load_lpcd": 200.0}


class TestFloorExpansion(unittest.TestCase):
    """기준층 1개를 floors_residential 범위만큼 반복한다."""

    def test_G2_는_5개층으로_펼쳐진다(self):
        inp = load("tests/golden/G2")
        self.assertEqual(residential_floors(inp), (1, 2, 3, 4, 5))
        a = analyze(inp, "supply")
        self.assertEqual([f.floor for f in a.floors], [1, 2, 3, 4, 5])
        self.assertEqual(len(a.units), 100)  # 층당 20세대 × 5개층

    def test_범위가_없으면_준_도면만_쓴다(self):
        inp = load("data/buildings/esquisse-gasan")
        self.assertIsNone(inp.building.floors_residential)
        self.assertEqual(residential_floors(inp), (5,))

    def test_층별로_피난_한계가_다시_계산된다(self):
        # 16층 이상 건물의 16층 이상 층은 40m
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(
            inp.building, floors_total=19, floors_residential=(15, 17)))
        a = analyze(inp, "supply")
        limits = {f.floor: f.egress.limit_m for f in a.floors}
        self.assertEqual(limits, {15: 50.0, 16: 40.0, 17: 40.0})

    def test_뒤집힌_범위는_실패한다(self):
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(
            inp.building, floors_residential=(9, 3)))
        with self.assertRaises(ContractError):
            analyze(inp, "supply")

    def test_알수없는_전략은_실패한다(self):
        with self.assertRaises(ContractError):
            analyze(load("tests/golden/G2"), "nope")


class TestCaps(unittest.TestCase):
    def test_G2_는_주차가_병목이다(self):
        a = analyze(load("tests/golden/G2"), "supply")
        self.assertEqual(a.caps.by_axis("plan").value, 100)
        self.assertEqual(a.caps.by_axis("parking").value, 40)  # 20대 ÷ 0.5
        self.assertEqual(a.caps.supply, 40)
        self.assertEqual(a.caps.bottleneck, "parking")

    def test_미확보_축은_숫자를_지어내지_않는다(self):
        a = analyze(load("tests/golden/G2"), "supply")
        septic = a.caps.by_axis("septic")
        self.assertIsNone(septic.value)
        self.assertFalse(a.caps.complete)
        self.assertIn("미확정", septic.blocked_reason)

    def test_주차_미입력이면_주차축이_막힌다(self):
        a = analyze(load("data/buildings/esquisse-gasan"), "supply")
        self.assertIsNone(a.caps.by_axis("parking").value)
        self.assertEqual(a.caps.bottleneck, "plan")

    def test_3축이_모두_돌면_complete(self):
        a = analyze(load("tests/golden/G2", **SEPTIC), "supply")
        self.assertTrue(a.caps.complete)
        self.assertEqual(a.caps.by_axis("septic").value, 100)  # 30㎥ × 3.33
        self.assertEqual(a.caps.supply, 40)
        self.assertEqual(a.caps.bottleneck, "parking")


class TestVerdict(unittest.TestCase):
    def test_세대_0_이면_부적합(self):
        a = analyze(load("tests/golden/G1"), "supply")
        self.assertEqual(a.caps.supply, 0)
        self.assertEqual(a.grade, "부적합")

    def test_미확보_축이_있으면_조건부_검토(self):
        a = analyze(load("tests/golden/G2"), "supply")
        self.assertEqual(a.grade, "조건부 검토")

    def test_인프라가_병목이면_검토_가능(self):
        a = analyze(load("tests/golden/G2", **SEPTIC), "supply")
        self.assertEqual(a.grade, "검토 가능")
        self.assertIn("주차 보강이 선행", " ".join(a.reasons))

    def test_평면이_병목이면_우선검토(self):
        inp = load("tests/golden/G2", **SEPTIC)
        inp = dc.replace(inp, building=dc.replace(inp.building, parking_existing=60))
        a = analyze(inp, "supply")
        self.assertEqual(a.caps.bottleneck, "plan")
        self.assertEqual(a.grade, "우선검토")

    def test_판정에는_반드시_이유가_붙는다(self):
        for case in ("tests/golden/G1", "tests/golden/G2"):
            with self.subTest(case=case):
                a = analyze(load(case), "supply")
                self.assertTrue(a.reasons)


class TestQuantities(unittest.TestCase):
    def test_단가는_들어있지_않다(self):
        q = analyze(load("tests/golden/G2"), "supply").quantities
        flat = repr(q)
        for word in ("cost", "price", "won", "원"):
            self.assertNotIn(word, flat.lower())

    def test_부족분은_평면_상한_기준이다(self):
        a = analyze(load("tests/golden/G2"), "supply")
        p = a.quantities["parking"]
        self.assertEqual(p["required"], 50.0)   # 100세대 × 0.5
        self.assertEqual(p["existing"], 20)
        self.assertEqual(p["shortfall"], 30.0)

    def test_기존_내부벽이_없어_철거물량은_산출_불가(self):
        q = analyze(load("tests/golden/G2"), "supply").quantities
        self.assertIsNone(q["demo_wall_m"])

    def test_신설벽은_기존_구조체_면을_빼고_센다(self):
        a = analyze(load("tests/golden/G2"), "supply")
        f = a.floors[0]
        total = new_wall_length_mm(f.grid, f.units)
        # 유닛 20개 단순 둘레 합은 360m. 외벽·공유면을 빼면 그보다 작아야 한다.
        self.assertLess(total / 1000, 360)
        self.assertGreater(total, 0)

    def test_샤프트가_없으면_거리는_None(self):
        a = analyze(load("tests/golden/G2"), "supply")
        self.assertTrue(all(u.shaft_dist_cells is None for u in a.units))
        self.assertEqual(a.quantities["shaft_reuse_ratio"], 0.0)


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_분석(self):
        a = analyze(load("tests/golden/G3"), "balanced")
        b = analyze(load("tests/golden/G3"), "balanced")
        self.assertEqual(a.caps, b.caps)
        self.assertEqual(a.grade, b.grade)
        self.assertEqual(a.quantities, b.quantities)
        self.assertEqual(a.units, b.units)


if __name__ == "__main__":
    unittest.main()
