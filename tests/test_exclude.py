import dataclasses as dc
import unittest

from engine.contracts import ContractError, Exclusions, load_inputs, load_json
from engine.exclude import check
from engine.pipeline import analyze

DATA = "data"
G2 = "tests/golden/G2"


def load(path=G2, **building_overrides):
    inp = load_inputs(path, DATA)
    if building_overrides:
        inp = dc.replace(inp, building=dc.replace(inp.building, **building_overrides))
    return inp


def run(inp):
    return check(inp.exclusions, inp.building, inp.floors)


class TestContract(unittest.TestCase):
    def test_공고_조건이_전부_실린다(self):
        ex = Exclusions.from_dict(load_json("data/exclusions.json"))
        self.assertGreaterEqual(len(ex.conditions), 16)
        kinds = {c.check for c in ex.conditions}
        self.assertEqual(kinds, {"auto", "ask", "geo"})

    def test_모든_조건에_출처가_있다(self):
        ex = Exclusions.from_dict(load_json("data/exclusions.json"))
        for c in ex.conditions:
            with self.subTest(c.id):
                self.assertTrue(c.source, f"{c.id} 에 공고 출처가 없다")

    def test_auto_인데_rule_이_없으면_실패한다(self):
        raw = load_json("data/exclusions.json")
        raw["conditions"] = [
            {"id": "x", "label": "x", "check": "auto", "source": "s"}
        ]
        with self.assertRaises(ContractError) as ctx:
            Exclusions.from_dict(raw)
        self.assertIn("rule", str(ctx.exception))

    def test_알수없는_check_종류는_실패한다(self):
        raw = load_json("data/exclusions.json")
        raw["conditions"] = [
            {"id": "x", "label": "x", "check": "느낌", "source": "s"}
        ]
        with self.assertRaises(ContractError):
            Exclusions.from_dict(raw)

    def test_구현되지_않은_rule_은_조용히_통과시키지_않는다(self):
        raw = load_json("data/exclusions.json")
        raw["conditions"] = [
            {"id": "x", "label": "x", "check": "auto", "rule": "없는규칙", "source": "s"}
        ]
        inp = load()
        with self.assertRaises(ContractError) as ctx:
            check(Exclusions.from_dict(raw), inp.building, inp.floors)
        self.assertIn("없는규칙", str(ctx.exception))


class TestAutoRules(unittest.TestCase):
    def test_지하세대가_있으면_제외다(self):
        a = analyze(load(floors_residential=(0, 3)), "supply")
        hit = [c for c in a.exclusion.checks if c.id == "basement_units"][0]
        self.assertEqual(hit.status, "excluded")
        self.assertEqual(a.grade, "매입제외")

    def test_지상층만이면_통과한다(self):
        a = analyze(load(), "supply")
        hit = [c for c in a.exclusion.checks if c.id == "basement_units"][0]
        self.assertEqual(hit.status, "ok")

    def test_위반건축물이면_제외다(self):
        a = analyze(load(violation=True), "supply")
        hit = [c for c in a.exclusion.checks if c.id == "legal_restriction"][0]
        self.assertEqual(hit.status, "excluded")

    def test_위반건축물_미입력이면_미확인이다(self):
        """모르는 것을 '해당 없음'으로 처리하지 않는다."""
        a = analyze(load(violation=None), "supply")
        hit = [c for c in a.exclusion.checks if c.id == "legal_restriction"][0]
        self.assertEqual(hit.status, "unknown")
        self.assertEqual(a.grade, "조건부 통과")


class TestAnswers(unittest.TestCase):
    def test_답이_없으면_미확인이다(self):
        res = run(load(exclusion_answers={}))
        self.assertTrue(res.unknown)
        self.assertEqual(res.grade, "조건부 통과")

    def test_참으로_답하면_제외다(self):
        res = run(load(exclusion_answers={"development_zone": True}))
        hit = [c for c in res.checks if c.id == "development_zone"][0]
        self.assertEqual(hit.status, "excluded")
        self.assertEqual(res.grade, "매입제외")

    def test_전부_해당없음으로_답하면_통과다(self):
        res = run(load())
        self.assertFalse(res.unknown, [c.id for c in res.unknown])
        self.assertFalse(res.excluded)
        self.assertEqual(res.grade, "통과")

    def test_위치_항목은_무엇이_필요한지_밝힌다(self):
        res = run(load(exclusion_answers={}))
        geo = [c for c in res.checks if c.check == "geo"]
        self.assertTrue(geo)
        for c in geo:
            self.assertIn("위치 데이터", c.detail)


class TestZoningEvidence(unittest.TestCase):
    """용도지역은 판정하지 않되, 판단 재료는 근거에 실어 보낸다."""

    def test_수집된_지정사항이_판정_근거에_붙는다(self):
        inp = load_inputs("data/buildings/esquisse-gasan", DATA)
        res = check(inp.exclusions, inp.building, inp.floors)
        c = [x for x in res.checks if x.id == "use_change_impossible"][0]
        self.assertEqual(c.status, "unknown")
        self.assertIn("상업지역", c.detail)

    def test_지정사항이_없으면_근거만_없고_판정은_같다(self):
        res = run(load(exclusion_answers={}))
        c = [x for x in res.checks if x.id == "use_change_impossible"][0]
        self.assertEqual(c.status, "unknown")
        self.assertNotIn("용도지역", c.detail)

    def test_용도지역으로_자동_제외하지_않는다(self):
        """조례 위임이라 전국 공통 표를 만들 수 없다 — 판정을 지어내지 않는다."""
        inp = load_inputs("data/buildings/esquisse-gasan", DATA)
        res = check(inp.exclusions, inp.building, inp.floors)
        self.assertFalse(
            [c for c in res.excluded if c.id == "use_change_impossible"]
        )


class TestGrade(unittest.TestCase):
    """LH 공고의 3구분을 그대로 쓴다 — 통과 / 조건부 통과 / 매입제외."""

    def test_제외가_미확인보다_우선한다(self):
        res = run(load(exclusion_answers={"legal_dispute": True}))
        self.assertTrue(res.unknown)
        self.assertEqual(res.grade, "매입제외")

    def test_요약에_사유가_들어간다(self):
        res = run(load(exclusion_answers={"access_road": True}))
        self.assertIn("진입도로", res.summary)


class TestDeterminism(unittest.TestCase):
    def test_같은_입력이면_같은_판정(self):
        self.assertEqual(run(load()), run(load()))


if __name__ == "__main__":
    unittest.main()
