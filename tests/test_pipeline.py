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


#: 축이 막힌 상태를 만드는 입력. 정화조 용량·인원도, 종전 용도 추정용 gfa_m2 도 없다.
#: 종전에는 에스키스 가산을 썼으나 건축물대장 API 로 실제 수치가 채워지면서
#: 더 이상 '미확보' 사례가 아니게 됐다. 실제 건물의 자료 상태에 테스트를 묶어 두면
#: 자료가 들어올 때마다 깨지므로 전용 골든케이스로 분리했다.
BLOCKED = "tests/golden/G6"


class TestFloorExpansion(unittest.TestCase):
    """기준층 1개를 floors_residential 범위만큼 반복한다."""

    def test_G2_는_5개층으로_펼쳐진다(self):
        inp = load("tests/golden/G2")
        self.assertEqual(residential_floors(inp), (1, 2, 3, 4, 5))
        a = analyze(inp, "supply")
        self.assertEqual([f.floor for f in a.floors], [1, 2, 3, 4, 5])
        # 층당 16세대 × 5개층 = 80. 주민공동시설 의무면적으로 1층에서 4세대가 빠져 76.
        self.assertEqual(len(a.units), 76)

    def test_범위가_없으면_준_도면만_쓴다(self):
        inp = load(BLOCKED)
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
        self.assertEqual(a.caps.by_axis("plan").value, 76)
        self.assertEqual(a.caps.by_axis("parking").value, 40)  # 20대 ÷ 0.5
        self.assertEqual(a.caps.supply, 40)
        self.assertEqual(a.caps.bottleneck, "parking")

    def test_미확보_축은_숫자를_지어내지_않는다(self):
        a = analyze(load(BLOCKED), "supply")
        septic = a.caps.by_axis("septic")
        self.assertIsNone(septic.value)
        self.assertFalse(a.caps.complete)
        self.assertIn("septic_capacity_persons", septic.blocked_reason)

    def test_주차_미입력이면_주차축이_막힌다(self):
        a = analyze(load(BLOCKED), "supply")
        self.assertIsNone(a.caps.by_axis("parking").value)
        self.assertEqual(a.caps.bottleneck, "plan")

    def test_3축이_모두_돌면_complete(self):
        a = analyze(load("tests/golden/G2"), "supply")
        self.assertTrue(a.caps.complete)
        # 30㎥ → 5+(30-1.5)×10 = 290인 (시행규칙 별표12) ÷ 청년형 2.0인 = 145세대
        self.assertEqual(a.caps.by_axis("septic").value, 145)
        self.assertEqual(a.caps.supply, 40)
        self.assertEqual(a.caps.bottleneck, "parking")

    def test_공공하수도_연결이면_정화조_축이_해당_없음이다(self):
        """도심 건물 상당수가 하수처리구역 안이다. 무조건 정화조 상한을 계산하면
        없는 병목이 생긴다. '미확보'와도 구분해야 한다 — 확보할 것이 없다."""
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(
            inp.building, septic_mode_raw="하수종말처리장 연결"))
        a = analyze(inp, "supply")
        septic = a.caps.by_axis("septic")
        self.assertIsNone(septic.value)
        self.assertTrue(septic.not_applicable)
        self.assertFalse(septic.is_blocked)
        self.assertEqual(septic.state_label, "해당 없음")
        # 해당 없음은 공백이 아니므로 complete 를 깨지 않는다
        self.assertTrue(a.caps.complete)
        self.assertEqual(a.grade, "통과")
        self.assertEqual(a.caps.bottleneck, "parking")

    def test_해당_없음과_미확보는_다르게_표시된다(self):
        blocked = analyze(load(BLOCKED), "supply").caps.by_axis("septic")
        self.assertTrue(blocked.is_blocked)
        self.assertFalse(blocked.not_applicable)
        self.assertEqual(blocked.state_label, "미확보")

    def test_오수처리시설은_숫자를_내지_않는다(self):
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(
            inp.building, septic_mode_raw="오수처리시설"))
        a = analyze(inp, "supply")
        septic = a.caps.by_axis("septic")
        self.assertIsNone(septic.value)
        self.assertTrue(septic.is_blocked)
        self.assertIn("산정식", septic.blocked_reason)

    def _mode(self, mode, **building):
        from engine.contracts import Rules, load_json
        raw = load_json("data/rules.json")
        raw["parking"]["mode"] = mode
        inp = load("tests/golden/G2")
        return analyze(dc.replace(
            inp, rules=Rules.from_dict(raw),
            building=dc.replace(inp.building, use="숙박시설", **building)), "supply")

    def test_제37조5는_주차_축을_없앤다(self):
        """종전 용도 기준으로 부설주차장을 보므로, 사용승인을 받은 건물이면
        기존 주차가 이미 그 기준을 충족한다. 세대수가 늘어도 추가를 요구하지 않는다."""
        a = self._mode("relaxed_037_5", converted_use="오피스텔", no_car_tenant=True)
        p = a.caps.by_axis("parking")
        self.assertIsNone(p.value)
        self.assertTrue(p.not_applicable)
        self.assertFalse(p.is_blocked)
        self.assertTrue(a.caps.complete)
        self.assertEqual(a.caps.bottleneck, "plan")
        self.assertIn("제37조⑤", p.basis)

    def test_요건을_못_맞추면_통상_계수로_떨어진다(self):
        """특례를 못 받는 쪽이 보수적이다. 왜 못 받았는지도 남긴다."""
        base = self._mode("statutory").caps.by_axis("parking").value
        for kw, missing in (
            ({"converted_use": "오피스텔", "no_car_tenant": False}, "요건3"),
            ({"converted_use": "공동주택", "no_car_tenant": True}, "요건1"),
            ({"no_car_tenant": True}, "요건1"),
        ):
            with self.subTest(missing):
                p = self._mode("relaxed_037_5", **kw).caps.by_axis("parking")
                self.assertEqual(p.value, base)
                self.assertIn(missing, p.basis)

    def test_비주택이_아니면_대상이_아니다(self):
        """제37조①제3호 한정 — 공동주택·단독주택은 이 특례를 못 받는다."""
        from engine.contracts import Rules, load_json
        raw = load_json("data/rules.json")
        raw["parking"]["mode"] = "relaxed_037_5"
        inp = load("tests/golden/G2")
        a = analyze(dc.replace(inp, rules=Rules.from_dict(raw), building=dc.replace(
            inp.building, use="공동주택", converted_use="오피스텔",
            no_car_tenant=True)), "supply")
        p = a.caps.by_axis("parking")
        self.assertIsNotNone(p.value)
        self.assertIn("대상 아님", p.basis)

    def test_전용_30제곱미터_이상_세대가_있으면_못_받는다(self):
        """요건2. G2 의 균형형은 신혼형 36.0㎡ 를 섞으므로 걸린다."""
        from engine.contracts import Rules, load_json
        raw = load_json("data/rules.json")
        raw["parking"]["mode"] = "relaxed_037_5"
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, rules=Rules.from_dict(raw), building=dc.replace(
            inp.building, use="숙박시설", converted_use="오피스텔", no_car_tenant=True))
        supply = analyze(inp, "supply").caps.by_axis("parking")     # 청년형 21.6 만
        balanced = analyze(inp, "balanced").caps.by_axis("parking")  # 신혼형 36.0 포함
        self.assertTrue(supply.not_applicable)
        self.assertIsNotNone(balanced.value)
        self.assertIn("요건2 미충족", balanced.basis)
        self.assertIn("36.0㎡", balanced.basis)

    def test_유형_구성이_정화조_상한을_움직인다(self):
        """신혼형은 2.7인, 청년형은 2.0인 — 같은 정화조로 받는 세대수가 달라진다."""
        supply = analyze(load("tests/golden/G2"), "supply")     # 청년형만
        balanced = analyze(load("tests/golden/G2"), "balanced")  # 두 유형 혼합
        self.assertGreater(
            supply.caps.by_axis("septic").value,
            balanced.caps.by_axis("septic").value,
        )


