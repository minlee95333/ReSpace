# -*- coding: utf-8 -*-
"""격자 조건별 추론 (CLAUDE.md §4.2 ~ §4.4).

조건 하나 = (ρ, θ, o) 한 점. 각 조건에서 실험셋 전체를 돌려 아래를 잰다.

  recall_hat · recall_nohat(주 지표) · conf_mean · conf_std · n_gt · n_tp · n_fp

IoU 0.5, confidence 0.25 고정(§4.4).

**θ 를 걸면 GT 박스도 같은 호모그래피로 옮긴다.** 이미지만 워핑하고 GT 를 그대로
두면 위치가 어긋나 recall 이 통째로 0 에 가까워진다. ρ 와 o 는 캔버스를 보존하고
박스를 움직이지 않으므로 변환이 필요 없다.

사용:
    python src/run_grid.py --smoke     9조건 (§7 Phase 1)
    python src/run_grid.py             125조건 (§7 Phase 2)
"""
from pathlib import Path
import argparse
import csv
import json
import statistics
import sys
# 콘솔 인코딩이 cp949 인 환경에서 출력을 파일로 리디렉션하면, 문자열에 cp949 로
# 표현 못 하는 문자(U+2212 마이너스, U+2014 em dash 등)가 하나만 있어도
# UnicodeEncodeError 로 죽는다. **계산을 다 끝내고 마지막 print 에서 죽는다** —
# 실제로 두 번 겪었다. 문자를 하나씩 쫓는 대신 출력단에서 막는다.
# encoding 은 그대로 두어 한글 콘솔 표시를 유지하고 errors 만 바꾼다.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import transforms as T

MANIFEST = config.DATA_FILTERED / "manifest.json"
WEIGHTS = config.DETECTOR_BEST

CLASSES = ("hat", "person")

# 125조건 × 500장이면 같은 파일을 62,500번 디코딩하게 된다. 한 번만 읽는다.
# 500장 전부 담아도 약 1.14GB 로 측정됐다.
_IMG_CACHE: dict[str, "object"] = {}


def load(rel_path: str):
    img = _IMG_CACHE.get(rel_path)
    if img is None:
        img = T.imread(Path(config.ROOT / rel_path))
        _IMG_CACHE[rel_path] = img
    return img


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def match(gt: list, det: list, ignore: list | None = None) -> tuple[int, int, list]:
    """GT 하나에 검출 하나를 그리디로 짝짓는다. 반환 (tp, fp, 매칭된 conf 목록).

    `ignore` 는 **40px 미만이라 GT 에서 빠진 머리들**이다. 여기 걸리는 검출은
    FP 로 세지 않는다. 실험셋은 기준 조건을 확보하려고 큰 머리만 GT 로 남겼는데
    (§4.1), 검출기는 작은 머리도 맞게 찾아낸다. 그것을 오검출로 세면 n_fp 가
    GT 수를 넘어가 해석이 불가능해진다.
    """
    used = set()
    tp = 0
    confs = []
    for g_cls, g_box in gt:
        best_i, best_v = -1, config.IOU_THR
        for i, (d_cls, d_box, d_conf) in enumerate(det):
            if i in used or d_cls != g_cls:
                continue
            v = iou(g_box, d_box)
            if v >= best_v:
                best_i, best_v = i, v
        if best_i >= 0:
            used.add(best_i)
            tp += 1
            confs.append(det[best_i][2])

    fp = 0
    for i, (d_cls, d_box, _) in enumerate(det):
        if i in used:
            continue
        if ignore and any(iou(d_box, ib) >= config.IOU_THR for ic, ib in ignore
                          if ic == d_cls):
            continue
        fp += 1
    return tp, fp, confs


