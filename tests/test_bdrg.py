"""건축물대장 어댑터.

픽스처가 두 종류다.

- `tests/fixtures/bdrg/*.json` — **합성**. 경계 조건을 골라 만든 것.
- `tests/fixtures/bdrg/real/*.json` — **실제 API 응답** (2026-08-10 수집, 강남구 역삼동).

합성만으로는 부족하다. 내가 만든 픽스처에는 내 가정이 그대로 반영되므로 가정이
틀려도 통과한다. 실제로 아래 셋이 실 응답에서 드러났다.

1. `modeCdNm` 은 시설 형식이 아니라 **처리공법**이다 (접촉폭기방법 등)
2. `capaLube`(㎥)는 거의 항상 0 이고 `capaPsper`(인원)가 채워진다
3. 한 대지에 분류가 다른 오수시설이 함께 등재되고, 지상층수가 0 인 대장도 있다
"""

import json
import unittest
from pathlib import Path

from engine.adapters.bdrg import AdapterError, _from_env_file, _items, _url, build
from engine.contracts import Building, ContractError, Rules, load_json

FIX = Path("tests/fixtures/bdrg")


def cache(title="title", floor="floor", wclf="wclf") -> dict:
    return {
        "title": json.loads((FIX / f"{title}.json").read_text(encoding="utf-8")),
        "floor": json.loads((FIX / f"{floor}.json").read_text(encoding="utf-8")),
        "wclf": json.loads((FIX / f"{wclf}.json").read_text(encoding="utf-8")),
    }


class TestEnvelope(unittest.TestCase):
    """공공데이터포털 공통 응답의 함정을 어댑터가 흡수하는가."""

    def test_item_이_하나면_dict_로_온다(self):
        one = json.loads((FIX / "title_single.json").read_text(encoding="utf-8"))
        self.assertEqual(len(_items(one)), 1)

    def test_빈_결과는_빈_목록이다(self):
        empty = json.loads((FIX / "wclf_empty.json").read_text(encoding="utf-8"))
        self.assertEqual(_items(empty), [])

    def test_키는_URL_에_그대로_들어간다(self):
        url = _url("title", "KEY", {"sigunguCd": "11680", "bun": "0001"})
        self.assertIn("getBrTitleInfo", url)
        self.assertIn("serviceKey=KEY", url)
        self.assertIn("_type=json", url)


class TestMapping(unittest.TestCase):
    def setUp(self):
        self.b = build(cache(), name="시험동")

    def test_층수와_용도(self):
        self.assertEqual(self.b["floors_total"], 5)
        self.assertEqual(self.b["use"], "업무시설")
        self.assertEqual(self.b["_detail"]["지하층수"], 1)

    def test_주차는_4종_합계다(self):
        self.assertEqual(self.b["parking_existing"], 20)  # 12+6+2+0
        parts = self.b["_detail"]["주차_내역"]
        self.assertEqual(parts["옥내자주식"], 12)
        self.assertNotIn("옥외기계식", parts)  # 0 은 '없음'이라 남기지 않는다

    def test_연면적은_부설주차장을_뺀다(self):
        """정화조 인원산정식의 A 는 부설주차장을 제외한 바닥면적이다.
        전체를 넣으면 인원이 과대 산정되어 정화조 축이 후해진다."""
        d = self.b["_detail"]
        self.assertEqual(d["연면적_전체"], 2700.0)      # 450 × 6개층
        self.assertEqual(self.b["gfa_m2"], 2250.0)       # 주차장 450 제외
        self.assertEqual(len(d["제외한_층"]), 1)
        self.assertIn("주차장", d["제외한_층"][0])

    def test_오수처리_인원과_형식(self):
        """대장은 용량(㎥)이 아니라 처리대상인원을 싣는다 — 실 표본에서 ㎥ 는 대개 0."""
        self.assertEqual(self.b["septic_capacity_persons"], 290.0)
        self.assertIsNone(self.b["septic_capacity_m3"])
        self.assertEqual(self.b["septic_mode_raw"], "부패탱크방법")
        self.assertEqual(self.b["septic_mode_code"], "201")

    def test_용량만_있는_경우도_읽는다(self):
        b = build(cache(wclf="wclf_volume_only"))
        self.assertEqual(b["septic_capacity_m3"], 30.0)
        self.assertIsNone(b["septic_capacity_persons"])

    def test_사용승인일에서_연도를_뽑는다(self):
        self.assertEqual(self.b["approval_year"], 2010)

    def test_내진은_적용_여부로_읽는다(self):
        self.assertTrue(self.b["seismic"])


