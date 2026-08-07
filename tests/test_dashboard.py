import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine.contracts import load_inputs
from engine.dashboard import MARKER, _building_payload, build_payload, render
from engine.dashboard import write as write_dashboard
from engine.pipeline import analyze, recommend

DATA = "data"
SMOKE = Path(__file__).with_name("smoke_dashboard.mjs")


def payload_for(dirs=("tests/golden/G2", "data/buildings/esquisse-gasan")):
    buildings, rules_version, grid_mm = [], None, None
    for d in dirs:
        inp = load_inputs(d, DATA)
        rules_version, grid_mm = inp.rules.version, inp.rules.grid_mm
        analyses = {s: analyze(inp, s) for s in inp.units.strategies}
        best, reasons = recommend(analyses)
        buildings.append(_building_payload(analyses, best, reasons))
    return build_payload(buildings, rules_version, grid_mm, "2026-08-07T19:00:00+09:00")


class TestRecommend(unittest.TestCase):
    def test_공급_최다안을_고른다(self):
        inp = load_inputs("data/buildings/esquisse-gasan", DATA)
        analyses = {s: analyze(inp, s) for s in inp.units.strategies}
        # 16 / 11 / 4 — 동점 없음
        best, reasons = recommend(analyses)
        self.assertEqual(best, "supply")
        self.assertIn("최다", reasons[0])

    def test_세대수와_재사용률이_같으면_덜_뜯는_안(self):
        # G2 는 샤프트가 없어 재사용률이 전부 0%. 주차가 40세대로 묶으므로
        # 공급우선형·균형형이 동수가 되고, 신설 벽체가 갈림길이 된다.
        inp = load_inputs("tests/golden/G2", DATA)
        analyses = {s: analyze(inp, s) for s in inp.units.strategies}
        self.assertEqual(analyses["supply"].caps.supply, 40)
        self.assertEqual(analyses["balanced"].caps.supply, 40)
        self.assertEqual(analyses["supply"].quantities["shaft_reuse_ratio"], 0.0)
        self.assertEqual(analyses["balanced"].quantities["shaft_reuse_ratio"], 0.0)
        best, reasons = recommend(analyses)
        self.assertEqual(best, "balanced")
        joined = " ".join(reasons)
        self.assertIn("신설 벽체", joined)
        # 0% vs 0% 같은 무의미한 근거가 나오면 안 된다
        self.assertNotIn("0% vs 0%", joined)

    def test_동수면_설비_재사용률이_높은_안(self):
        inp = load_inputs("tests/golden/G3", DATA)
        analyses = {s: analyze(inp, s) for s in inp.units.strategies}
        # 공급우선형과 균형형 모두 주차 상한 60세대에 걸린다
        self.assertEqual(analyses["supply"].caps.supply, 60)
        self.assertEqual(analyses["balanced"].caps.supply, 60)
        self.assertGreater(
            analyses["balanced"].quantities["shaft_reuse_ratio"],
            analyses["supply"].quantities["shaft_reuse_ratio"],
        )
        best, reasons = recommend(analyses)
        self.assertEqual(best, "balanced")
        self.assertIn("재사용률", " ".join(reasons))


class TestPayload(unittest.TestCase):
    def setUp(self):
        self.p = payload_for()

    def test_건물마다_3안이_들어간다(self):
        self.assertEqual(len(self.p["buildings"]), 2)
        for b in self.p["buildings"]:
            self.assertEqual(set(b["strategies"]), {"supply", "balanced", "minimal"})
            self.assertIn(b["recommended"], b["strategies"])
            self.assertTrue(b["recommend_reasons"])

    def test_층마다_SVG_가_있다(self):
        for b in self.p["buildings"]:
            for s in b["strategies"].values():
                self.assertEqual(
                    sorted(s["svgs"]), sorted(b["floors_analyzed"])
                )
                for svg in s["svgs"].values():
                    self.assertTrue(svg.startswith("<svg"))

    def test_단가나_금액이_들어있지_않다(self):
        flat = json.dumps(self.p, ensure_ascii=False)
        for word in ("단가 ", "총사업비", "원/", "만원"):
            self.assertNotIn(word, flat)


class TestRender(unittest.TestCase):
    def test_자리표시자가_치환된다(self):
        html = render(payload_for(("tests/golden/G2",)))
        self.assertNotIn(MARKER, html)
        self.assertIn("window.__RESPACE__", html)

    def test_스크립트_조기종료가_없다(self):
        # SVG 안의 </svg> 등이 스크립트 블록을 끊으면 안 된다.
        html = render(payload_for(("tests/golden/G2",)))
        m = re.search(r"<script>window\.__RESPACE__ = (.*?);</script>", html, re.S)
        self.assertIsNotNone(m)
        self.assertNotIn("</script>", m.group(1))
        self.assertEqual(json.loads(m.group(1))["grid_mm"], 600)

    def test_데이터가_앱_스크립트보다_먼저_온다(self):
        html = render(payload_for(("tests/golden/G2",)))
        self.assertLess(
            html.index("window.__RESPACE__"), html.index("const D = window.__RESPACE__")
        )

    def test_외부_리소스를_참조하지_않는다(self):
        # 오프라인·file:// 에서 더블클릭으로 열려야 한다.
        html = render(payload_for(("tests/golden/G2",)))
        for tag in ("<link ", "src=\"http", "@import", "cdn."):
            self.assertNotIn(tag, html)

    def test_파일로_쓰인다(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_dashboard(payload_for(("tests/golden/G2",)), f"{tmp}/d.html")
            self.assertTrue(p.exists())
            self.assertGreater(p.stat().st_size, 10_000)


@unittest.skipIf(shutil.which("node") is None, "node 없음 — JS 스모크 생략")
class TestJavaScript(unittest.TestCase):
    """DOM 스텁으로 실제 렌더 로직을 돌린다. 브라우저 없이 검증 가능한 범위."""

    def test_4개_탭이_모두_렌더된다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_dashboard(payload_for(), f"{tmp}/d.html")
            r = subprocess.run(
                ["node", str(SMOKE), str(path)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("전부 통과", r.stdout)


if __name__ == "__main__":
    unittest.main()
