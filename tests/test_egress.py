import dataclasses as dc
import unittest

from engine.contracts import load_inputs
from engine.corridor import generate
from engine.egress import compute
from engine.grid import gridify

DATA = "data"


def run(building_dir, all_cores=None):
    inp = load_inputs(building_dir, DATA)
    rules = inp.rules
    if all_cores is not None:
        rules = dc.replace(rules, egress=dc.replace(rules.egress, all_cores=all_cores))
    grid = gridify(inp.floors[0], rules)
    corridor = generate(inp.floors[0], grid, rules, inp.units)
    return grid, corridor, compute(inp.floors[0], grid, rules, inp.building)


class TestLimitSelection(unittest.TestCase):
    def test_내화구조면_50m(self):
        _, _, em = run("tests/golden/G2")
        self.assertEqual(em.limit_m, 50.0)


class TestG4(unittest.TestCase):
    """60m 장변, 계단 1개소가 좌측 끝. 원단부가 한계를 넘는다."""

    def test_한계_초과_구역이_생긴다(self):
        _, _, em = run("tests/golden/G4")
        self.assertEqual(em.stair_count, 1)
        self.assertGreater(em.over_limit_cells, 0)

    def test_좌측은_통과_우측은_실격(self):
        grid, cor, em = run("tests/golden/G4")
        row = cor.band[0] - 1  # 복도 바로 아래 행
        self.assertTrue(em.ok(row, 5))
        self.assertFalse(em.ok(row, grid.cols - 1))

    def test_거리는_격자_스텝의_배수다(self):
        grid, cor, em = run("tests/golden/G4")
        d = em.at(cor.band[0], grid.cols - 1)
        self.assertIsNotNone(d)
        steps = d / 0.6
        self.assertAlmostEqual(steps, round(steps), places=6)


class TestG5AllCoresSwitch(unittest.TestCase):
    """계단 2개소가 양 끝. 스위치가 결과를 뒤집는다.

    all_cores=True 는 '직통계단 2개소 이상이면 모두 기준 충족'의 직역이며,
    이 해석에서는 계단이 2개라서 오히려 불리해진다. 상식과 반대이므로
    제안서에 쓸 값을 정하기 전에 양쪽을 비교한다.
    """

    def test_false_면_전_구역_통과(self):
        _, _, em = run("tests/golden/G5", all_cores=False)
        self.assertEqual(em.stair_count, 2)
        self.assertEqual(em.over_limit_cells, 0)

    def test_true_면_양끝이_실격된다(self):
        _, _, em = run("tests/golden/G5", all_cores=True)
        self.assertGreater(em.over_limit_cells, 0)

    def test_계단_2개가_불리해지는_역설(self):
        _, _, one = run("tests/golden/G4", all_cores=True)   # 계단 1개
        _, _, two = run("tests/golden/G5", all_cores=True)   # 계단 2개
        # 같은 크기 평면인데 계단이 늘어나 실격 셀이 더 많아진다
        self.assertGreater(two.over_limit_cells, one.over_limit_cells)

    def test_계단_1개면_스위치가_무의미하다(self):
        _, _, f = run("tests/golden/G4", all_cores=False)
        _, _, t = run("tests/golden/G4", all_cores=True)
        self.assertEqual(f.over_limit_cells, t.over_limit_cells)


class TestTraversal(unittest.TestCase):
    def test_코어_샤프트_기둥은_통행_불가(self):
        grid, _, em = run("data/buildings/esquisse-gasan")
        self.assertIsNone(em.at(12, 28))  # CORE
        self.assertIsNone(em.at(12, 26))  # SHAFT
        self.assertIsNone(em.at(6, 12))   # COLUMN

    def test_계단이_없으면_전부_도달불가(self):
        inp = load_inputs("data/buildings/esquisse-gasan", DATA)
        fp = dc.replace(inp.floors[0], cores=tuple(
            c for c in inp.floors[0].cores if c.type == "ev"))
        grid = gridify(fp, inp.rules)
        generate(fp, grid, inp.rules, inp.units)
        em = compute(fp, grid, inp.rules, inp.building)
        self.assertEqual(em.stair_count, 0)
        self.assertEqual(em.reachable_cells, 0)


if __name__ == "__main__":
    unittest.main()
