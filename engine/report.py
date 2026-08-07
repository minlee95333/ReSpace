"""파이프라인 실행 CLI. result.json 과 층별 SVG 를 낸다.

    python -m engine.report data/buildings/esquisse-gasan --out out/esquisse
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .caps import AXIS_LABEL
from .contracts import ContractError, load_inputs
from .emit import write
from .pipeline import analyze


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Re:Space 분석 실행")
    p.add_argument("building_dir")
    p.add_argument("--data", default="data")
    p.add_argument("--strategy", default="balanced")
    p.add_argument("--out", default=None, help="기본값: out/<폴더명>/<전략>")
    p.add_argument("--all-strategies", action="store_true",
                   help="3안을 모두 실행한다")
    args = p.parse_args(argv)

    try:
        inp = load_inputs(args.building_dir, args.data)
    except ContractError as e:
        print(f"[실패] {e}")
        return 1

    stamp = datetime.now().isoformat(timespec="seconds")
    strategies = list(inp.units.strategies) if args.all_strategies else [args.strategy]

    for sid in strategies:
        try:
            a = analyze(inp, sid)
        except ContractError as e:
            print(f"[실패] {sid}: {e}")
            return 1

        base = args.out or f"out/{args.building_dir.rstrip('/').split('/')[-1]}"
        out_dir = f"{base}/{sid}" if (args.all_strategies or not args.out) else base
        files = write(a, out_dir, stamp)

        label = inp.units.strategies[sid].label
        print(f"[{label}] {a.grade} · 공급 {a.caps.supply}세대 "
              f"· 병목 {AXIS_LABEL[a.caps.bottleneck]}")
        for ax in a.caps.axes:
            mark = " " if ax.available else "!"
            print(f"  {mark} {ax.label:5s} {str(ax.value) if ax.available else '미확보':>6s}  {ax.basis}")
        if not a.caps.complete:
            print(f"  ! {a.caps.note}")
        q = a.quantities
        print(f"    신설벽 {q['new_wall_m']}m · 설비재사용 {q['shaft_reuse_ratio']:.0%}"
              f" · 공용 {q['common_area_m2']}㎡")
        print(f"    → {files[0]} 외 {len(files) - 1}개")

    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
