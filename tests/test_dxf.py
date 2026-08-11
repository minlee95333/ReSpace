"""DXF 자동 판독. 픽스처는 tests/fixtures/dxf 의 **합성** 도면이다.

검증하는 것은 판독 규칙이다 — 사람이 레이어를 지정하지 않고도 역할을 가려내는가,
그리고 **못 읽을 때 추측하지 않고 멈추는가**.
"""

import unittest
from pathlib import Path

from engine.contracts import FloorPlan, load_json
from engine.adapters.dxf import DxfError, convert, parse, read_text, snap_poly_inward

FIX = Path("tests/fixtures/dxf")
LEX = Path("data/dxf_lexicon.json")
GRID = 600


def run(name: str, floor: int = 3) -> dict:
    return convert(FIX / f"{name}.dxf", floor, GRID, LEX)


class TestTextFirst(unittest.TestCase):
    """레이어명이 아니라 실명 텍스트로 역할을 정한다."""

    def test_계단실과_승강기를_구분한다(self):
        p = run("basic")
        types = sorted(c["type"] for c in p["cores"])
        self.assertEqual(types, ["ev", "stair"])

    def test_샤프트를_찾는다(self):
        self.assertEqual(len(run("basic")["shafts"]), 1)

    def test_같은_레이어에_있어도_텍스트로_갈린다(self):
        """계단실·EV·PS·화장실이 전부 A-AREA 레이어다. 레이어만 보면 구분이 안 된다."""
        p = run("basic")
        self.assertEqual(len(p["cores"]), 2)
        self.assertEqual(len(p["shafts"]), 1)
        wet = [r for r in p["_detected"]["기타실"] if r["role"] == "wet"]
        self.assertEqual(len(wet), 1)

    def test_영문_레이어_도면도_읽는다(self):
        """레이어명이 KS F 1542 형식이어도 결과가 같아야 한다 — 3순위 신호일 뿐이다."""
        a, b = run("basic"), run("english_layers")
        self.assertEqual(a["cores"], b["cores"])
        self.assertEqual(len(a["windows"]), len(b["windows"]))

    def test_cp949_도면도_읽는다(self):
        self.assertEqual(run("basic")["cores"], run("basic_cp949")["cores"])


class TestUnits(unittest.TestCase):
    def test_INSUNITS_로_배율을_잡는다(self):
        mm, m = run("basic"), run("meters")
        self.assertEqual(mm["boundary"], m["boundary"])
        self.assertIn("$INSUNITS", m["_assumptions"]["단위배율"])

    def test_INSUNITS_가_없으면_크기로_추정한다(self):
        p = run("no_insunits_mm")
        self.assertEqual(p["boundary"], run("basic")["boundary"])
        self.assertIn("추정", p["_assumptions"]["단위배율"])

    def test_애매하면_추측하지_않고_실패한다(self):
        """배율을 틀리면 모든 수치가 조용히 틀어진다. 조용한 오류보다 멈추는 편이 낫다."""
        with self.assertRaises(DxfError) as ctx:
            run("ambiguous_units")
        self.assertIn("단위", str(ctx.exception))


