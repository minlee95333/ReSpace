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

    def test_주차_완화모드는_세대별로_갈린다(self):
        """공공주택특별법 시행령 제37조④ — '전용면적이 30㎡ 미만인 **세대는** 0.3대'.

        조문이 세대 단위로 쓰므로 혼합 구성이면 기준을 넘는 세대는 statutory 로
        떨어진다. 기준이 개정되면 코드가 아니라 rules.json 만 바꾼다.
        """
        raw = load_json("data/rules.json")
        raw["parking"]["mode"] = "relaxed_037_4"
        r = Rules.from_dict(raw)
        self.assertEqual(r.parking_mode, "relaxed_037_4")
        self.assertEqual(r.parking_coef(21.6), 0.3)   # 청년형 — 완화 대상
        self.assertEqual(r.parking_coef(29.999), 0.3)
        self.assertEqual(r.parking_coef(30.0), 0.6)   # 신혼형 — 완화 대상 밖
        self.assertEqual(r.parking_coef(36.0), 0.6)
        self.assertEqual(r.parking_coef(60.1), 1.0)

    def test_없는_주차모드는_실패한다(self):
        raw = load_json("data/rules.json")
        raw["parking"]["mode"] = "nope"
        with self.assertRaises(ContractError) as ctx:
            Rules.from_dict(raw)
        self.assertIn("nope", str(ctx.exception))

    def test_피난_한계(self):
        eg = self.rules.egress
        self.assertEqual(eg.limit_m(fire_resistant=False, floor=5, floors_total=10), 30)
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=5, floors_total=10), 50)
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=16, floors_total=19), 40)
        # 16층 이상 건물이어도 15층은 40m 가 아니다
        self.assertEqual(eg.limit_m(fire_resistant=True, floor=15, floors_total=19), 50)

    def test_정화조_용량_환산은_시행규칙_별표12를_따른다(self):
        s = self.rules.septic
        # 3인 이하 1.0㎥, 5인까지 1.5㎥, 초과분은 5인당 0.5㎥ 가산
        self.assertEqual(s.volume_for_persons(3), 1.0)
        self.assertEqual(s.volume_for_persons(5), 1.5)
        self.assertEqual(s.volume_for_persons(10), 2.0)
        self.assertEqual(s.volume_for_persons(105), 11.5)

    def test_인원과_용량은_왕복한다(self):
        s = self.rules.septic
        for n in (6, 25, 160, 440):
            self.assertAlmostEqual(s.persons_for_volume(s.volume_for_persons(n)), n)

    def test_용도별_인원산정식(self):
        s = self.rules.septic
        # 고시 별표: 숙박시설 N = 0.080A
        self.assertAlmostEqual(s.persons_for_use("숙박시설", 20000), 1600.0)
        self.assertAlmostEqual(s.persons_for_use("오피스텔", 10000), 500.0)

    def test_형식코드_앞자리로_분류한다(self):
        """실 API 표본(2026-08-10)에서 확인한 코드. 공법 이름은 수십 종이지만
        modeCd 앞자리는 1=오수처리시설 / 2=정화조 / 3=공공하수도 로 안정적이다."""
        s = self.rules.septic
        self.assertEqual(s.mode_for("접촉산화방법", "102").id, "sewage_treatment")
        self.assertEqual(s.mode_for("접촉폭기방법", "117").id, "sewage_treatment")
        self.assertEqual(s.mode_for("부패탱크방법", "201").id, "septic_tank")
        self.assertEqual(s.mode_for("하수종말처리장연결", "300").id, "public_sewer")

    def test_처음_보는_공법도_앞자리로_분류된다(self):
        """공법명을 다 담을 수는 없다. 앞자리가 맞으면 이름을 몰라도 분류된다."""
        s = self.rules.septic
        self.assertEqual(s.mode_for("아직모르는신공법", "199").id, "sewage_treatment")
        self.assertEqual(s.mode_for("아직모르는신공법", "299").id, "septic_tank")

    def test_코드가_없으면_이름으로_본다(self):
        s = self.rules.septic
        self.assertEqual(s.mode_for("단독정화조").id, "septic_tank")
        self.assertEqual(s.mode_for("공공하수처리시설").id, "public_sewer")
        self.assertEqual(s.mode_for("오수처리시설").id, "sewage_treatment")

    def test_공공하수도_연결은_세대수를_제한하지_않는다(self):
        m = self.rules.septic.mode_for("하수종말처리장연결", "300")
        self.assertFalse(m.limits)
        self.assertTrue(m.not_applicable)

    def test_오수처리시설에는_별표12_환산을_쓰지_않는다(self):
        """규모 산정식이 BOD 부하 기준이라 인원↔용량 환산이 성립하지 않는다."""
        self.assertFalse(self.rules.septic.mode_for("접촉폭기방법", "117").volume_conversion)
        self.assertTrue(self.rules.septic.mode_for("부패탱크방법", "201").volume_conversion)

    def test_모르는_처리방식은_정화조라고_단정하지_않는다(self):
        with self.assertRaises(ContractError) as ctx:
            self.rules.septic.mode_for("자체처리", "999")
        self.assertIn("999", str(ctx.exception))

    def test_모르는_용도의_계수는_지어내지_않는다(self):
        with self.assertRaises(ContractError) as ctx:
            self.rules.septic.persons_for_use("판매시설", 1000)
        self.assertIn("판매시설", str(ctx.exception))