class TestHonesty(unittest.TestCase):
    """없는 값을 지어내지 않는가. 이 어댑터의 존재 이유다."""

    def test_대장에_없는_항목은_null_이다(self):
        b = build(cache())
        for field in ("fire_resistant", "floor_height_mm", "floors_residential"):
            with self.subTest(field):
                self.assertIsNone(b[field])

    def test_위반건축물은_수집하지_않으므로_null_이다(self):
        b = build(cache())
        self.assertIsNone(b["violation"])
        self.assertIn("기본개요", b["_detail"]["_violation_note"])

    def test_공공하수도_연결이면_용량이_비고_형식만_남는다(self):
        b = build(cache(wclf="wclf_public"))
        self.assertIsNone(b["septic_capacity_m3"])
        self.assertIsNone(b["septic_capacity_persons"])
        self.assertEqual(b["septic_mode_code"], "300")

    def test_오수정화시설_기록이_없으면_전부_null_이다(self):
        b = build(cache(wclf="wclf_empty"))
        for f in ("septic_capacity_m3", "septic_capacity_persons",
                  "septic_mode_raw", "septic_mode_code"):
            with self.subTest(f):
                self.assertIsNone(b[f])

    def test_표제부가_비면_조용히_넘어가지_않는다(self):
        empty = json.loads((FIX / "wclf_empty.json").read_text(encoding="utf-8"))
        with self.assertRaises(AdapterError):
            build({"title": empty, "floor": empty, "wclf": empty})


class TestContractFit(unittest.TestCase):
    """어댑터 출력이 엔진 계약에 그대로 들어가는가."""

    def test_building_계약으로_로딩된다(self):
        b = Building.from_dict(build(cache()))
        self.assertEqual(b.floors_total, 5)
        self.assertEqual(b.parking_existing, 20)
        self.assertEqual(b.septic_capacity_persons, 290.0)
        self.assertEqual(b.septic_mode_code, "201")

    def test_형식코드가_규칙에_걸린다(self):
        rules = Rules.from_dict(load_json("data/rules.json"))
        for fx, expect in (("wclf", "septic_tank"),
                           ("wclf_public", "public_sewer"),
                           ("wclf_sewage", "sewage_treatment")):
            with self.subTest(fx):
                b = Building.from_dict(build(cache(wclf=fx)))
                mode = rules.septic.mode_for(b.septic_mode_raw, b.septic_mode_code)
                self.assertEqual(mode.id, expect)


class TestZoning(unittest.TestCase):
    """용도지역은 **수집만** 한다. 판정하지 않는 것이 결론이다 (미결정 ⑥)."""

    CACHE = Path("data/buildings/esquisse-gasan/_api_cache")

    def test_실제_응답에서_지정사항을_구분별로_모은다(self):
        from engine.adapters.bdrg import load_cache
        z = build(load_cache(self.CACHE))["zoning"]
        self.assertEqual(z["용도지역코드"], ["상업지역"])
        self.assertIn("용도지구코드", z)
        self.assertIn("용도구역코드", z)

    def test_지역지구구역_캐시가_없어도_돈다(self):
        """나중에 추가된 오퍼레이션이라 기존 캐시에는 없다."""
        b = build(cache())
        self.assertEqual(b["zoning"], {})

    def test_주택_허용_여부를_판정하지_않는다(self):
        """조례 위임이 많아 전국 공통 표를 만들 수 없다. 표를 만들면 틀린다."""
        from engine.adapters.bdrg import load_cache
        b = build(load_cache(self.CACHE))
        flat = json.dumps(b, ensure_ascii=False)
        for word in ("주택허용", "housing_allowed", "허용여부"):
            self.assertNotIn(word, flat)
        self.assertIn("판정하지 않는다", b["_detail"]["_zoning_note"])

    def test_위반건축물은_수집_불가로_명시한다(self):
        b = build(cache())
        self.assertIsNone(b["violation"])
        self.assertIn("수집할 수 없다", b["_detail"]["_violation_note"])


