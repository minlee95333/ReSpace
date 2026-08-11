import unittest

from engine.contracts import load_inputs
from engine.corridor import generate
from engine.grid import CellState, gridify

DATA = "data"


def run(building_dir):
    inp = load_inputs(building_dir, DATA)
    grid = gridify(inp.floors[0], inp.rules)
    return grid, generate(inp.floors[0], grid, inp.rules, inp.units)


class TestGoldenG1(unittest.TestCase):
    """30×12m. 복도 1.8m 를 빼면 양옆이 유닛 깊이 6m 에 미달한다. 세대 0 이 정답."""

    def test_양쪽_모두_사용_불가(self):
        _, res = run("tests/golden/G1")
        self.assertEqual(res.type, "none")
        self.assertEqual(res.axis, "h")
        self.assertEqual(res.need_cells, 10)
        self.assertLess(res.depth_low_cells, 10)
        self.assertLess(res.depth_high_cells, 10)

    def test_깊이_수치(self):
        _, res = run("tests/golden/G1")
        # 중복도 폭(3행)으로는 양쪽 다 미달이므로 편복도 폭(2행)으로 다시 놓는다.
        # 20행 - 복도 2행 = 18행이 대칭으로 갈려 양쪽 9행.
        self.assertEqual(res.width_cells, 2)
        self.assertEqual(res.depth_low_cells, 9)
        self.assertEqual(res.depth_high_cells, 9)
        # 폭을 줄여도 유닛 깊이 10행에는 여전히 못 미친다 — G1 의 정답은 그대로 0세대다.
        self.assertEqual(res.type, "none")

    def test_편복도_폭으로_다시_놓아도_판정이_뒤집히지_않는다(self):
        """2패스가 끝난다는 근거. 폭이 좁아지면 깊이는 늘 뿐 중복도가 새로 생기지 않는다."""
        _, res = run("tests/golden/G1")
        self.assertLess(res.width_cells, 3)
        self.assertLess(res.depth_low_cells, res.need_cells)


class TestGoldenG2(unittest.TestCase):
    """G1 에서 깊이만 15m 로. 중복도가 성립하는 경계 바로 위."""

    def test_중복도_성립(self):
        _, res = run("tests/golden/G2")
        self.assertEqual(res.type, "double")
        # 중복도이므로 1패스에서 확정된다 — 좁은 폭으로 내려가지 않는다.
        self.assertEqual(res.width_cells, 3)
        self.assertEqual(res.depth_low_cells, 11)
        self.assertEqual(res.depth_high_cells, 11)
        self.assertEqual(res.coverage_low, 1.0)
        self.assertEqual(res.coverage_high, 1.0)


class TestEsquissePlaceholder(unittest.TestCase):
    def test_중복도로_판정된다(self):
        grid, res = run("data/buildings/esquisse-gasan")
        self.assertEqual(res.type, "double")
        self.assertEqual(res.axis, "h")
        self.assertEqual(res.band, (13, 15))

    def test_코어가_벌어진_방향으로_축을_잡는다(self):
        # 코어 2개가 x 방향으로 나란하므로 복도는 수평
        _, res = run("data/buildings/esquisse-gasan")
        self.assertEqual(res.axis, "h")

    def test_복도는_FREE_셀만_덮는다(self):
        grid, res = run("data/buildings/esquisse-gasan")
        lo, hi = res.band
        # 밴드 안의 코어·샤프트는 그대로 남아야 한다
        self.assertEqual(grid[13, 28], CellState.CORE)
        self.assertEqual(grid[13, 26], CellState.SHAFT)
        self.assertEqual(grid[13, 0], CellState.CORRIDOR)
        self.assertEqual(grid.count(CellState.CORE), 60)
        self.assertEqual(grid.count(CellState.SHAFT), 12)

    def test_복도_셀수(self):
        grid, res = run("data/buildings/esquisse-gasan")
        # 3행 × 60열 = 180 중 코어 10열 + 샤프트 2열이 빠진다
        self.assertEqual(grid.count(CellState.CORRIDOR), 3 * (60 - 12))


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_결과(self):
        a = run("data/buildings/esquisse-gasan")[1]
        b = run("data/buildings/esquisse-gasan")[1]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
