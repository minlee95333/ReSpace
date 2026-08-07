import unittest

from engine.common import REASONS, collect, summarize
from engine.contracts import load_inputs
from engine.corridor import generate
from engine.daylight import evaluate
from engine.egress import compute
from engine.grid import CellState, gridify
from engine.place import place

DATA = "data"
CASES = [
    "tests/golden/G1",
    "tests/golden/G2",
    "tests/golden/G3",
    "tests/golden/G4",
    "tests/golden/G5",
    "data/buildings/esquisse-gasan",
]


def run(building_dir, strategy="supply"):
    inp = load_inputs(building_dir, DATA)
    grid = gridify(inp.floors[0], inp.rules)
    corridor = generate(inp.floors[0], grid, inp.rules, inp.units)
    em = compute(inp.floors[0], grid, inp.rules, inp.building)
    pr = place(grid, corridor, em, inp.rules, inp.units, strategy)
    dl = evaluate(inp.floors[0], inp.rules, inp.units, pr)
    return grid, em, dl, collect(grid, em, dl.units, dl.rejected)


class TestAreaConservation(unittest.TestCase):
    """사용가능 면적은 세대와 공용으로 남김없이 나뉜다.

    이게 깨지면 어딘가에서 면적이 사라지거나 겹쳐 세면서 세대수가 틀어진다.
    """

    def test_전_케이스_면적_보존(self):
        for case in CASES:
            with self.subTest(case=case):
                grid, _, dl, areas = run(case)
                free_m2 = grid.count(CellState.FREE) * (grid.grid_mm / 1000) ** 2
                unit_m2 = sum(u.rect_mm[2] * u.rect_mm[3] for u in dl.units) / 1e6
                common_m2 = sum(a.area_m2 for a in areas)
                self.assertAlmostEqual(free_m2, unit_m2 + common_m2, places=6)

    def test_공용_셀수가_잔여_셀수와_같다(self):
        for case in CASES:
            with self.subTest(case=case):
                grid, _, dl, areas = run(case)
                used = sum(u.cells[2] * u.cells[3] for u in dl.units)
                self.assertEqual(
                    sum(a.cell_count for a in areas),
                    grid.count(CellState.FREE) - used,
                )


class TestReasons(unittest.TestCase):
    def test_탈락_유닛은_사각형_그대로_나온다(self):
        _, _, dl, areas = run("tests/golden/G3")
        rects = {a.bbox_mm for a in areas}
        for r in dl.rejected:
            self.assertIn(r.rect_mm, rects)

    def test_G3_사유_구성(self):
        _, _, _, areas = run("tests/golden/G3")
        s = summarize(areas)
        self.assertEqual(s["no_window"], 108.0)      # 18㎡ × 6
        self.assertEqual(s["daylight_short"], 18.0)  # 18㎡ × 1
        self.assertIn("geometry", s)

    def test_피난_초과_구역이_따로_잡힌다(self):
        # 통과 셀과 섞어 묶으면 초과 구역이 geometry 로 뭉개져 화면에서 사라진다.
        grid, em, _, areas = run("tests/golden/G4")
        self.assertGreater(em.over_limit_cells, 0)
        over = [a for a in areas if a.reason == "egress_over_limit"]
        self.assertTrue(over)
        # 공용 영역은 FREE 셀만 덮는다. 한계를 넘은 복도 셀은 여전히 복도다.
        free_over = sum(
            1
            for r in range(grid.rows)
            for c in range(grid.cols)
            if grid.cells[r][c] == CellState.FREE and not em.ok(r, c)
        )
        self.assertEqual(sum(a.cell_count for a in over), free_over)
        self.assertLess(free_over, em.over_limit_cells)

    def test_피난_문제가_없으면_초과_구역도_없다(self):
        _, em, _, areas = run("tests/golden/G2")
        self.assertEqual(em.over_limit_cells, 0)
        self.assertFalse([a for a in areas if a.reason == "egress_over_limit"])

    def test_사유_우선순위대로_정렬된다(self):
        _, _, _, areas = run("tests/golden/G4")
        idx = [REASONS.index(a.reason) for a in areas]
        self.assertEqual(idx, sorted(idx))

    def test_모든_사유가_알려진_값이다(self):
        for case in CASES:
            with self.subTest(case=case):
                _, _, _, areas = run(case)
                for a in areas:
                    self.assertIn(a.reason, REASONS)
                    self.assertTrue(a.label)


class TestG1(unittest.TestCase):
    def test_세대_0_이면_전부_공용_후보(self):
        grid, _, dl, areas = run("tests/golden/G1")
        self.assertEqual(dl.kept, 0)
        free_m2 = grid.count(CellState.FREE) * 0.36
        self.assertAlmostEqual(sum(a.area_m2 for a in areas), free_m2, places=6)


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_공용_영역(self):
        for case in CASES:
            with self.subTest(case=case):
                self.assertEqual(run(case)[3], run(case)[3])


if __name__ == "__main__":
    unittest.main()