def run_condition(model, records: list, rho: float, theta: float, occ: float,
                  min_head_px: float = config.MIN_HEAD_PX,
                  occ_divisor: int = T.DEFAULT_STRIPE_DIVISOR) -> dict:
    per_cls_gt = {c: 0 for c in CLASSES}
    per_cls_tp = {c: 0 for c in CLASSES}
    n_fp = 0
    confs: list[float] = []
    occ_actuals: list[float] = []

    names = model.names
    for rec in records:
        img = load(rec["image"])
        h, w = img.shape[:2]

        boxes = [i["bbox"] for i in rec["instances"]]
        labels = [i["cls"] for i in rec["instances"]]

        # GT 에서 빠진 작은 머리들 — FP 집계에서 제외할 대상
        small = [i for i in rec.get("all_instances", [])
                 if i["short_px"] < min_head_px and i["bbox"] not in boxes]
        s_boxes = [i["bbox"] for i in small]
        s_labels = [i["cls"] for i in small]

        out = T.apply_rho(img, rec["ref_head_px"], rho)
        if theta > 0:
            m = T.theta_matrix(w, h, theta)
            gt = [(labels[i], b) for i, b in T.warp_boxes(boxes, m, w, h)]
            ignore = [(s_labels[i], b) for i, b in T.warp_boxes(s_boxes, m, w, h)]
            out = T.apply_theta(out, theta)
        else:
            gt = list(zip(labels, boxes))
            ignore = list(zip(s_labels, s_boxes))
        out, occ_actual = T.apply_occlusion(out, occ / 100.0, divisor=occ_divisor)
        occ_actuals.append(occ_actual)

        if not gt:
            continue

        r = model.predict(out, conf=config.CONF_THR, device=0, verbose=False)[0]
        det = [(names[int(c)], b.tolist(), float(cf))
               for c, b, cf in zip(r.boxes.cls, r.boxes.xyxy, r.boxes.conf)]

        tp, fp, cf = match(gt, det, ignore)
        n_fp += fp
        confs.extend(cf)
        for g_cls, _ in gt:
            per_cls_gt[g_cls] += 1
        # 클래스별 tp 는 매칭을 클래스별로 다시 세어 얻는다
        for c in CLASSES:
            g_c = [(gc, gb) for gc, gb in gt if gc == c]
            d_c = [d for d in det if d[0] == c]
            if g_c:
                t, _, _ = match(g_c, d_c)
                per_cls_tp[c] += t

    n_gt = sum(per_cls_gt.values())
    n_tp = sum(per_cls_tp.values())
    return {
        # 어느 검출기로 잰 값인지 행마다 남긴다. 검출기를 바꿔 재실행할 때
        # 이전 결과를 그대로 재사용하면 곡선에 엉뚱한 이름이 붙는다.
        "detector": config.DETECTOR_ARCH,
        "rho_px": rho,
        "theta_deg": theta,
        "occ_pct_target": occ,
        "occ_pct_actual": round(statistics.mean(occ_actuals) * 100, 2) if occ_actuals else 0.0,
        "recall_hat": round(per_cls_tp["hat"] / per_cls_gt["hat"], 4) if per_cls_gt["hat"] else None,
        "recall_nohat": round(per_cls_tp["person"] / per_cls_gt["person"], 4) if per_cls_gt["person"] else None,
        "conf_mean": round(statistics.mean(confs), 4) if confs else None,
        "conf_std": round(statistics.pstdev(confs), 4) if len(confs) > 1 else None,
        "n_gt": n_gt,
        "n_tp": n_tp,
        "n_fp": n_fp,
        "n_gt_hat": per_cls_gt["hat"],
        "n_gt_person": per_cls_gt["person"],
    }


