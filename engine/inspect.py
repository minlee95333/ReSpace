"""입력 도면이 제대로 읽혔는지 눈으로 확인하는 도구.

도면 재구성 담당자가 floor_plan.json 을 고칠 때마다 돌려, 좌표가 격자에 맞는지·
코어와 샤프트가 의도한 자리에 있는지·복도가 어떻게 잡히는지 즉시 본다.

    python -m engine.inspect data/buildings/esquisse-gasan
"""

from __future__ import annotations

import argparse
import sys

from .contracts import ContractError, load_inputs
from .corridor import generate
from .grid import CellState, gridify

GLYPH = {
    CellState.OUTSIDE: " ",
    CellState.FREE: ".",
    CellState.COLUMN: "o",
    CellState.SHAFT: "S",
    CellState.CORE: "#",
    CellState.CORRIDOR: "=",
}

LEGEND = "  . 사용가능   # 코어   S 샤프트   o 기둥   = 복도   (공백) 외부"


def render(grid) -> str:
    """위쪽이 +y 가 되도록 행을 뒤집어 출력한다."""
    return "\n".join(
        "".join(GLYPH[grid.cells[r][c]] for c in range(grid.cols))
        for r in range(grid.rows - 1, -1, -1)
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re:Space 입력 검사")
    p.add_argument("building_dir", help="building.json 과 floor_plan_*.json 이 있는 폴더")
    p.add_argument("--data", default="data", help="rules.json/units.json 위치")
    p.add_argument("--no-art", action="store_true", help="격자 그림 생략")
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
    if inp.rules.septic_persons_per_unit is None:
        print("미확정  rules.json: septic 파라미터 — 정화조 축 계산 불가")

    for fp in inp.floors:
        grid = gridify(fp, inp.rules)
        res = generate(fp, grid, inp.rules, inp.units)
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
        if not args.no_art:
            print()
            print(render(grid))
            print(LEGEND)

    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
