import unittest

from engine.contracts import (
    Building,
    ContractError,
    FloorPlan,
    Rules,
    _strip_comments,
    load_inputs,
    load_json,
)

DATA = "data"
ESQUISSE = "data/buildings/esquisse-gasan"


class TestStrip(unittest.TestCase):
    def test_밑줄_키는_제거된다(self):
        src = {"a": 1, "_note": "x", "b": [{"c": 2, "_d": 3}]}
        self.assertEqual(_strip_comments(src), {"a": 1, "b": [{"c": 2}]})


class TestRules(unittest.TestCase):
    def setUp(self):
        self.rules = Rules.from_dict(load_json(f"{DATA}/rules.json"))

    def test_격자와_복도폭(self):
        self.assertEqual(self.rules.grid_mm, 600)
        self.assertEqual(self.rules.corridor_width_mm, 1800)
        self.assertEqual(self.rules.corridor_width_cells, 3)

    def test_주차_계수_경계(self):
        # '30㎡ 미만'은 strict, '60㎡ 이하'는 inclusive.
        # 신혼형을 28.8㎡ 로 잡은 이유가 여기 있다.
        self.assertEqual(self.rules.parking_coef(16.65), 0.5)
        self.assertEqual(self.rules.parking_coef(28.8), 0.5)
        self.assertEqual(self.rules.parking_coef(29.999), 0.5)
        self.assertEqual(self.rules.parking_coef(30.0), 0.6)
        self.assertEqual(self.rules.parking_coef(60.0), 0.6)
        self.assertEqual(self.rules.parking_coef(60.1), 1.0)

    def test_피난_한계(self):
        eg = self.rules.egress
        self.assertEqual(eg.limit_m(fire_resistant=False, floor=5, floors_total=10), 30)
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=5, floors_total=10), 50)
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=16, floors_total=19), 40)
        # 16층 이상 건물이어도 15층은 40m 가 아니다
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=15, floors_total=19), 50)

    def test_정화조_미확정이면_명시적으로_실패한다(self):
        with self.assertRaises(ContractError) as ctx:
            self.rules.septic_units_per_m3()
        self.assertIn("미확정", str(ctx.exception))


class TestValidation(unittest.TestCase):
    def test_격자_위반은_실패한다(self):
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        d["cores"][0]["rect"] = [16801, 7200, 3600, 3600]
        with self.assertRaises(ContractError) as ctx:
            FloorPlan.from_dict(d, 600)
        self.assertIn("격자", str(ctx.exception))

    def test_알수없는_코어_타입은_실패한다(self):
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        d["cores"][0]["type"] = "escalator"
        with self.assertRaises(ContractError):
            FloorPlan.from_dict(d, 600)

    def test_boundary_첫점_반복은_실패한다(self):
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        d["boundary"] = d["boundary"] + [d["boundary"][0]]
        with self.assertRaises(ContractError):
            FloorPlan.from_dict(d, 600)

    def test_미확정_필드를_쓰면_실패한다(self):
        b = Building.from_dict(load_json(f"{ESQUISSE}/building.json"))
        self.assertIsNone(b.parking_existing)
        with self.assertRaises(ContractError) as ctx:
            b.require("parking_existing")
        self.assertIn("parking_existing", str(ctx.exception))


class TestLoadInputs(unittest.TestCase):
    def test_에스키스_묶음_로딩(self):
        inp = load_inputs(ESQUISSE, DATA)
        self.assertEqual(inp.rules.grid_mm, 600)
        self.assertEqual(len(inp.units.types), 2)
        self.assertEqual(inp.units.min_depth_mm, 6000)
        self.assertEqual(len(inp.floors), 1)
        self.assertEqual(inp.floors[0].floor, 5)
        self.assertEqual(len(inp.floors[0].stair_cores()), 1)

    def test_해시가_기록된다(self):
        inp = load_inputs(ESQUISSE, DATA)
        self.assertEqual(
            set(inp.input_hash),
            {"rules.json", "units.json", "building.json", "floor_plan_05.json"},
        )
        for v in inp.input_hash.values():
            self.assertTrue(v.startswith("sha256:"))

    def test_해시는_재현된다(self):
        a = load_inputs(ESQUISSE, DATA).input_hash
        b = load_inputs(ESQUISSE, DATA).input_hash
        self.assertEqual(a, b)

    def test_유닛_격자_정합(self):
        inp = load_inputs(ESQUISSE, DATA)
        self.assertEqual(inp.units.by_id("youth").cells(600), (5, 10))
        self.assertEqual(inp.units.by_id("newlywed").cells(600), (8, 10))


if __name__ == "__main__":
    unittest.main()
