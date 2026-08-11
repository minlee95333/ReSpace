"""DXF 도면 → floor_plan_NN.json (형상).

**사람이 레이어를 지정하는 단계가 없다.** 레이어명은 사무소마다 다르지만
(`A-WALL`/`벽`/`0`/`WALL-1`), 한국 도면에는 실명(室名) 텍스트가 거의 항상 들어간다.
그래서 신호 순위를 이렇게 둔다.

1. **실명 텍스트** (TEXT/MTEXT) — 닫힌 영역 안에 있는 문자열이 그 영역의 역할을 정한다
2. **기하 특성** — 최대 닫힌 폴리라인 = 외곽, 작은 반복 사각형 = 기둥
3. **레이어명** — 보조. KS F 1542 패턴을 사전에 넣어 두었으나 전제하지 않는다

용어 사전은 `data/dxf_lexicon.json` 에 있고 **프로젝트에 한 번** 둔다.

**못 읽으면 추측하지 않는다.** 계단실을 못 찾으면 피난 거리가 통째로 틀리므로
실패시킨다. 배율이 애매해도 실패시킨다 — 배율을 틀리면 모든 수치가 조용히 틀어진다.
읽어낸 결과는 `status: "reconstructed"` 이며, 가정한 값은 `_assumptions` 에 남는다.

격자 스냅은 **전부 보수적 방향**이다. 외곽은 안쪽으로 줄이고(면적 과대 방지),
코어·샤프트·기둥은 바깥으로 키우며(장애물 과소 방지), 창은 짧게 자른다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import ContractError, load_json

Point = tuple[float, float]


class DxfError(RuntimeError):
    """판독 실패. 무엇을 못 읽었는지 메시지에 담는다."""


# ---------------------------------------------------------------- 원시 파싱


@dataclass
class Entity:
    kind: str
    layer: str = ""
    pairs: list[tuple[int, str]] = field(default_factory=list)

    def all_of(self, code: int) -> list[str]:
        return [v for c, v in self.pairs if c == code]

    def first(self, code: int, default=None):
        for c, v in self.pairs:
            if c == code:
                return v
        return default

    def floats(self, code: int) -> list[float]:
        out = []
        for v in self.all_of(code):
            try:
                out.append(float(v))
            except ValueError:
                pass
        return out

    @property
    def points(self) -> list[Point]:
        xs, ys = self.floats(10), self.floats(20)
        pts = list(zip(xs, ys))[: min(len(xs), len(ys))]
        # LINE 은 끝점이 11/21 에 따로 온다. 이걸 빼면 선분이 점 하나로 보인다.
        if self.kind == "LINE":
            ex, ey = self.floats(11), self.floats(21)
            if ex and ey:
                pts = pts + [(ex[0], ey[0])]
        return pts

    @property
    def closed(self) -> bool:
        flag = self.first(70)
        try:
            return bool(int(flag) & 1)
        except (TypeError, ValueError):
            return False

    @property
    def text(self) -> str:
        # MTEXT 는 긴 문자열을 3 으로 나눠 보내고 마지막 조각이 1 이다.
        return ("".join(self.all_of(3)) + (self.first(1) or "")).strip()


@dataclass
class Drawing:
    header: dict[str, str]
    entities: list[Entity]


def read_text(path: Path) -> str:
    """DXF 는 UTF-8 이거나 cp949 다. 판별에 실패하면 그대로 알린다."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DxfError(
        f"{path}: 인코딩을 판별할 수 없다 (utf-8 / cp949 아님). "
        f"바이너리 DWG 를 확장자만 바꾼 것은 아닌지 확인할 것 — "
        f"CAD 에서 'DXF 저장'으로 다시 내보내야 한다."
    )


def parse(text: str) -> Drawing:
    """태그드 ASCII DXF 를 (코드, 값) 쌍으로 읽는다."""
    lines = text.splitlines()
    if not any(line.strip() == "SECTION" for line in lines[:200]):
        raise DxfError(
            "DXF 로 보이지 않는다 (SECTION 이 없다). "
            "바이너리 DXF 나 DWG 는 지원하지 않는다 — ASCII DXF 로 내보낼 것."
        )

    pairs: list[tuple[int, str]] = []
    for i in range(0, len(lines) - 1, 2):
        code_raw = lines[i].strip()
        try:
            pairs.append((int(code_raw), lines[i + 1].strip()))
        except ValueError:
            # 홀수 줄이 어긋나면 뒤가 전부 틀어진다. 조용히 넘기지 않는다.
            raise DxfError(
                f"{i + 1}번째 줄 '{code_raw}' 가 그룹 코드가 아니다. "
                f"파일이 잘렸거나 편집 중 손상됐을 수 있다."
            ) from None

    header: dict[str, str] = {}
    entities: list[Entity] = []
    section = None
    var = None
    cur: Entity | None = None

    for code, value in pairs:
        if code == 0 and value == "SECTION":
            section = "?"
            cur = None
            continue
        if code == 0 and value == "ENDSEC":
            section = None
            cur = None
            continue
        if section == "?" and code == 2:
            section = value
            continue

        if section == "HEADER":
            if code == 9:
                var = value
            elif var is not None:
                header.setdefault(var, value)
            continue

        if section == "ENTITIES":
            if code == 0:
                cur = Entity(kind=value)
                entities.append(cur)
            elif cur is not None:
                if code == 8:
                    cur.layer = value
                cur.pairs.append((code, value))

    return Drawing(header, entities)