class TestVerdict(unittest.TestCase):
    """등급은 LH 자체 3구분을 그대로 쓴다 — 통과 / 조건부 통과 / 매입제외."""

    def test_세대_0_이면_매입제외(self):
        a = analyze(load("tests/golden/G1"), "supply")
        self.assertEqual(a.caps.supply, 0)
        self.assertEqual(a.grade, "매입제외")

    def test_미확보_축이_있으면_조건부_통과(self):
        a = analyze(load(BLOCKED), "supply")
        self.assertEqual(a.grade, "조건부 통과")

    def test_인프라가_병목이어도_통과다(self):
        """병목이 있다는 것과 매입 부적격은 다르다. 보강하면 되는 사안이다."""
        a = analyze(load("tests/golden/G2"), "supply")
        self.assertEqual(a.grade, "통과")
        self.assertIn("주차 보강이 선행", " ".join(a.reasons))

    def test_평면이_병목이면_보강이_필요없다고_적는다(self):
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(inp.building, parking_existing=60))
        a = analyze(inp, "supply")
        self.assertEqual(a.caps.bottleneck, "plan")
        self.assertEqual(a.grade, "통과")
        self.assertIn("인프라 여유", " ".join(a.reasons))

    def test_매입제외_사유가_있으면_세대수와_무관하게_제외다(self):
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(inp.building, violation=True))
        a = analyze(inp, "supply")
        self.assertGreater(a.caps.supply, 0)
        self.assertEqual(a.grade, "매입제외")
        self.assertIn("건축법 위반", " ".join(a.reasons))

    def test_미확인_항목이_있으면_통과를_주지_않는다(self):
        """확인되지 않은 것을 통과로 처리하면 판정이 후하게 틀린다."""
        inp = load("tests/golden/G2")
        inp = dc.replace(inp, building=dc.replace(inp.building, exclusion_answers={}))
        a = analyze(inp, "supply")
        self.assertEqual(a.grade, "조건부 통과")
        self.assertTrue(a.exclusion.unknown)

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
        self.assertEqual(p["required"], 38.0)   # 76세대 × 0.5
        self.assertEqual(p["existing"], 20)
        self.assertEqual(p["shortfall"], 18.0)

    def test_정화조_필요용량은_세대수에_비례하지_않는다(self):
        """1.5㎥ 기본 + 초과분 가산이라 원점을 지나지 않는다."""
        s = analyze(load("tests/golden/G2"), "supply").quantities["septic"]
        self.assertEqual(s["persons"], 152.0)          # 76세대 × 2.0인
        self.assertEqual(s["required_m3"], 16.2)       # 1.5 + (152-5)×0.1
        self.assertEqual(s["shortfall_m3"], 0.0)       # 기존 30㎥ 로 충분

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
