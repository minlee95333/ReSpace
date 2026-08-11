"""건축물대장 API → building.json.

LH 가 받는 신청 서류 묶음 원본은 대외비다. 그러나 그 안의 **수치는 대부분 공개**다 —
건축물대장이 표제부·층별개요·오수정화시설을 무료로 개방한다. 막히는 것은 평면 형상뿐이고,
그것은 `dxf` 어댑터가 맡는다.

세 오퍼레이션을 쓴다.

| 오퍼레이션 | 얻는 것 |
|---|---|
| `getBrTitleInfo`   | 층수, 주용도, 주차대수 4종, 승강기, 사용승인일, 내진 |
| `getBrFlrOulnInfo` | 층별 용도·면적 → 연면적 |
| `getBrWclfInfo`    | 오수처리 형식(정화조/공공하수도/오수처리시설), 용량(㎥·인용) |

**응답을 캐시해 커밋한다.** 심사 때 인터넷 없이 같은 결과가 나와야 하고, 나중에
"이 숫자가 어디서 왔나"를 원본으로 되짚을 수 있어야 한다.

**없는 값을 지어내지 않는다.** 응답에 없거나 0 이면 None 으로 두어 엔진이
`blocked_reason` 을 내게 한다. 그것이 이 시스템의 유일한 정직성 장치다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: 국토교통부 건축HUB 건축물대장정보 서비스 (공공데이터포털 15134735).
BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"

OPS = {
    "title": "getBrTitleInfo",
    "floor": "getBrFlrOulnInfo",
    "wclf": "getBrWclfInfo",
    "jijigu": "getBrJijiguInfo",
}

#: 캐시가 없어도 되는 오퍼레이션. 나중에 추가된 것이라 기존 캐시에는 없다.
OPTIONAL_OPS = ("jijigu",)

KEY_ENV = "DATA_GO_KR_KEY"

#: 부설주차장은 오수가 발생하지 않아 정화조 인원산정 면적에서 뺀다
#: (기후에너지환경부고시 제2025-165호 별표 각주 2).
_PARKING_WORDS = ("주차장", "주차")


class AdapterError(RuntimeError):
    pass


# ---------------------------------------------------------------- 호출


def _url(op: str, key: str, params: dict) -> str:
    q = {
        "serviceKey": key,
        "_type": "json",
        "numOfRows": "500",
        "pageNo": "1",
        **params,
    }
    return f"{BASE}/{OPS[op]}?" + urllib.parse.urlencode(q, safe="")


def _items(payload: dict) -> list[dict]:
    """공공데이터포털 공통 응답에서 item 목록만 꺼낸다.

    항목이 1개면 dict, 여러 개면 list 로 오는 흔한 함정을 여기서 흡수한다.
    """
    body = (payload.get("response") or {}).get("body") or {}
    items = body.get("items")
    if not items:
        return []
    if isinstance(items, str):  # 빈 결과를 문자열로 주는 경우가 있다
        return []
    item = items.get("item") if isinstance(items, dict) else items
    if item is None:
        return []
    return item if isinstance(item, list) else [item]


#: 공공데이터포털은 정상 키로도 간헐적으로 503 을 낸다 (2026-08-10 확인).
#: 재시도로 흡수하되, 계속 실패하면 조용히 넘기지 않고 그대로 알린다.
_RETRY_STATUS = (429, 500, 502, 503, 504)
_RETRIES = 4
_BACKOFF_S = 1.5


def fetch(op: str, key: str, params: dict, timeout: int = 30) -> dict:
    url = _url(op, key, params)
    last: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                raw = r.read().decode("utf-8")
            # 호출량 제한에 걸리면 200 에 빈 본문이 오기도 한다. 재시도 대상이다.
            if not raw.strip():
                last = AdapterError(f"{OPS[op]} 응답 본문이 비어 있다")
                if attempt < _RETRIES - 1:
                    time.sleep(_BACKOFF_S * (attempt + 1))
                    continue
                raise last
            break
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in _RETRY_STATUS:
                raise AdapterError(f"{OPS[op]} 호출 실패: HTTP {e.code} {e.reason}") from e
        except Exception as e:  # noqa: BLE001 — 네트워크 실패 원인을 그대로 보여준다
            last = e
        if attempt < _RETRIES - 1:
            time.sleep(_BACKOFF_S * (attempt + 1))
    else:
        raise AdapterError(
            f"{OPS[op]} 호출이 {_RETRIES}회 모두 실패했다: "
            f"{type(last).__name__} {last}. 공공데이터포털이 불안정할 때가 있으니 "
            f"잠시 후 다시 시도할 것."
        ) from last
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        # 키가 잘못되면 XML 오류를 돌려준다. 원문 앞부분을 보여주는 편이 빠르다.
        raise AdapterError(
            f"{OPS[op]} 응답이 JSON 이 아니다 (키 오류일 가능성이 높다):\n{raw[:400]}"
        ) from e
    head = (payload.get("response") or {}).get("header") or {}
    if head.get("resultCode") not in (None, "00", "0"):
        raise AdapterError(
            f"{OPS[op]} 오류 {head.get('resultCode')}: {head.get('resultMsg')}"
        )
    return payload


def fetch_all(key: str, params: dict, cache_dir: Path) -> dict[str, dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for op in OPS:
        payload = fetch(op, key, params)
        path = cache_dir / f"{op}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        out[op] = payload
    (cache_dir / "_query.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def load_cache(cache_dir: Path) -> dict[str, dict]:
    out = {}
    for op in OPS:
        path = cache_dir / f"{op}.json"
        if not path.exists():
            if op in OPTIONAL_OPS:
                continue
            raise AdapterError(
                f"{path} 가 없다. 먼저 --fetch 로 받아 캐시를 만들 것."
            )
        out[op] = json.loads(path.read_text(encoding="utf-8"))
    return out


# ---------------------------------------------------------------- 매핑


def _num(v, cast=float):
    """대장 수치는 문자열로 오고 빈 값이 ''·'0' 로 온다. 0 은 '없음'으로 본다."""
    if v in (None, "", "0", 0):
        return None
    try:
        n = cast(v)
    except (TypeError, ValueError):
        return None
    return n or None


def _title(payload: dict) -> dict:
    items = _items(payload)
    if not items:
        raise AdapterError(
            "표제부 응답이 비어 있다. 시군구·법정동 코드와 번지를 확인할 것."
        )
    # 부속건축물(창고·주차타워 등)은 주동이 아니다. 있으면 주건축물만 본다.
    main = [it for it in items if "주건축물" in str(it.get("mainAtchGbCdNm") or "")]
    pool = main or items
    # 한 대지에 동이 여럿이면 연면적이 가장 큰 동을 주동으로 본다.
    return max(pool, key=lambda it: _num(it.get("totArea")) or 0.0)


def _gfa(payload: dict, dong: str | None = None) -> tuple[float | None, float | None, list[str]]:
    """층별개요 → (부설주차장 제외 연면적, 전체 연면적, 제외한 층 설명).

    정화조 인원산정식의 A 는 '당해 용도로 사용되는 바닥면적(부설주차장 제외)' 이다.
    전체 연면적을 그대로 넣으면 인원이 과대 산정되어 정화조 축이 후해진다.

    한 대지에 동이 여럿이면 층별개요가 전 동을 함께 준다. 표제부에서 고른 동만
    센다 — 안 그러면 옆 동 면적까지 합쳐진다.
    """
    total = 0.0
    net = 0.0
    dropped: list[str] = []
    for it in _items(payload):
        if dong and str(it.get("dongNm") or "").strip() != dong:
            continue
        area = _num(it.get("area"))
        if area is None:
            continue
        total += area
        purpose = str(it.get("mainPurpsCdNm") or "") + str(it.get("etcPurps") or "")
        if any(w in purpose for w in _PARKING_WORDS):
            dropped.append(f"{it.get('flrNoNm') or it.get('flrNo')} {purpose} {area}㎡")
            continue
        net += area
    return (round(net, 2) or None, round(total, 2) or None, dropped)


def _parking(title: dict) -> tuple[int | None, dict]:
    parts = {
        "옥내자주식": _num(title.get("indrAutoUtcnt"), int),
        "옥외자주식": _num(title.get("oudrAutoUtcnt"), int),
        "옥내기계식": _num(title.get("indrMechUtcnt"), int),
        "옥외기계식": _num(title.get("oudrMechUtcnt"), int),
    }
    known = [v for v in parts.values() if v is not None]
    total = sum(known) if known else None
    return total, {k: v for k, v in parts.items() if v is not None}


def _septic(payload: dict) -> tuple[float | None, float | None, str | None, str | None, dict]:
    """→ (용량㎥, 처리대상인원, 형식명, 형식코드, 원본)

    실 API 표본에서 `capaLube`(㎥)는 거의 전부 0 이고 `capaPsper`(인용)가 채워진다.
    인원이 곧 엔진에 필요한 값이므로 그대로 넘긴다 — 환산하지 않는 편이 정확하다.
    """
    items = _items(payload)
    if not items:
        return None, None, None, None, {}

    # 한 대지에 분류가 다른 기록이 섞이는 경우가 실제로 있다(정화조 + 하수도연결).
    # 제약이 **있는** 쪽을 대표로 삼는다 — 없는 쪽을 택하면 상한이 사라져
    # 세대수가 후해진다. 상충 사실은 그대로 남겨 사람이 볼 수 있게 한다.
    prefixes = {str(x.get("modeCd") or "")[:1] for x in items if x.get("modeCd")}
    limiting = [x for x in items if str(x.get("modeCd") or "").startswith(("1", "2"))]
    pool = limiting or items
    it = max(pool, key=lambda x: _num(x.get("capaPsper")) or 0.0)
    mode = str(it.get("modeCdNm") or "").strip() or None
    if mode in ("기타", "그밖의") and it.get("etcMode"):
        mode = str(it["etcMode"]).strip()
    code = str(it.get("modeCd") or "").strip() or None
    return (
        _num(it.get("capaLube")),
        _num(it.get("capaPsper")),
        mode,
        code,
        {
            "용량_루베": it.get("capaLube"),
            "용량_인용": it.get("capaPsper"),
            "형식코드": it.get("modeCd"),
            "형식": it.get("modeCdNm"),
            "기타형식": it.get("etcMode"),
            "단위": it.get("unitGbCdNm"),
            "시설수": len(items),
            "분류상충": len(prefixes) > 1,
            "전체기록": [
                {"코드": x.get("modeCd"), "형식": x.get("modeCdNm"),
                 "인용": x.get("capaPsper"), "루베": x.get("capaLube")}
                for x in items
            ] if len(prefixes) > 1 else None,
            "_대표선정": (
                "분류(코드 앞자리)가 다른 기록이 섞여 있어 제약이 있는 쪽(1xx·2xx)을 "
                "대표로 삼았다. 공공하수도 연결이 현재 상태라면 정화조 축이 실제로는 "
                "걸리지 않으므로, 등본으로 확인해 직접 정정할 것."
            ) if len(prefixes) > 1 else "기록 1종",
        },
    )


def _zoning(payload: dict | None) -> dict:
    """지역지구구역 → 구분별 목록.

    **판정하지 않고 수집만 한다.** 대장의 이 칸에는 국토계획법 용도지역뿐 아니라
    수도권정비계획법 권역(과밀억제권역), 건축법 지정(가로구역별최고높이제한지역)
    까지 섞여 들어온다. 게다가 주택 허용 여부는 국토계획법 시행령 별표에서
    **조례로 위임된 부분이 많아** 전국 공통 표를 만들 수 없다.

    따라서 사람이 판단할 재료로 보여주기만 하고, 매입제외 판정은 답변으로 받는다.
    """
    if not payload:
        return {}
    out: dict[str, list[str]] = {}
    for it in _items(payload):
        kind = str(it.get("jijiguGbCdNm") or "").strip()
        name = str(it.get("jijiguCdNm") or it.get("etcJijigu") or "").strip()
        if not kind or not name:
            continue
        out.setdefault(kind, [])
        if name not in out[kind]:
            out[kind].append(name)
    return out


def build(cache: dict[str, dict], name: str | None = None) -> dict:
    """캐시된 응답 → building.json 초안."""
    title = _title(cache["title"])
    dong = str(title.get("dongNm") or "").strip() or None
    net_gfa, total_gfa, dropped = _gfa(cache["floor"], dong)
    parking_total, parking_parts = _parking(title)
    septic_m3, septic_persons, septic_mode, septic_code, septic_raw = _septic(
        cache["wclf"]
    )

    grnd = _num(title.get("grndFlrCnt"), int)
    ugrnd = _num(title.get("ugrndFlrCnt"), int)
    apr = str(title.get("useAprDay") or "")
    seismic_raw = str(title.get("rserthqkDsgnApplyYn") or "").strip()

    return {
        "_about": (
            "건축물대장 API 로 채운 초안. 형상(floor_plan_*.json)은 별도이며, "
            "값이 null 인 항목은 대장에 없거나 0 이어서 비운 것이다 — "
            "임의로 채우지 말 것."
        ),
        "_provenance": {
            "source": "국토교통부 건축HUB 건축물대장정보 서비스",
            "operations": list(OPS.values()),
            "cache": "_api_cache/ 의 원본 응답을 함께 커밋한다 (오프라인 재현용)",
        },
        "name": name or str(title.get("bldNm") or title.get("platPlc") or "이름 미상"),
        "use": str(title.get("mainPurpsCdNm") or ""),
        "floors_total": grnd,
        "floors_residential": None,
        "seismic": True if seismic_raw.startswith("적용") else None,
        "fire_resistant": None,
        "floor_height_mm": None,
        "approval_year": int(apr[:4]) if len(apr) >= 4 and apr[:4].isdigit() else None,
        "gfa_m2": net_gfa,
        "parking_existing": parking_total,
        "septic_capacity_m3": septic_m3,
        "septic_capacity_persons": septic_persons,
        "septic_mode_raw": septic_mode,
        "septic_mode_code": septic_code,
        "violation": None,
        "zoning": _zoning(cache.get("jijigu")),
        "exclusion_answers": {},
        "source_note": "건축물대장 API (자동 수집)",
        "_detail": {
            "지하층수": ugrnd,
            "연면적_전체": total_gfa,
            "연면적_부설주차장_제외": net_gfa,
            "_gfa_note": (
                "gfa_m2 는 부설주차장을 뺀 값이다. 정화조 인원산정식의 A 가 "
                "'당해 용도로 사용되는 바닥면적(부설주차장 제외)' 이기 때문이다 "
                "(기후에너지환경부고시 제2025-165호 별표 각주 2)."
            ),
            "제외한_층": dropped,
            "주차_내역": parking_parts,
            "_parking_note": (
                "parking_existing 은 4종 합계다. LH 가 기계식을 달리 볼 수 있어 "
                "내역을 남긴다."
            ),
            "오수정화시설_원본": septic_raw,
            "승용승강기": title.get("rideUseElvtCnt"),
            "내진설계": seismic_raw,
            "내진능력": title.get("rserthqkAblty"),
            "사용승인일": apr,
            "구조": title.get("strctCdNm"),
            "용도상세": title.get("etcPurps"),
            "_violation_note": (
                "**위반건축물 표시는 이 API 로 수집할 수 없다** (2026-08-11 확인). "
                "표제부·기본개요·지역지구구역 어느 응답에도 해당 항목이 없다. "
                "세움터에서 대장을 열람하면 표지에 찍혀 있지만 개방 항목이 아니다. "
                "따라서 violation 은 null 이고 매입제외 판정에서 '미확인' 으로 남는다 — "
                "건축물대장 등본을 떼서 직접 확인해야 한다."
            ),
            "_zoning_note": (
                "용도지역은 수집만 하고 판정하지 않는다. 이 칸에는 국토계획법 용도지역 "
                "외에 수도권정비계획법 권역·건축법 지정까지 섞여 오고, 주택 허용 여부는 "
                "국토계획법 시행령 별표에서 조례로 위임된 부분이 많아 전국 공통 표를 "
                "만들 수 없다. 사람이 판단할 재료로 보여주기만 한다."
            ),
            "_missing_note": (
                "fire_resistant / floor_height_mm / floors_residential 은 대장에 "
                "없다. 도면이나 현장에서 확인해 직접 채울 것."
            ),
        },
    }


# ---------------------------------------------------------------- CLI


def _from_env_file(name: str, path: Path = Path(".env")) -> str | None:
    """`.env` 에서 키를 읽는다 (gitignore 됨).

    `setx` 로 넣은 환경변수는 **이미 떠 있는 프로세스에 상속되지 않아** 셸이나
    에디터를 재시작해야 보인다. 파일을 읽으면 그 함정이 없다.
    """
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == name:
            return v.strip().strip('"').strip("'") or None
    return None


def _key(explicit: str | None) -> str:
    key = explicit or os.environ.get(KEY_ENV) or _from_env_file(KEY_ENV)
    if not key:
        raise AdapterError(
            f"API 키가 없다. 셋 중 하나로 줄 것 — ①--key ②환경변수 {KEY_ENV} "
            f"③저장소 루트의 .env 파일에 `{KEY_ENV}=...` (gitignore 됨).\n"
            f"발급: https://www.data.go.kr 회원가입 → "
            f"'국토교통부_건축HUB_건축물대장정보 서비스' 활용신청 → "
            f"일반 인증키(Decoding)."
        )
    return key


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m engine.adapters.bdrg",
        description="건축물대장 API 로 building.json 초안을 만든다.",
        epilog=(
            "시군구·법정동 코드는 '행정안전부 법정동코드' 에서 확인한다 "
            "(https://www.code.go.kr). 예: 서울 강남구 역삼동 = 11680 / 10100."
        ),
    )
    p.add_argument("--out", required=True, help="대상 폴더 (data/buildings/<id>)")
    p.add_argument("--sigungu", help="시군구코드 5자리")
    p.add_argument("--bjdong", help="법정동코드 5자리")
    p.add_argument("--bun", help="본번")
    p.add_argument("--ji", default="0", help="부번 (기본 0)")
    p.add_argument("--plat-gb", default="0", help="대지구분 0=대지 1=산 2=블록")
    p.add_argument("--name", help="building.json 의 name")
    p.add_argument("--key", help=f"인증키 (없으면 환경변수 {KEY_ENV})")
    p.add_argument("--fetch", action="store_true", help="API 를 호출해 캐시를 갱신한다")
    p.add_argument("--dry-run", action="store_true", help="호출할 URL 만 출력한다")
    a = p.parse_args(argv)

    out = Path(a.out)
    cache_dir = out / "_api_cache"

    params = {
        "sigunguCd": a.sigungu or "",
        "bjdongCd": a.bjdong or "",
        "platGbCd": a.plat_gb,
        "bun": (a.bun or "").zfill(4),
        "ji": (a.ji or "0").zfill(4),
    }

    if a.dry_run:
        for op in OPS:
            print(_url(op, "<KEY>", params))
        return 0

    try:
        if a.fetch:
            missing = [k for k in ("sigunguCd", "bjdongCd", "bun") if not params[k].strip("0")]
            if missing:
                raise AdapterError(f"--fetch 에는 {', '.join(missing)} 가 필요하다.")
            cache = fetch_all(_key(a.key), params, cache_dir)
            print(f"캐시 저장: {cache_dir}")
        else:
            cache = load_cache(cache_dir)
            print(f"캐시 사용: {cache_dir} (갱신하려면 --fetch)")

        draft = build(cache, a.name)
    except AdapterError as e:
        print(f"실패: {e}", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    target = out / "building.json"
    target.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"작성: {target}")

    blank = [k for k, v in draft.items() if v is None and not k.startswith("_")]
    if blank:
        print(f"미확보 항목 {len(blank)}개 — {', '.join(blank)}")
        print("대장에 없는 값이다. 지어내지 말고 도면·현장에서 확인해 채울 것.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