def main(smoke: bool, limit: int | None,
         occ_divisor: int = T.DEFAULT_STRIPE_DIVISOR,
         out_csv: Path | None = None,
         occ_only: bool = False,
         manifest_path: Path | None = None,
         rho_only: bool = False) -> Path:
    """occ_only 는 h(o) 단면(ρ=48, θ=0)만 돌린다 - 주기 민감도용이다.

    가림축이 결과를 지배하는데 스트라이프 주기는 §4.2 가 자유 파라미터로 남긴
    값이라 근거가 없다. 주기를 바꿔 단면만 다시 재면 λ 가 얼마나 흔들리는지
    싸게 확인할 수 있다. 격자 전체를 다시 돌릴 이유가 없다.
    """
    from ultralytics import YOLO

    if not WEIGHTS.exists():
        raise FileNotFoundError(
            f"파인튜닝 가중치가 없다: {WEIGHTS}\n"
            "먼저 `python src/train_detector.py` 를 돌릴 것."
        )
    manifest = json.loads((manifest_path or MANIFEST).read_text(encoding="utf-8"))
    records = manifest["images"][:limit] if limit else manifest["images"]

    if smoke:
        grid = [(r, t, o) for r in config.SMOKE_RHO_PX
                for t in config.SMOKE_THETA_DEG for o in config.SMOKE_OCC_PCT]
        out_csv = out_csv or config.OUTPUTS / "smoke_results.csv"
    elif rho_only:
        # ρ 단면(θ=0, o=0)만. 다른 데이터셋에 같은 변형을 걸어 f(ρ) 를 재는 용도다
        grid = [(r, 0.0, 0.0) for r in config.RHO_LEVELS_PX]
        out_csv = out_csv or config.OUTPUTS / "rho_section.csv"
    elif occ_only:
        grid = [(48.0, 0.0, o) for o in config.OCC_LEVELS_PCT]
        out_csv = out_csv or config.OUTPUTS / f"occ_section_div{occ_divisor}.csv"
    else:
        grid = [(r, t, o) for r in config.RHO_LEVELS_PX
                for t in config.THETA_LEVELS_DEG for o in config.OCC_LEVELS_PCT]
        out_csv = out_csv or config.GRID_RESULTS_CSV

    # 이미 계산된 조건은 건너뛴다. 격자를 넓힐 때 앞선 결과를 다시 돌리지 않는다.
    done: dict[tuple, dict] = {}
    if out_csv.exists() and not limit:
        with out_csv.open(encoding="utf-8") as f:
            stale = 0
            for row in csv.DictReader(f):
                # **다른 검출기로 잰 행은 버린다.** 조건만 맞다고 가져다 쓰면
                # v8n 수치에 yolo26s 라는 이름이 붙는다.
                if row.get("detector", "") != config.DETECTOR_ARCH:
                    stale += 1
                    continue
                key = (float(row["rho_px"]), float(row["theta_deg"]),
                       float(row["occ_pct_target"]))
                done[key] = row
        if stale:
            print(f"다른 검출기의 기존 행 {stale}개를 버린다 "
                  f"(현재 {config.DETECTOR_ARCH})")
        if done:
            print(f"기존 결과 {len(done)}조건을 재사용한다")

    model = YOLO(str(WEIGHTS))
    rows = []
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    def flush():
        """조건 하나가 끝날 때마다 쓴다.

        맨 끝에 한 번만 쓰면 중간에 프로세스가 죽었을 때 몇 시간치가 통째로
        날아간다. 이 환경에서 장시간 작업이 끊기는 일이 있어 매번 흘려둔다.
        재실행하면 위의 `done` 이 읽어 이어서 돈다.
        """
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)

    for i, (r, t, o) in enumerate(grid, 1):
        cached = done.get((float(r), float(t), float(o)))
        if cached is not None:
            rows.append(cached)
            continue
        row = run_condition(model, records, r, t, o, manifest['min_head_px'],
                            occ_divisor)
        rows.append(row)
        flush()
        print(f"[{i}/{len(grid)}] ρ={r:>2} θ={t:>2} o={o:>2}  "
              f"recall_nohat {row['recall_nohat']}  recall_hat {row['recall_hat']}",
              flush=True)

    if rows:
        flush()
    print(f"→ {out_csv}  ({len(rows)}조건 · 이미지 {len(records)}장)")
    return out_csv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="9조건만 (§7 Phase 1)")
    ap.add_argument("--limit", type=int, default=None, help="이미지 수 제한 (디버그용)")
    ap.add_argument("--occ-divisor", type=int, default=T.DEFAULT_STRIPE_DIVISOR,
                    help="스트라이프 주기 = 화면 가로 / divisor")
    ap.add_argument("--occ-only", action="store_true",
                    help="h(o) 단면(ρ=48, θ=0)만 - 주기 민감도용")
    ap.add_argument("--out", type=Path, default=None, help="출력 CSV 경로")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="실험셋 manifest 경로 (기본: data/filtered/manifest.json)")
    ap.add_argument("--rho-only", action="store_true",
                    help="f(ρ) 단면(θ=0, o=0)만 - 데이터셋 간 비교용")
    args = ap.parse_args()
    main(args.smoke, args.limit, args.occ_divisor, args.out, args.occ_only,
         args.manifest, args.rho_only)
