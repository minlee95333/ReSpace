"""파이프라인 실행 CLI.

    python -m engine.report data/buildings/esquisse-gasan
    python -m engine.report data/buildings/* --dashboard out/dashboard.html
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .caps import AXIS_LABEL
from .contracts import ContractError, load_inputs
from .dashboard import build_payload, _building_payload
from .dashboard import write as write_dashboard
from .emit import write as write_result
from .pipeline import analyze, recommend


def _print_one(sid: str, a, label: str) -> None:
    print(f"[{label}] {a.grade} · 공급 {a.caps.supply}세대 "
          f"· 병목 {AXIS_LABEL[a.caps.bottleneck]}")
    for ax in a.caps.axes:
        mark = " " if ax.available else "!"
        val = str(ax.value) if ax.available else "미확보"
        print(f"  {mark} {ax.label:5s} {val:>6s}  {ax.basis}")
    q = a.quantities
    print(f"    신설벽 {q['new_wall_m']}m · 설비재사용 "
          f"{q['shaft_reuse_ratio']:.0%} · 공용 {q['common_area_m2']}㎡")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re:Space 분석 실행")
    p.add_argument("building_dirs", nargs="+")
    p.add_argument("--data", default="data")
    p.add_argument("--strategy", default=None,
                   help="지정하면 그 전략만. 기본은 3안 전부")
    p.add_argument("--out", default="out", help="산출물 루트 (기본 out)")
    p.add_argument("--dashboard", default=None,
                   help="자립형 HTML 경로. 기본 <out>/dashboard.html")
    p.add_argument("--no-dashboard", action="store_true")
    args = p.parse_args(argv)

    stamp = datetime.now().isoformat(timespec="seconds")
    buildings: list[dict] = []
    rules_version = grid_mm = None

    for bdir in args.building_dirs:
        try:
            inp = load_inputs(bdir, args.data)
        except ContractError as e:
            print(f"[실패] {bdir}: {e}")
            return 1

        rules_version, grid_mm = inp.rules.version, inp.rules.grid_mm
        sids = [args.strategy] if args.strategy else list(inp.units.strategies)
        name = Path(bdir).name
        print(f"\n=== {inp.building.name} ({bdir}) ===")

        analyses = {}
        for sid in sids:
            try:
                a = analyze(inp, sid)
            except ContractError as e:
                print(f"[실패] {sid}: {e}")
                return 1
            analyses[sid] = a
            label = inp.units.strategies[sid].label
            _print_one(sid, a, label)
            files = write_result(a, f"{args.out}/{name}/{sid}", stamp)
            print(f"    → {files[0]} 외 {len(files) - 1}개")

        best, reasons = recommend(analyses)
        print(f"  추천: {reasons[0]}")
        buildings.append(_building_payload(analyses, best, reasons))

    if not args.no_dashboard:
        payload = build_payload(buildings, rules_version, grid_mm, stamp)
        path = write_dashboard(
            payload, args.dashboard or f"{args.out}/dashboard.html"
        )
        size = path.stat().st_size / 1024
        print(f"\n대시보드 → {path}  ({size:.0f} KB, 더블클릭으로 열림)")

    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
