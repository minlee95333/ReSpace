# -*- coding: utf-8 -*-
"""변형 없는 실사진에서 f(ρ) 를 직접 잰다 (2026-08-25).

왜 있는가:
  `transforms.apply_rho` 는 다운샘플 후 **원본 크기로 되돌린다**. 머리가 화면에서
  차지하는 크기는 그대로라 흐려짐만 재고 작아짐은 못 잰다. 검출기에게 이 둘은
  다른 문제다. 실제로 GDUT-HWD 로 갈라보니:

      머리 12px   변형으로 만든 것 0.897   /   실제 12px 머리 0.504

  같은 데이터에서 갈렸으므로 원인은 데이터가 아니라 변형 방식이다.
  따라서 ρ 축만은 합성이 아니라 **실사진의 실제 머리 크기**로 잰다.

  θ·o 는 실사진에 라벨이 없어 합성 변형을 유지한다. 두 축은 ρ=48 기준에서
  쟀으므로 작은 머리에서의 열화가 빠져 있다 — 낙관 방향이며 제안서에 적는다.

전제:
  검출기가 해당 영역을 **원 해상도로** 본다고 본다(타일링·크롭 추론). 4K 프레임을
  통째로 640 으로 줄여 넣는 파이프라인이면 12px 머리는 2px 이 되어 이보다 나쁘다.

산출: outputs/native_instances.json (인스턴스별 크기·적중), outputs/native_curve.json
"""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

GD = config.DATA_RAW / "GDUT-HWD"
HAT_NAMES = {"blue", "white", "yellow", "red"}
OUT_INST = config.OUTPUTS / "native_instances.json"


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    w, h = max(0.0, x2 - x1), max(0.0, y2 - y1)
    inter = w * h
    if inter <= 0:
        return 0.0
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


# 데이터셋 두 개를 같은 방식으로 잰다. SHWD 는 학습에 쓴 데이터라 test 분할만
# 쓰더라도 같은 수집 경로의 사진이다 — 교차 확인용이지 근거의 주가 아니다.
DATASETS = {
    "gdut": {"root": GD, "split": "ImageSets/Main/test.txt",
             "hat": HAT_NAMES, "none": {"none"},
             "label": "GDUT-HWD test (변형 없음)"},
    "shwd": {"root": config.DATA_RAW / "VOC2028", "split": "ImageSets/Main/test.txt",
             "hat": {"hat"}, "none": {"person"},
             "label": "SHWD/VOC2028 test (변형 없음)"},
}