class TestKeyLoading(unittest.TestCase):
    """`setx` 로 넣은 환경변수는 이미 떠 있는 프로세스에 상속되지 않는다.
    파일에서 읽는 경로가 있어야 셸을 재시작하지 않고도 돈다."""

    def test_env_파일에서_읽는다(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            f.write_text(
                '# 주석\n\nOTHER=x\nDATA_GO_KR_KEY="abc123"\n', encoding="utf-8"
            )
            self.assertEqual(_from_env_file("DATA_GO_KR_KEY", f), "abc123")
            self.assertEqual(_from_env_file("OTHER", f), "x")
            self.assertIsNone(_from_env_file("NOPE", f))

    def test_파일이_없으면_None(self):
        self.assertIsNone(_from_env_file("X", Path("없는파일.env")))


class TestRealResponses(unittest.TestCase):
    """**실제 API 응답**으로 만든 픽스처 (2026-08-10 수집, 서울 강남구 역삼동).

    합성 픽스처는 내가 만든 것이라 내 가정이 그대로 반영된다. 실 응답이라야
    가정이 틀렸을 때 드러난다 — 실제로 `modeCdNm` 이 형식이 아니라 공법이라는 것과
    `capaLube` 가 거의 항상 0 이라는 것이 여기서 드러났다.
    """

    REAL = FIX / "real"

    def real(self, kind: str) -> dict:
        return {
            op: json.loads((self.REAL / f"{kind}_{op}.json").read_text(encoding="utf-8"))
            for op in ("title", "floor", "wclf")
        }

    def test_실제_코드가_규칙에_걸린다(self):
        rules = Rules.from_dict(load_json("data/rules.json"))
        for kind, code in (("septic_tank", "201"), ("sewage_treatment", "102")):
            with self.subTest(kind):
                draft = build(self.real(kind))
                self.assertEqual(draft["septic_mode_code"], code)
                mode = rules.septic.mode_for(
                    draft["septic_mode_raw"], draft["septic_mode_code"]
                )
                self.assertEqual(mode.id, kind)

    def test_대장에_층수가_없는_건물이_실제로_있다(self):
        """르메르디앙서울호텔 — 숙박시설 29,731㎡ 인데 대장의 지상층수가 0 이다.

        자동 수집만으로 끝나지 않는 건물이 실제로 있다는 뜻이다. 이때 0 을 그대로
        믿거나 아무 값이나 넣지 않고, 무엇을 채워야 하는지 알려주며 멈춘다.
        """
        draft = build(self.real("sewage_treatment"))
        self.assertIsNone(draft["floors_total"])
        self.assertEqual(draft["use"], "숙박시설")
        with self.assertRaises(ContractError) as ctx:
            Building.from_dict(draft)
        self.assertIn("floors_total", str(ctx.exception))
        self.assertIn("직접 넣을 것", str(ctx.exception))

    def test_층수만_채우면_바로_돈다(self):
        draft = build(self.real("sewage_treatment"))
        draft["floors_total"] = 20  # 사람이 등본에서 확인해 채운 값
        b = Building.from_dict(draft)
        self.assertEqual(b.use, "숙박시설")
        self.assertIsNotNone(b.septic_capacity_persons)

    def test_실제_응답에서_인원이_채워진다(self):
        """설계 가정이 뒤집힌 지점. 용량(㎥)이 아니라 인원이 온다."""
        b = Building.from_dict(build(self.real("septic_tank")))
        self.assertIsNotNone(b.septic_capacity_persons)
        self.assertIsNone(b.septic_capacity_m3)

    def test_분류가_섞인_대지에서는_제약이_있는_쪽을_택한다(self):
        """한 대지에 정화조(201)와 하수종말처리장연결(300)이 함께 등재된 실제 사례.

        연결 쪽을 택하면 정화조 축이 사라져 세대수가 후해진다. 확인 전까지는
        제약이 남는 쪽이 안전하다. 상충 사실은 그대로 남긴다.
        """
        raw = build(self.real("mixed"))
        self.assertEqual(raw["septic_mode_code"], "201")
        detail = raw["_detail"]["오수정화시설_원본"]
        self.assertTrue(detail["분류상충"])
        codes = {r["코드"] for r in detail["전체기록"]}
        self.assertEqual(codes, {"201", "300"})
        self.assertIn("등본으로 확인", detail["_대표선정"])

    def test_실제_응답이_계약을_통과한다(self):
        for kind in ("septic_tank", "mixed"):
            with self.subTest(kind):
                b = Building.from_dict(build(self.real(kind)))
                self.assertGreater(b.floors_total or 0, 0)
                self.assertTrue(b.use)


class TestDeterminism(unittest.TestCase):
    def test_같은_캐시면_같은_출력(self):
        self.assertEqual(build(cache(), "x"), build(cache(), "x"))


if __name__ == "__main__":
    unittest.main()