class TestValidation(unittest.TestCase):
    def test_격자_위반은_실패한다(self):
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        d["cores"][0]["rect"] = [16801, 7200, 3600, 3600]
        with self.assertRaises(ContractError) as ctx:
            FloorPlan.from_dict(d, 600)
        self.assertIn("격자", str(ctx.exception))

    def test_출처가_없으면_실패한다(self):
        # 도면 출처를 밝히지 않은 결과는 어디까지 믿어도 되는지 알 수 없다.
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        del d["status"]
        with self.assertRaises(ContractError) as ctx:
            FloorPlan.from_dict(d, 600)
        self.assertIn("status", str(ctx.exception))

    def test_알수없는_출처값은_실패한다(self):
        d = load_json(f"{ESQUISSE}/floor_plan_05.json")
        d["status"] = "대충그림"
        with self.assertRaises(ContractError):
            FloorPlan.from_dict(d, 600)

    def test_플레이스홀더는_신뢰할_수_없다고_표시된다(self):
        fp = FloorPlan.from_dict(load_json(f"{ESQUISSE}/floor_plan_05.json"), 600)
        self.assertEqual(fp.status, "placeholder")
        self.assertFalse(fp.is_trustworthy)
        self.assertIn("사례 대조에 쓸 수 없음", fp.status_label)

    def test_인공_평면도_신뢰_대상이_아니다(self):
        fp = FloorPlan.from_dict(load_json("tests/golden/G2/floor_plan_01.json"), 600)
        self.assertEqual(fp.status, "synthetic")
        self.assertFalse(fp.is_trustworthy)

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
        b = Building.from_dict(load_json("tests/golden/G6/building.json"))
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
            {
                "rules.json",
                "units.json",
                "exclusions.json",
                "building.json",
                "floor_plan_05.json",
            },
        )
        for v in inp.input_hash.values():
            self.assertTrue(v.startswith("sha256:"))

    def test_해시는_재현된다(self):
        a = load_inputs(ESQUISSE, DATA).input_hash
        b = load_inputs(ESQUISSE, DATA).input_hash
        self.assertEqual(a, b)

    def test_유닛_격자_정합(self):
        inp = load_inputs(ESQUISSE, DATA)
        self.assertEqual(inp.units.by_id("youth").cells(600), (6, 10))
        self.assertEqual(inp.units.by_id("newlywed").cells(600), (10, 10))

    def test_세대당_처리대상인원이_유형별로_있다(self):
        inp = load_inputs(ESQUISSE, DATA)
        # 고시 별표: 1호 1거실 → 2인, R=2 → 2.7+(2-2)×0.5 = 2.7인
        self.assertEqual(inp.units.by_id("youth").persons_per_household, 2.0)
        self.assertEqual(inp.units.by_id("newlywed").persons_per_household, 2.7)


if __name__ == "__main__":
    unittest.main()
