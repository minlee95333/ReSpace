import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from engine.contracts import load_inputs
from engine.emit import FILL, build_result, build_svg, write
from engine.pipeline import analyze

DATA = "data"


def run(building_dir="tests/golden/G2", strategy="supply"):
    return analyze(load_inputs(building_dir, DATA), strategy)


class TestResultJson(unittest.TestCase):
    def setUp(self):
        self.r = build_result(run(), "2026-08-07T19:00:00+09:00")

    def test_최상위_구조(self):
        self.assertEqual(
            set(self.r),
            {"meta", "per_floor", "caps", "quantities", "verdict", "disclaimer"},
        )

    def test_입력_해시가_들어간다(self):
        h = self.r["meta"]["input_hash"]
        self.assertEqual(
            set(h),
            {"rules.json", "units.json", "building.json", "floor_plan_01.json"},
        )
        for v in h.values():
            self.assertTrue(v.startswith("sha256:"))

    def test_격자_원점이_들어간다(self):
        # 결과를 원래 좌표계로 되돌리려면 격자 크기와 원점이 함께 필요하다.
        self.assertEqual(self.r["meta"]["grid_mm"], 600)
        self.assertEqual(self.r["meta"]["grid_origin_mm"], [0, 0])

    def test_면책문구가_붙는다(self):
        self.assertIn("전문가", self.r["disclaimer"])

    def test_병목이_명시된다(self):
        self.assertEqual(self.r["caps"]["bottleneck"], "parking")
        self.assertEqual(self.r["caps"]["bottleneck_label"], "주차")
        self.assertFalse(self.r["caps"]["complete"])

    def test_미확보_축은_null_과_사유를_함께_낸다(self):
        septic = next(a for a in self.r["caps"]["axes"] if a["axis"] == "septic")
        self.assertIsNone(septic["value"])
        self.assertTrue(septic["blocked_reason"])

    def test_센티널이_새지_않는다(self):
        # 샤프트가 없는 건물에서 내부 정렬용 큰 수가 결과로 나가면 안 된다.
        self.assertNotIn("1000000", json.dumps(self.r))

    def test_JSON_으로_직렬화된다(self):
        s = json.dumps(self.r, ensure_ascii=False)
        self.assertEqual(json.loads(s)["caps"]["supply"], 40)


class TestDeterminism(unittest.TestCase):
    def test_시각을_빼면_바이트_단위로_같다(self):
        a = json.dumps(build_result(run(), None), ensure_ascii=False, sort_keys=True)
        b = json.dumps(build_result(run(), None), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b)

    def test_시각은_호출자가_넘긴다(self):
        # 엔진이 시계를 읽으면 회귀 비교가 불가능해진다.
        self.assertIsNone(build_result(run())["meta"]["generated_at"])
        self.assertEqual(
            build_result(run(), "X")["meta"]["generated_at"], "X"
        )


class TestSvg(unittest.TestCase):
    def setUp(self):
        self.a = run()
        self.svg = build_svg(self.a.floors[0], "테스트")

    def test_유효한_XML_이다(self):
        root = ET.fromstring(self.svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_유닛이_외곽_안에_있고_겹치지_않는다(self):
        root = ET.fromstring(self.svg)
        rects = [
            (
                e.get("fill"),
                float(e.get("x")), float(e.get("y")),
                float(e.get("width")), float(e.get("height")),
            )
            for e in root.iter()
            if e.tag.endswith("rect") and e.get("width") != "100%"
        ]
        units = [r for r in rects if r[0] == FILL["youth"]]
        border = [r for r in rects if r[0] == "none"][0]
        self.assertEqual(len(units), 20)

        _, bx, by, bw, bh = border
        for _, x, y, w, h in units:
            self.assertGreaterEqual(x, bx - 0.01)
            self.assertGreaterEqual(y, by - 0.01)
            self.assertLessEqual(x + w, bx + bw + 0.01)
            self.assertLessEqual(y + h, by + bh + 0.01)

        for i in range(len(units)):
            for j in range(i + 1, len(units)):
                _, x1, y1, w1, h1 = units[i]
                _, x2, y2, w2, h2 = units[j]
                overlap = x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1
                self.assertFalse(overlap, f"{units[i]} vs {units[j]}")

    def test_치수가_실제_유닛과_맞는다(self):
        root = ET.fromstring(self.svg)
        sizes = {
            (float(e.get("width")), float(e.get("height")))
            for e in root.iter()
            if e.tag.endswith("rect") and e.get("fill") == FILL["youth"]
        }
        # 3000×6000mm × 0.02 px/mm
        self.assertEqual(sizes, {(60.0, 120.0)})


class TestWrite(unittest.TestCase):
    def test_층마다_SVG_가_나온다(self):
        a = run()
        with tempfile.TemporaryDirectory() as tmp:
            files = write(a, tmp, "2026-08-07T19:00:00+09:00")
            names = sorted(p.name for p in files)
            self.assertEqual(
                names,
                ["floor_01.svg", "floor_02.svg", "floor_03.svg",
                 "floor_04.svg", "floor_05.svg", "result.json"],
            )
            loaded = json.loads(
                (Path(tmp) / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(loaded["per_floor"]), 5)


if __name__ == "__main__":
    unittest.main()