class TestConservativeSnap(unittest.TestCase):
    """스냅은 전부 세대수가 늘지 않는 방향이다."""

    def test_외곽은_안쪽으로_줄어든다(self):
        # 도면 외곽은 30010 × 15010. 격자에 맞추며 커지면 없는 바닥이 생긴다.
        p = run("basic")
        xs = [pt[0] for pt in p["boundary"]]
        ys = [pt[1] for pt in p["boundary"]]
        self.assertEqual(max(xs), 30000)
        self.assertEqual(max(ys), 15000)

    def test_코어는_바깥으로_커진다(self):
        # 계단실 원본 3600×4800 → 격자 정렬로 4200×5400 이상이어야 한다.
        stair = [c for c in run("basic")["cores"] if c["type"] == "stair"][0]
        _, _, w, h = stair["rect"]
        self.assertGreaterEqual(w, 3600)
        self.assertGreaterEqual(h, 4800)

    def test_스냅_방향_보조함수(self):
        # 정사각형을 살짝 키운 도형이 원래 격자 크기로 줄어든다
        poly = [(10, 10), (1210, 10), (1210, 1210), (10, 1210)]
        self.assertEqual(
            snap_poly_inward(poly, 600),
            [(600, 600), (1200, 600), (1200, 1200), (600, 1200)],
        )

    def test_모든_좌표가_격자에_맞는다(self):
        p = run("basic")
        vals = [v for pt in p["boundary"] for v in pt]
        for c in p["cores"]:
            vals += c["rect"]
        for s in p["shafts"]:
            vals += s["rect"]
        for w in p["windows"]:
            vals += w["start"] + w["end"]
        for v in vals:
            self.assertEqual(v % GRID, 0, f"{v} 가 격자 배수가 아니다")


class TestRefusal(unittest.TestCase):
    """못 읽으면 멈춘다. 이 어댑터의 존재 이유다."""

    def test_계단실이_없으면_실패한다(self):
        with self.assertRaises(DxfError) as ctx:
            run("no_stair")
        msg = str(ctx.exception)
        self.assertIn("계단실", msg)
        # 무엇을 읽었는지 보여줘야 사전을 고칠 수 있다
        self.assertIn("E/V", msg)
        self.assertIn("dxf_lexicon", msg)

    def test_DXF_가_아니면_실패한다(self):
        with self.assertRaises(DxfError) as ctx:
            run("not_dxf")
        self.assertIn("DXF", str(ctx.exception))

    def test_창이_없으면_경고를_남긴다(self):
        """조용히 0세대를 내지 않고 왜 그런지 밝힌다."""
        p = run("no_windows")
        self.assertEqual(p["windows"], [])
        self.assertTrue(any("창" in w for w in p["_warnings"]))


class TestProvenance(unittest.TestCase):
    def test_출처는_재구성이다(self):
        self.assertEqual(run("basic")["status"], "reconstructed")

    def test_가정한_값을_숨기지_않는다(self):
        """창의 입면 치수는 평면도에 없다. 가정임을 결과에 남긴다."""
        a = run("basic")["_assumptions"]
        self.assertIn("측정값 아님", a["창_입면치수"])
        self.assertIn("가정", a["창_입면치수"])

    def test_무엇을_찾았는지_센다(self):
        d = run("basic")["_detected"]
        self.assertEqual(d["코어"], 2)
        self.assertEqual(d["샤프트"], 1)
        self.assertEqual(d["기둥"], 6)
        self.assertEqual(d["창"], 5)


class TestContractFit(unittest.TestCase):
    """판독 결과가 엔진 계약에 그대로 들어가는가."""

    def test_FloorPlan_으로_로딩된다(self):
        fp = FloorPlan.from_dict(run("basic", floor=3), GRID)
        self.assertEqual(fp.floor, 3)
        self.assertEqual(fp.status, "reconstructed")
        self.assertTrue(fp.is_trustworthy)
        self.assertEqual(len(fp.stair_cores()), 1)

    def test_사전은_프로젝트에_하나다(self):
        lex = load_json(LEX)
        self.assertIn("room_terms", lex)
        self.assertIn("stair", lex["room_terms"])
        self.assertIn("layer_hints", lex)


class TestDeterminism(unittest.TestCase):
    def test_같은_도면이면_같은_결과(self):
        self.assertEqual(run("basic"), run("basic"))

    def test_파싱이_손상을_조용히_넘기지_않는다(self):
        text = read_text(FIX / "basic.dxf")
        broken = text.replace("SECTION", "SECTION\n", 1)  # 줄 짝이 어긋난다
        with self.assertRaises(DxfError):
            parse(broken)


if __name__ == "__main__":
    unittest.main()