# ---------------------------------------------------------------- 기하


def area_of(poly: list[Point]) -> float:
    """신발끈 공식. 방향과 무관하게 양수."""
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def bbox_of(poly: list[Point]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def centroid_of(poly: list[Point]) -> Point:
    return (
        sum(p[0] for p in poly) / len(poly),
        sum(p[1] for p in poly) / len(poly),
    )


def contains(poly: list[Point], pt: Point) -> bool:
    """레이 캐스팅. 경계 위의 점은 안쪽으로 본다."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi >= x:
                inside = not inside
    return inside


# ---------------------------------------------------------------- 격자 스냅


def snap_poly_inward(poly: list[Point], grid: int) -> list[tuple[int, int]]:
    """외곽선을 격자에 맞추되 **안쪽으로만** 움직인다.

    각 꼭짓점을 도형 중심 방향의 격자점으로 보낸다. 면적이 늘어나지 않으므로
    없는 바닥을 만들어내지 않는다.
    """
    cx, cy = centroid_of(poly)
    out: list[tuple[int, int]] = []
    for x, y in poly:
        sx = math.ceil(x / grid) * grid if x < cx else math.floor(x / grid) * grid
        sy = math.ceil(y / grid) * grid if y < cy else math.floor(y / grid) * grid
        pt = (int(sx), int(sy))
        if not out or out[-1] != pt:
            out.append(pt)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def snap_rect_outward(b: tuple[float, float, float, float], grid: int) -> list[int]:
    """장애물(코어·샤프트·기둥)을 격자에 맞추되 **바깥으로만** 키운다.

    작게 잡으면 없는 여유가 생겨 세대가 과대 산출된다. 크게 잡는 쪽이 안전하다.
    """
    x0, y0, x1, y1 = b
    gx0 = math.floor(x0 / grid) * grid
    gy0 = math.floor(y0 / grid) * grid
    gx1 = math.ceil(x1 / grid) * grid
    gy1 = math.ceil(y1 / grid) * grid
    return [int(gx0), int(gy0), int(gx1 - gx0), int(gy1 - gy0)]


def snap_segment_inward(a: Point, b: Point, grid: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """창 구간을 격자에 맞추되 **짧게** 자른다. 길게 잡으면 채광이 후해진다."""
    (x1, y1), (x2, y2) = a, b
    if abs(x1 - x2) >= abs(y1 - y2):  # 수평
        y = round((y1 + y2) / 2 / grid) * grid
        lo, hi = sorted((x1, x2))
        return (int(math.ceil(lo / grid) * grid), int(y)), (
            int(math.floor(hi / grid) * grid), int(y))
    x = round((x1 + x2) / 2 / grid) * grid
    lo, hi = sorted((y1, y2))
    return (int(x), int(math.ceil(lo / grid) * grid)), (
        int(x), int(math.floor(hi / grid) * grid))


# ---------------------------------------------------------------- 사전 적용


def _norm(s: str) -> str:
    return s.replace(" ", "").replace("\t", "").upper()


def role_of_text(lex: dict, text: str) -> tuple[str, str] | None:
    """실명 텍스트 → (역할, 세부). 사전 선언 순서대로 먼저 걸리는 것이 이긴다."""
    t = _norm(text)
    if not t:
        return None
    for key, spec in lex["room_terms"].items():
        for kw in spec["match"]:
            if _norm(kw) in t:
                return spec["role"], spec.get("core_type", key)
    return None


def layer_matches(patterns: list[str], layer: str) -> bool:
    lay = _norm(layer)
    for p in patterns:
        pat = _norm(p)
        if pat.endswith("*"):
            if lay.startswith(pat[:-1]):
                return True
        elif pat in lay:
            return True
    return False


def scale_to_mm(lex: dict, drawing: Drawing, extent: float) -> tuple[float, str]:
    """도면 단위 → mm 배율과 그 근거."""
    ins = drawing.header.get("$INSUNITS")
    table = lex["units"]["insunits"]
    if ins in table:
        return float(table[ins]), f"$INSUNITS={ins}"
    if ins == "0":
        pass  # 0 = 단위 없음. 추정으로 넘어간다.

    cfg = lex["units"]
    if extent >= cfg["infer_mm_min_extent"]:
        return 1.0, f"$INSUNITS 없음 — 최대 변 {extent:.0f} 이므로 mm 로 추정"
    if extent <= cfg["infer_m_max_extent"]:
        return 1000.0, f"$INSUNITS 없음 — 최대 변 {extent:.1f} 이므로 m 로 추정"
    raise DxfError(
        f"도면 단위를 정할 수 없다. $INSUNITS 가 없고 최대 변이 {extent:.1f} 로 "
        f"mm({cfg['infer_mm_min_extent']} 이상)도 m({cfg['infer_m_max_extent']} 이하)도 "
        f"아니다. 배율을 잘못 잡으면 모든 수치가 조용히 틀어지므로 추측하지 않는다. "
        f"CAD 에서 단위를 지정해 다시 내보낼 것."
    )


# ---------------------------------------------------------------- 판독


@dataclass
class Region:
    poly: list[Point]
    layer: str
    area_m2: float
    labels: list[str] = field(default_factory=list)


def interpret(drawing: Drawing, lex: dict, grid: int, floor: int) -> dict:
    polys = [
        e for e in drawing.entities
        if e.kind in ("LWPOLYLINE", "POLYLINE") and e.closed and len(e.points) >= 3
    ]
    if not polys:
        raise DxfError(
            "닫힌 폴리라인이 하나도 없다. 외곽선이 선(LINE) 으로만 그려져 있으면 "
            "외곽을 잡을 수 없다. 평면도 시트만 따로 내보냈는지 확인할 것."
        )

    raw_boundary = max(polys, key=lambda e: area_of(e.points))
    bx0, by0, bx1, by1 = bbox_of(raw_boundary.points)
    extent = max(bx1 - bx0, by1 - by0)
    scale, scale_basis = scale_to_mm(lex, drawing, extent)

    def mm(pts: list[Point]) -> list[Point]:
        return [(x * scale, y * scale) for x, y in pts]

    boundary = mm(raw_boundary.points)
    b_area = area_of(boundary) / 1_000_000
    geo = lex["geometry"]
    if b_area < geo["boundary_min_area_m2"]:
        raise DxfError(
            f"가장 큰 닫힌 도형의 면적이 {b_area:.1f}㎡ 로 "
            f"{geo['boundary_min_area_m2']}㎡ 에 못 미친다. 평면도가 아니라 "
            f"상세도·범례일 가능성이 크다."
        )

    # 텍스트를 모아 각 영역에 배정한다.
    texts = [
        (mm([e.points[0]])[0], e.text)
        for e in drawing.entities
        if e.kind in ("TEXT", "MTEXT") and e.points and e.text
    ]

    regions: list[Region] = []
    for e in polys:
        if e is raw_boundary:
            continue
        poly = mm(e.points)
        reg = Region(poly, e.layer, area_of(poly) / 1_000_000)
        for pt, t in texts:
            if contains(poly, pt):
                reg.labels.append(t)
        regions.append(reg)

    cores: list[dict] = []
    shafts: list[dict] = []
    noted: list[dict] = []
    used: set[int] = set()

    for i, reg in enumerate(regions):
        hit = None
        for t in reg.labels:
            hit = role_of_text(lex, t)
            if hit:
                break
        if not hit:
            continue
        role, detail = hit
        used.add(i)
        rect = snap_rect_outward(bbox_of(reg.poly), grid)
        if role == "core":
            if not (geo["core_min_area_m2"] <= reg.area_m2 <= geo["core_max_area_m2"]):
                raise DxfError(
                    f"'{reg.labels[0]}' 로 읽은 영역의 면적이 {reg.area_m2:.1f}㎡ 로 "
                    f"코어 범위({geo['core_min_area_m2']}~{geo['core_max_area_m2']}㎡)를 "
                    f"벗어난다. 실명 텍스트가 엉뚱한 영역에 잡힌 것으로 보인다."
                )
            cores.append({"type": detail, "rect": rect})
        elif role == "shaft":
            if reg.area_m2 <= geo["shaft_max_area_m2"]:
                shafts.append({"rect": rect})
        else:
            noted.append({"role": role, "label": reg.labels[0], "area_m2": round(reg.area_m2, 2)})

    if not any(c["type"] == "stair" for c in cores):
        seen = sorted({t for _, t in texts})[:20]
        raise DxfError(
            "계단실을 찾지 못했다. 피난 기점이 없으면 보행거리가 통째로 틀리므로 "
            "추측하지 않고 중단한다.\n"
            f"도면에서 읽은 실명 텍스트: {seen or '(없음)'}\n"
            "이 중 계단실에 해당하는 표기가 있으면 data/dxf_lexicon.json 의 "
            "room_terms.stair.match 에 추가할 것 — 도면마다가 아니라 한 번만 하면 된다."
        )

    # 기둥: 실명이 붙지 않은 작은 닫힌 사각형.
    columns = []
    for i, reg in enumerate(regions):
        if i in used:
            continue
        x0, y0, x1, y1 = bbox_of(reg.poly)
        w, h = x1 - x0, y1 - y0
        if not (geo["column_min_mm"] <= w <= geo["column_max_mm"]):
            continue
        if not (geo["column_min_mm"] <= h <= geo["column_max_mm"]):
            continue
        rect = snap_rect_outward((x0, y0, x1, y1), grid)
        columns.append({
            "center": [rect[0] + rect[2] // 2, rect[1] + rect[3] // 2],
            "size": [rect[2], rect[3]],
        })

    # 창: 창호 레이어의 선분 중 충분히 긴 것.
    windows = []
    wa = lex["window_assumption"]
    for e in drawing.entities:
        if not layer_matches(lex["layer_hints"]["window"], e.layer):
            continue
        pts = mm(e.points)
        if len(pts) < 2:
            continue
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) < geo["window_min_mm"]:
                continue
            s, t = snap_segment_inward(a, b, grid)
            if s == t:
                continue
            windows.append({
                "start": list(s), "end": list(t),
                "sill": wa["sill_mm"], "height": wa["height_mm"],
            })

    warnings = []
    if not windows:
        warnings.append(
            "창을 하나도 찾지 못했다. 채광 판정에서 모든 세대가 '외벽 창 미접'으로 "
            "탈락해 결과가 0세대가 된다. 창호 레이어 표기를 dxf_lexicon.json 의 "
            "layer_hints.window 에 추가하거나, 창 정보를 직접 채울 것."
        )
    if not shafts:
        warnings.append("샤프트를 찾지 못했다 — 설비 재사용률이 0 으로 나온다.")
    if not columns:
        warnings.append("기둥을 찾지 못했다 — 구조체 간섭이 반영되지 않는다.")

    return {
        "_about": (
            "DXF 자동 판독 결과. 사람이 레이어를 지정하지 않았다. "
            "실명 텍스트 → 기하 → 레이어명 순으로 역할을 정했다."
        ),
        "floor": floor,
        "unit": "mm",
        "status": "reconstructed",
        "boundary": [list(p) for p in snap_poly_inward(boundary, grid)],
        "cores": cores,
        "shafts": shafts,
        "columns": columns,
        "windows": windows,
        "_assumptions": {
            "단위배율": scale_basis,
            "창_입면치수": (
                f"sill {wa['sill_mm']}mm / height {wa['height_mm']}mm — "
                f"평면도에 없어 가정한 값이다 (측정값 아님). {wa['note']}"
            ),
            "격자스냅": (
                f"{grid}mm. 외곽은 안쪽으로, 코어·샤프트·기둥은 바깥으로, "
                f"창은 짧게 — 전부 세대수가 늘지 않는 방향."
            ),
        },
        "_detected": {
            "닫힌영역": len(regions),
            "실명텍스트": len(texts),
            "코어": len(cores),
            "샤프트": len(shafts),
            "기둥": len(columns),
            "창": len(windows),
            "기타실": noted,
        },
        "_warnings": warnings,
    }


# ---------------------------------------------------------------- CLI


def convert(path: Path, floor: int, grid: int, lexicon: Path) -> dict:
    lex = load_json(lexicon)
    return interpret(parse(read_text(path)), lex, grid, floor)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m engine.adapters.dxf",
        description="DXF 평면도를 floor_plan_NN.json 으로 판독한다 (사람 개입 없음).",
    )
    p.add_argument("dxf", help="입력 DXF 파일")
    p.add_argument("--floor", type=int, required=True, help="층 번호")
    p.add_argument("--out", help="대상 폴더 (없으면 표준출력)")
    p.add_argument("--grid", type=int, default=600, help="격자 mm (기본 600)")
    p.add_argument("--lexicon", default="data/dxf_lexicon.json")
    a = p.parse_args(argv)

    try:
        plan = convert(Path(a.dxf), a.floor, a.grid, Path(a.lexicon))
    except (DxfError, ContractError) as e:
        print(f"판독 실패: {e}", file=sys.stderr)
        return 1

    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if not a.out:
        print(text)
        return 0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"floor_plan_{a.floor:02d}.json"
    target.write_text(text, encoding="utf-8")
    print(f"작성: {target}")
    for k, v in plan["_detected"].items():
        print(f"  {k}: {v}")
    for w in plan["_warnings"]:
        print(f"  경고: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
