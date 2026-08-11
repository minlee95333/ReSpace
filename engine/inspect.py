"""입력 도면이 제대로 읽혔는지 눈으로 확인하는 도구.

도면 재구성 담당자가 floor_plan.json 을 고칠 때마다 돌려, 좌표가 격자에 맞는지·
코어와 샤프트가 의도한 자리에 있는지·복도가 어떻게 잡히는지 즉시 본다.

    python -m engine.inspect data/buildings/esquisse-gasan
"""

from __future__ import annotations

import argparse
import sys

from .common import summarize
from .contracts import ContractError, load_inputs
from .grid import CellState
from .pipeline import analyze_floor

GLYPH = {
    CellState.OUTSIDE: " ",
    CellState.FREE: ".",
    CellState.COLUMN: "o",
    CellState.SHAFT: "S",
    CellState.CORE: "#",
    CellState.CORRIDOR: "=",
}

LEGEND = (
    "  . 사용가능   # 코어   S 샤프트   o 기둥   = 복도   (공백) 외부\n"
    "  y 청년형 18.0㎡   n 신혼형 28.8㎡   x 피난 한계 초과   "
    "w 창 미접 탈락   d 채광 부족 탈락"
)

_REJECT_GLYPH = {"no_window": "w", "daylight_short": "d"}


def render(grid, egress=None, placement=None, daylight=None) -> str:
    """위쪽이 +y 가 되도록 행을 뒤집어 출력한다."""
    art = [[GLYPH[grid.cells[r][c]] for c in range(grid.cols)] for r in range(grid.rows)]

    def fill(cells, ch):
        r0, c0, rows, cols = cells
        for r in range(r0, r0 + rows):
            for c in range(c0, c0 + cols):
                art[r][c] = ch

    if egress is not None:
        for r in range(grid.rows):
            for c in range(grid.cols):
                if grid.cells[r][c] == CellState.FREE and not egress.ok(r, c):
                    art[r][c] = "x"

    if placement is not None:
        for u in placement.units:
            fill(u.cells, u.type_id[0])

    # 채광 탈락은 배치 위에 덮어써 어디가 왜 빠졌는지 보이게 한다.
    if daylight is not None:
        for u in daylight.rejected:
            fill(u.cells, _REJECT_GLYPH.get(u.reason, "?"))

    return "\n".join("".join(art[r]) for r in range(grid.rows - 1, -1, -1))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re:Space 입력 검사")
    p.add_argument("building_dir", help="building.json 과 floor_plan_*.json 이 있는 폴더")
    p.add_argument("--data", default="data", help="rules.json/units.json 위치")
    p.add_argument("--no-art", action="store_true", help="격자 그림 생략")
    p.add_argument("--strategy", default="balanced",
                   help="그림에 표시할 전략 (supply/balanced/minimal)")
    args = p.parse_args(argv)

    try:
        inp = load_inputs(args.building_dir, args.data)
    except ContractError as e:
        print(f"[실패] {e}")
        return 1

    b = inp.building
    print(f"건물   {b.name}  ({b.use}, 지상 {b.floors_total}층)")
    print(f"규칙   rules {inp.rules.version} · 격자 {inp.rules.grid_mm}mm · "
          f"복도 {inp.rules.corridor_width_mm}mm")
    print(f"유닛   " + " / ".join(
        f"{u.label} {u.area_m2}㎡ ({u.cells(inp.rules.grid_mm)[0]}×"
        f"{u.cells(inp.rules.grid_mm)[1]}셀)" for u in inp.units.types))

    missing = [f for f in ("approval_year", "gfa_m2", "floors_residential",
                           "parking_existing", "septic_capacity_m3")
               if getattr(b, f) is None]
    if missing:
        print(f"미확정  building.json: {', '.join(missing)}")
    if b.septic_capacity_m3 is None and (b.gfa_m2 is None or not b.use):
        print("미확정  정화조 — 용량(septic_capacity_m3) 도, "
              "종전 용도 추정용 use/gfa_m2 도 없어 축 계산 불가")
    print(f"주차   기준 모드 '{inp.rules.parking_mode}'")

    # 층 확장(floors_residential)은 하지 않는다. 이 도구는 입력 도면을 보는 용도다.
    for fp in inp.floors:
        runs = {
            sid: analyze_floor(inp, fp.floor, sid) for sid in inp.units.strategies
        }
        ref = runs[args.strategy]
        grid, res, em = ref.grid, ref.corridor, ref.egress
        x0, y0, x1, y1 = fp.bbox_mm
        print()
        print(f"── {fp.floor}층  {x1 - x0}×{y1 - y0}mm  "
              f"{grid.cols}×{grid.rows}셀 ──")
        counts = {s: grid.count(s) for s in CellState}
        print("  셀     " + "  ".join(
            f"{s.name} {counts[s]}" for s in CellState if counts[s]))
        print(f"  창     {len(fp.windows)}구간  "
              f"총 {sum(w.length_mm for w in fp.windows)}mm")
        print(f"  코어   " + ", ".join(f"{c.type}" for c in fp.cores)
              + f"  (계단 {len(fp.stair_cores())}개소)")
        need = res.need_cells
        print(f"  복도   {res.type}  축 {res.axis}  밴드 {res.band}")
        print(f"         깊이 저 {res.depth_low_cells}셀 / 고 {res.depth_high_cells}셀"
              f"  (필요 {need}셀)")
        print(f"         커버리지 저 {res.coverage_low:.0%} / 고 {res.coverage_high:.0%}"
              f"  (기준 {inp.rules.corridor_side_usable_coverage:.0%})")
        if res.type == "none":
            print("  경고   양쪽 모두 유닛 깊이 미달 — 이 층은 세대 0 이 된다.")
        if not fp.stair_cores():
            print("  경고   stair 코어가 없다 — 피난 판정(④) 을 돌릴 수 없다.")

        mode = "모든 계단 충족" if em.all_cores else "가장 가까운 계단"
        print(f"  피난   한계 {em.limit_m}m · {mode} · 계단 {em.stair_count}개소")
        print(f"         도달 {em.reachable_cells}셀 중 한계 초과 {em.over_limit_cells}셀")

        print("  대안   배치 → 채광통과 | 유형 구성 | 설비 재사용")
        for sid, fa in runs.items():
            mix = ", ".join(f"{inp.units.by_id(k).label} {v}"
                            for k, v in sorted(fa.placement.count_by_type().items()))
            print(f"         {inp.units.strategies[sid].label:8s} "
                  f"{fa.placement.count:3d} → {fa.daylight.kept:3d}세대  "
                  f"{mix or '없음':24s} 재사용 {fa.placement.shaft_reuse_ratio:.0%}")

        if ref.daylight.rejected:
            counts: dict[str, int] = {}
            for r in ref.daylight.rejected:
                counts[r.reason] = counts.get(r.reason, 0) + 1
            print(f"  채광   탈락 {len(ref.daylight.rejected)}세대 — "
                  + ", ".join(f"{k} {v}" for k, v in counts.items()))
            print(f"         예: {ref.daylight.rejected[0].detail}")

        s = summarize(ref.commons)
        if s:
            print("  공용   " + ", ".join(f"{k} {v}㎡" for k, v in s.items()))

        if not args.no_art:
            print()
            print(f"  [{inp.units.strategies[args.strategy].label}]")
            print(render(grid, em, ref.placement, ref.daylight))
            print(LEGEND)

    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