def main(dataset: str = "gdut", weights: Path | None = None,
         out_path: Path | None = None):
    from ultralytics import YOLO
    ds = DATASETS[dataset]
    global GD, HAT_NAMES, OUT_INST
    GD = ds["root"]
    HAT_NAMES = ds["hat"]
    none_names = ds["none"]
    OUT_INST = out_path or (config.OUTPUTS / f"native_instances_{dataset}.json")
    stems = sorted((GD / ds["split"]).read_text().split())
    model = YOLO(str(weights or config.DETECTOR_BEST))
    names = model.names
    recs = []
    for i, s in enumerate(stems, 1):
        root = ET.parse(GD / "Annotations" / f"{s}.xml").getroot()
        gts = []
        for o in root.findall("object"):
            raw = (o.findtext("name") or "").strip()
            if raw in HAT_NAMES:
                cls = "hat"
            elif raw in none_names:
                cls = "person"
            else:
                continue
            b = o.find("bndbox")
            box = [float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
            gts.append({"cls": cls, "box": box,
                        "short": min(box[2]-box[0], box[3]-box[1]), "hit": False})
        if not gts:
            continue
        r = model.predict(str(GD / "JPEGImages" / f"{s}.jpg"),
                          conf=config.CONF_THR, verbose=False)[0]
        det = [(names[int(c)], b.tolist())
               for c, b in zip(r.boxes.cls, r.boxes.xyxy)]
        # 클래스별로 탐욕 매칭. run_grid.match 와 같은 규칙(IoU>=0.5, 1:1)
        for cls in ("hat", "person"):
            gs = [g for g in gts if g["cls"] == cls]
            for _, db in [d for d in det if d[0] == cls]:
                best, bg = 0.0, None
                for g in gs:
                    if g["hit"]:
                        continue
                    v = iou(db, g["box"])
                    if v > best:
                        best, bg = v, g
                if bg is not None and best >= config.IOU_THR:
                    bg["hit"] = True
        for g in gts:
            recs.append({"stem": s, "cls": g["cls"],
                         "short_px": round(g["short"], 1), "hit": int(g["hit"])})
        if i % 400 == 0:
            print(f"  {i}/{len(stems)}", flush=True)

    OUT_INST.parent.mkdir(parents=True, exist_ok=True)
    OUT_INST.write_text(json.dumps({
        "source": ds["label"],
        "detector": config.DETECTOR_ARCH,
        "detector_weights": str(Path(weights or config.DETECTOR_BEST).resolve().relative_to(config.ROOT)),
        "iou_thr": config.IOU_THR, "conf_thr": config.CONF_THR,
        "n_images": len(stems), "n_instances": len(recs),
        "instances": recs,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"인스턴스 {len(recs)}개 -> {OUT_INST}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(DATASETS), default="gdut")
    ap.add_argument("--weights", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    main(a.dataset, a.weights, a.out)


# ── f(ρ) 피팅 ──────────────────────────────────────────────────────────────
# 구간 평균이 아니라 **인스턴스 단위 최대우도**로 맞춘다. 구간 경계·대표값을
# 어떻게 잡느냐에 결과가 흔들리지 않게 하려는 것이다.

def fit(path: Path = None, out_path: Path = None) -> dict:
    path = Path(path or config.OUTPUTS / "native_instances_gdut.json")
    import math
    import numpy as np
    from scipy.optimize import minimize

    data = json.loads(path.read_text(encoding="utf-8"))
    out = {
        "source": data["source"],
        "detector": data["detector"],
        "detector_weights": data["detector_weights"],
        "iou_thr": data["iou_thr"], "conf_thr": data["conf_thr"],
        "method": "인스턴스 단위 베르누이 최대우도. 3모수 로지스틱 L/(1+exp(-k(x-x0)))",
        "note": "변형 없는 실사진의 실제 머리 픽셀 크기로 잰 값이다",
        "targets": {},
    }
    for tgt, cls in (("helmet_nohat", "person"), ("helmet_worn", "hat")):
        xs = np.array([r["short_px"] for r in data["instances"] if r["cls"] == cls])
        ys = np.array([r["hit"] for r in data["instances"] if r["cls"] == cls], float)

        def nll(p):
            L, k, x0 = p
            if not (0.05 < L <= 1.0) or k <= 0:
                return 1e9
            q = np.clip(L / (1.0 + np.exp(-np.clip(k * (xs - x0), -50, 50))), 1e-9, 1 - 1e-9)
            return -np.sum(ys * np.log(q) + (1 - ys) * np.log(1 - q))

        best = None
        for x0_0 in (8.0, 13.0, 20.0):
            for k_0 in (0.1, 0.2, 0.4):
                r = minimize(nll, [0.93, k_0, x0_0], method="Nelder-Mead",
                             options={"maxiter": 20000, "xatol": 1e-6, "fatol": 1e-6})
                if best is None or r.fun < best.fun:
                    best = r
        L, k, x0 = best.x
        # 구간별 관측치도 같이 남긴다 - 눈으로 확인할 수 있게
        edges = [4, 8, 12, 16, 24, 32, 48, 96, 10**9]
        bins = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (xs >= lo) & (xs < hi)
            if m.sum():
                bins.append({"lo": lo, "hi": None if hi > 10**8 else hi,
                             "n": int(m.sum()), "recall": round(float(ys[m].mean()), 4),
                             "fitted": round(float(L / (1 + math.exp(-k * (float(xs[m].mean()) - x0)))), 4)})
        out["targets"][tgt] = {
            "class": cls, "n_instances": int(len(xs)),
            "f_rho": {"form": "logistic", "L": float(L), "k": float(k), "x0": float(x0),
                      "measured_range_px": [float(xs.min()), float(xs.max())],
                      "extrapolation": "4px 미만은 detect_model.py 가 0 으로 본다"},
            "nll": float(best.fun), "bins": bins,
        }
    p = Path(out_path or config.OUTPUTS / "native_curve.json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
