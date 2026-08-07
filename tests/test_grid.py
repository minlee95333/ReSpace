import unittest

from engine.contracts import load_inputs
from engine.grid import CellState, gridify

DATA = "data"
ESQUISSE = "data/buildings/esquisse-gasan"


class TestGridify(unittest.TestCase):
    def setUp(self):
        self.inp = load_inputs(ESQUISSE, DATA)
        self.grid = gridify(self.inp.floors[0], self.inp.rules)

    def test_크기(self):
        # 36000 × 18000 / 600
        self.assertEqual(self.grid.cols, 60)
        self.assertEqual(self.grid.rows, 30)
        self.assertEqual(self.grid.origin_mm, (0, 0))

    def test_직사각형_평면에는_외부셀이_없다(self):
        self.assertEqual(self.grid.count(CellState.OUTSIDE), 0)

    def test_장애물_셀수(self):
        # stair 3600×3600 = 6×6, ev 2400×3600 = 4×6
        self.assertEqual(self.grid.count(CellState.CORE), 36 + 24)
        # shaft 1200×3600 = 2×6
        self.assertEqual(self.grid.count(CellState.SHAFT), 12)
        # 기둥 8개 × 600×600 = 1셀
        self.assertEqual(self.grid.count(CellState.COLUMN), 8)

    def test_셀_총합이_보존된다(self):
        total = sum(self.grid.count(s) for s in CellState)
        self.assertEqual(total, self.grid.cols * self.grid.rows)
        self.assertEqual(self.grid.count(CellState.FREE), 1800 - 60 - 12 - 8)

    def test_좌표_왕복(self):
        self.assertEqual(self.grid.to_mm(0, 0), (0, 0))
        self.assertEqual(self.grid.to_mm(12, 28), (16800, 7200))
        self.assertEqual(self.grid.cell_rect_mm(12, 28), (16800, 7200, 600, 600))

    def test_코어_위치가_맞다(self):
        # stair rect [16800, 7200, 3600, 3600] → rows 12..17, cols 28..33
        self.assertEqual(self.grid[12, 28], CellState.CORE)
        self.assertEqual(self.grid[17, 33], CellState.CORE)
        self.assertEqual(self.grid[11, 28], CellState.FREE)
        self.assertEqual(self.grid[12, 27], CellState.SHAFT)


class TestConservativeStamp(unittest.TestCase):
    """셀에 조금이라도 걸치면 셀 전체를 점유로 본다. 과대 산정을 막기 위함."""

    def test_격자에_걸친_기둥은_셀_전체를_먹는다(self):
        inp = load_inputs(ESQUISSE, DATA)
        fp = inp.floors[0]
        grid = gridify(fp, inp.rules)
        # 기둥 center (7500, 3900), size 600 → 정확히 1셀 (row 6, col 12)
        self.assertEqual(grid[6, 12], CellState.COLUMN)
        self.assertEqual(grid[6, 11], CellState.FREE)
        self.assertEqual(grid[5, 12], CellState.FREE)


class TestGoldenGrid(unittest.TestCase):
    def test_G1_크기(self):
        inp = load_inputs("tests/golden/G1", DATA)
        grid = gridify(inp.floors[0], inp.rules)
        self.assertEqual((grid.cols, grid.rows), (50, 20))

    def test_G2_크기(self):
        inp = load_inputs("tests/golden/G2", DATA)
        grid = gridify(inp.floors[0], inp.rules)
        self.assertEqual((grid.cols, grid.rows), (50, 25))


if __name__ == "__main__":
    unittest.main()
