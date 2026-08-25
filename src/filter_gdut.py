# -*- coding: utf-8 -*-
"""GDUT-HWD 필터링 — `filter_data.py` 의 GDUT 판.

왜 있는가 (2026-08-25):
  ρ 곡선이 SHWD 합성 변형에서 나왔는데, 같은 검출기로 GDUT-HWD **실사진**의
  머리 크기별 재현율을 재보니 크게 어긋났다 (12~16px 구간에서 0.504 vs 0.935).
  원인 후보가 둘이다.
    (a) 데이터가 달라서            → GDUT 에 같은 변형을 걸면 SHWD 와 같이 나온다
    (b) 변형 방식이 틀려서          → GDUT 에 걸어도 실사진 값과 어긋난다
  `apply_rho` 는 다운샘플 후 **원본 크기로 되돌리므로** 머리가 화면에서 차지하는
  크기는 그대로다. 즉 흐려짐만 재고 작아짐은 안 잰다. (b) 가 유력하지만
  측정해서 가른다. 이 모듈은 그 측정을 위한 실험셋을 만든다.

`filter_data.py` 와 같은 형식의 manifest 를 낸다. 뒤 단계가 그대로 읽는다.
난수를 쓰지 않는다 — 파일명 정렬 순서로만 고른다.
"""
from pathlib import Path
import json
import statistics
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

GD_ROOT = config.DATA_RAW / "GDUT-HWD"
ANNOTATIONS = GD_ROOT / "Annotations"
IMAGES = GD_ROOT / "JPEGImages"
SPLITS = GD_ROOT / "ImageSets" / "Main"
MANIFEST = config.DATA_FILTERED / "manifest_gdut.json"

EVAL_SPLIT = "test"          # 1,587장. SHWD 로 학습했으므로 누수 자체는 없으나
                             # 원 논문 분할을 지켜 비교 가능하게 둔다
REF_HEAD_PX = 48.0           # ρ 기준 조건. apply_rho 는 다운샘플만 하므로 필요하다

# GDUT 는 헬멧 색을 4개 클래스로 나눈다. 우리 두 클래스로 접는다.
HAT_NAMES = {"blue", "white", "yellow", "red"}
NONE_NAME = "none"


def parse_annotation(xml_path: Path, min_head_px: float) -> dict | None:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    kept, every = [], []
    for obj in root.findall("object"):
        raw = (obj.findtext("name") or "").strip()
        if raw in HAT_NAMES:
            name = "hat"
        elif raw == NONE_NAME:
            name = "person"
        else:
            continue
        b = obj.find("bndbox")
        x1, y1 = float(b.findtext("xmin")), float(b.findtext("ymin"))
        x2, y2 = float(b.findtext("xmax")), float(b.findtext("ymax"))
        inst = {"cls": name, "bbox": [x1, y1, x2, y2],
                "short_px": round(min(x2 - x1, y2 - y1), 1)}
        every.append(inst)
        if min(x2 - x1, y2 - y1) >= min_head_px:
            kept.append(inst)
    if not kept:
        return None
    return {
        "stem": xml_path.stem,
        "image": str((IMAGES / f"{xml_path.stem}.jpg").relative_to(config.ROOT)),
        "width": int(size.findtext("width")),
        "height": int(size.findtext("height")),
        "instances": kept,
        "all_instances": every,
        "ref_head_px": round(statistics.median(k["short_px"] for k in kept), 1),
        "n_hat": sum(1 for k in kept if k["cls"] == "hat"),
        "n_person": sum(1 for k in kept if k["cls"] == "person"),
    }


def select(records: list[dict], target: int) -> list[dict]:
    """두 클래스가 고루 들어가도록 target 장. `filter_data.select` 와 같은 규칙."""
    both = [r for r in records if r["n_hat"] and r["n_person"]]
    hat_only = [r for r in records if r["n_hat"] and not r["n_person"]]
    per_only = [r for r in records if r["n_person"] and not r["n_hat"]]
    chosen = both[:target]
    i = j = 0
    while len(chosen) < target and (i < len(hat_only) or j < len(per_only)):
        if i < len(hat_only):
            chosen.append(hat_only[i]); i += 1
        if len(chosen) < target and j < len(per_only):
            chosen.append(per_only[j]); j += 1
    return chosen


def main(min_head_px: float = config.MIN_HEAD_PX,
         target: int = config.TARGET_IMAGES) -> dict:
    if not ANNOTATIONS.is_dir():
        raise FileNotFoundError(
            f"어노테이션이 없다: {ANNOTATIONS}\n"
            "GDUT-HWD.zip 을 data/raw/GDUT-HWD/ 아래에 풀어야 한다."
        )
    stems = sorted((SPLITS / f"{EVAL_SPLIT}.txt").read_text().split())

    def collect(min_px: float) -> list[dict]:
        out = []
        for stem in stems:
            xml_path = ANNOTATIONS / f"{stem}.xml"
            if not xml_path.exists():
                continue
            rec = parse_annotation(xml_path, min_px)
            if rec and rec["ref_head_px"] >= REF_HEAD_PX:
                out.append(rec)
        return out

    records = collect(min_head_px)
    relaxed = False
    if len(records) < target:
        relaxed = True
        records = collect(config.MIN_HEAD_PX_RELAXED)

    chosen = select(records, target)
    manifest = {
        "source": "GDUT-HWD (Wu et al., Automation in Construction 106, 2019)",
        "source_license": "Apache-2.0 (github.com/wujixiu/helmet-detection)",
        "split": EVAL_SPLIT,
        "split_reason": "원 논문 test 분할. 검출기는 SHWD 로 학습했으므로 전 구간이 미학습이다",
        "class_map": "blue/white/yellow/red -> hat, none -> person",
        "min_head_px": config.MIN_HEAD_PX_RELAXED if relaxed else min_head_px,
        "relaxed_to_30px": relaxed,
        "ref_head_px_min": REF_HEAD_PX,
        "n_candidates": len(records),
        "n_selected": len(chosen),
        "n_hat": sum(r["n_hat"] for r in chosen),
        "n_person": sum(r["n_person"] for r in chosen),
        "selection": "파일명 정렬 순서. 난수 없음",
        "images": chosen,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = main()
    print(f"후보 {m['n_candidates']}장 -> 선정 {m['n_selected']}장")
    print(f"인스턴스: hat {m['n_hat']} · person(미착용) {m['n_person']}")
    print(f"-> {MANIFEST}")
