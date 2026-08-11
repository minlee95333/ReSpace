import dataclasses as dc
import unittest

from engine.contracts import load_inputs
from engine.corridor import generate
from engine.egress import compute
from engine.grid import CellState, gridify
from engine.place import place

DATA = "data"
ESQUISSE = "data/buildings/esquisse-gasan"


def run(building_dir, strategy="supply", all_cores=None):
    inp = load_inputs(building_dir, DATA)
    rules = inp.rules
    if all_cores is not None:
        rules = dc.replace(rules, egress=dc.replace(rules.egress, all_cores=all_cores))
    grid = gridify(inp.floors[0], rules)
    corridor = generate(inp.floors[0], grid, rules, inp.units)
    em = compute(inp.floors[0], grid, rules, inp.building)
    return grid, em, place(grid, corridor, em, rules, inp.units, strategy)


class TestInvariants(unittest.TestCase):
    def setUp(self):
        self.grid, self.em, self.res = run(ESQUISSE, "supply")

    def test_유닛이_겹치지_않는다(self):
        seen = set()
        for u in self.res.units:
            r0, c0, rows, cols = u.cells
            for r in range(r0, r0 + rows):
                for c in range(c0, c0 + cols):
                    self.assertNotIn((r, c), seen)
                    seen.add((r, c))

    def test_배치된_셀은_모두_FREE_였다(self):
        for u in self.res.units:
            r0, c0, rows, cols = u.cells
            for r in range(r0, r0 + rows):
                for c in range(c0, c0 + cols):
                    self.assertEqual(self.grid.cells[r][c], CellState.FREE)

    def test_모든_유닛이_피난_한계_이내다(self):
        for u in self.res.units:
            self.assertLessEqual(u.egress_dist_m, self.em.limit_m)

    def test_유닛_치수가_규격과_같다(self):
        for u in self.res.units:
            _, _, w, h = u.rect_mm
            self.assertEqual(w * h / 1_000_000, 21.6 if u.type_id == "youth" else 36.0)

    def test_유닛_면적이_LH_매입_하한을_넘는다(self):
        """청년Ⅱ 19㎡ 이상 / 신혼·신생아 36㎡ 이상 (매입 공고 3장 공급유형표).

        하한 미달이면 매입 대상이 아니라 세대수를 아무리 뽑아도 무효다.
        """
        minimum = {"youth": 19.0, "newlywed": 36.0}
        for u in self.res.units:
            _, _, w, h = u.rect_mm
            self.assertGreaterEqual(w * h / 1_000_000, minimum[u.type_id])


class TestGoldenG1(unittest.TestCase):
    def test_복도_불가면_세대_0(self):
        _, _, res = run("tests/golden/G1", "supply")
        self.assertEqual(res.count, 0)


class TestGoldenG2(unittest.TestCase):
    def test_공급우선형_16세대(self):
        # 50열 / 청년형 6열 = 면당 8세대, 중복도이므로 ×2
        _, _, res = run("tests/golden/G2", "supply")
        self.assertEqual(res.count, 16)
        self.assertEqual(res.count_by_type(), {"youth": 16})

    def test_균형형은_두_유형이_섞인다(self):
        _, _, res = run("tests/golden/G2", "balanced")
        by = res.count_by_type()
        self.assertIn("youth", by)
        self.assertIn("newlywed", by)
        self.assertLessEqual(abs(by["youth"] - by["newlywed"]), 1)

    def test_샤프트가_없으면_저개입형은_0(self):
        # G2 에는 shafts 가 없다. 재사용할 설비가 없으므로 놓을 자리도 없다.
        _, _, res = run("tests/golden/G2", "minimal")
        self.assertEqual(res.count, 0)


class TestGoldenG4(unittest.TestCase):
    def test_한계_초과_구역에는_놓이지_않는다(self):
        grid, em, res = run("tests/golden/G4", "supply")
        far = max(u.cells[1] + u.cells[3] for u in res.units)
        self.assertLess(far, grid.cols)  # 우측 끝까지 채우지 못한다
        for u in res.units:
            self.assertLessEqual(u.egress_dist_m, em.limit_m)


class TestGoldenG5(unittest.TestCase):
    def test_all_cores_가_세대수를_줄인다(self):
        _, _, loose = run("tests/golden/G5", "supply", all_cores=False)
        _, _, strict = run("tests/golden/G5", "supply", all_cores=True)
        self.assertGreater(loose.count, strict.count)


class TestStrategies(unittest.TestCase):
    def test_저개입형은_재사용률_100퍼센트(self):
        _, _, res = run(ESQUISSE, "minimal")
        self.assertGreater(res.count, 0)
        self.assertEqual(res.shaft_reuse_ratio, 1.0)

    def test_저개입형이_공급우선형보다_적다(self):
        _, _, supply = run(ESQUISSE, "supply")
        _, _, minimal = run(ESQUISSE, "minimal")
        self.assertLess(minimal.count, supply.count)

    def test_저개입형_유닛은_모두_재사용_범위_안(self):
        inp = load_inputs(ESQUISSE, DATA)
        _, _, res = run(ESQUISSE, "minimal")
        for u in res.units:
            self.assertLessEqual(
                u.shaft_dist_cells, inp.rules.shaft_reuse_threshold_cells
            )

    def test_공급우선형이_가장_많다(self):
        counts = {s: run(ESQUISSE, s)[2].count
                  for s in ("supply", "balanced", "minimal")}
        self.assertEqual(max(counts, key=counts.get), "supply")


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_배치(self):
        for s in ("supply", "balanced", "minimal"):
            a = run(ESQUISSE, s)[2]
            b = run(ESQUISSE, s)[2]
            self.assertEqual(a, b, s)


if __name__ == "__main__":
    unittest.main()
