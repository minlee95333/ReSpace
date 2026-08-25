# -*- coding: utf-8 -*-
"""가림 곡선이 머리 크기에 따라 달라지는가 (2026-08-25).

왜 필요한가:
  분리형 곱셈 모델 P = f(ρ)·g(θ)·h(o) 는 축이 서로 독립이라고 본다. 그런데
  h(o) 는 SHWD 를 ρ=48px 기준 단면에서 재서 얻었다 — **큰 머리만 본 값**이다.
  작은 머리는 같은 비율을 가려도 더 치명적일 수 있고, 그렇다면 현장 WDR 이
  실제보다 높게 나온다.

어떻게 보는가:
  GDUT-HWD 실사진에 **가림 스트라이프만** 얹는다. ρ 변형을 걸지 않으므로
  머리 크기는 사진에 있던 그대로다. 인스턴스별로 (실제 머리 크기, 실제 가림률,
  적중) 을 기록하고, 크기 구간별로 h(o) 를 따로 맞춰 λ 를 비교한다.

  λ 가 구간마다 크게 다르면 분리 가정이 깨진 것이고, 그 사실을 제안서에
  적어야 한다. 값이 비슷하면 가정이 버틴 것이다.

산출: outputs/native_occ.json
"""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import transforms as T
from native_curve import iou, HAT_NAMES, GD

OUT = config.OUTPUTS / "native_occ.json"
SIZE_BINS = [(6, 16), (16, 32), (32, 10**9)]   # 작은 / 중간 / 큰 머리


def main(occ_levels=None) -> dict:
    import cv2
    from ultralytics import YOLO

    occ_levels = occ_levels or config.OCC_LEVELS_PCT
    stems = sorted((GD / "ImageSets/Main/test.txt").read_text().split())
    model = YOLO(str(config.DETECTOR_BEST))
    names = model.names
    recs = []

    for oi, occ_pct in enumerate(occ_levels, 1):
        occ_ratio = occ_pct / 100.0
        for i, s in enumerate(stems, 1):
            root = ET.parse(GD / "Annotations" / f"{s}.xml").getroot()
            gts = []
            for o in root.findall("object"):
                raw = (o.findtext("name") or "").strip()
                if raw in HAT_NAMES:
                    cls = "hat"
                elif raw == "none":
                    cls = "person"
                else:
                    continue
                b = o.find("bndbox")
                box = [float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")]
                gts.append({"cls": cls, "box": box,
                            "short": min(box[2]-box[0], box[3]-box[1]), "hit": False})
            if not gts:
                continue
            img = cv2.imread(str(GD / "JPEGImages" / f"{s}.jpg"))
            if img is None:
                continue
            w = img.shape[1]
            spans = T.stripe_spans(w, occ_ratio) if occ_ratio > 0 else []
            out = img if occ_ratio == 0 else T.apply_occlusion(img, occ_ratio)[0]

            r = model.predict(out, conf=config.CONF_THR, verbose=False)[0]
            det = [(names[int(c)], b.tolist())
                   for c, b in zip(r.boxes.cls, r.boxes.xyxy)]
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
                recs.append({"cls": g["cls"], "short_px": round(g["short"], 1),
                             # 개체 단위 가림률 - 곡선 입력과 같은 정의(§4.5)
                             "occ_box": round(T.box_occlusion(g["box"], spans), 4),
                             "occ_target": occ_pct, "hit": int(g["hit"])})
        print(f"  o={occ_pct}% 완료 ({oi}/{len(occ_levels)})", flush=True)

    OUT.write_text(json.dumps({
        "source": "GDUT-HWD test · 가림 스트라이프만 적용 (ρ 변형 없음)",
        "detector": config.DETECTOR_ARCH,
        "stripe_divisor": T.DEFAULT_STRIPE_DIVISOR,
        "occ_levels_pct": list(occ_levels),
        "size_bins_px": SIZE_BINS,
        "n_records": len(recs),
        "records": recs,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"기록 {len(recs)}개 -> {OUT}")
    return {"n": len(recs)}


if __name__ == "__main__":
    main()
