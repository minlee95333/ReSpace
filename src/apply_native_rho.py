# -*- coding: utf-8 -*-
"""f(ρ) 를 합성 변형 값에서 **실사진 실측값**으로 교체한다 (2026-08-25).

배경:
  `transforms.apply_rho` 는 다운샘플 뒤 원본 크기로 되돌리므로 머리가 화면에서
  차지하는 크기가 그대로다. 흐려짐만 재고 작아짐을 못 잰다. GDUT-HWD 로 갈라보니
  같은 데이터에서도 갈렸다 — 12px 구간에서 합성 0.897 / 실사진 0.504.
  원인은 데이터가 아니라 변형 방식이므로 ρ 축만 실사진 실측으로 바꾼다.

바꾸는 것: `f_rho` (두 항목 모두)
그대로 두는 것: `g_theta`, `h_occ`
  실사진에는 부감각·가림률 라벨이 없어 합성 변형 외에 잴 방법이 없다.
  두 축은 ρ=48 기준 단면에서 쟀으므로 **작은 머리에서의 열화가 빠져 있다.**
  낙관 방향이며 제안서에 명시한다.

R² 처리:
  종전 `r2_full_grid` 은 분리형 모델이 **합성 288조건 격자**를 얼마나 맞히는지의
  값이다. ρ 축을 실측으로 갈아끼운 뒤에는 그 격자를 맞히는 것이 목적이 아니므로
  그대로 두면 새 곡선을 검증한 값처럼 읽힌다. `r2_full_grid` 은 null 로 두고
  옛 값은 `r2_full_grid_synthetic_rho` 에 보존한다. ρ 축의 적합도는
  `r2_rho_native`(구간 가중 R²)로 따로 싣는다.
"""
from pathlib import Path
import json
import math
import sys

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

BACKUP = config.OUTPUTS / "curve_params_synthetic_rho.json"
NATIVE = config.OUTPUTS / "native_curve.json"


def binned_r2(bins: list) -> float:
    """구간 관측 재현율 대 피팅값. 구간 인스턴스 수로 가중한다."""
    n = sum(b["n"] for b in bins)
    mean = sum(b["n"] * b["recall"] for b in bins) / n
    ss_res = sum(b["n"] * (b["recall"] - b["fitted"]) ** 2 for b in bins)
    ss_tot = sum(b["n"] * (b["recall"] - mean) ** 2 for b in bins)
    return 1.0 - ss_res / ss_tot


def main() -> dict:
    cur = json.loads(config.CURVE_PARAMS_JSON.read_text(encoding="utf-8"))
    nat = json.loads(NATIVE.read_text(encoding="utf-8"))

    if cur.get("f_rho_source", "").startswith("native"):
        raise SystemExit("이미 실측 ρ 로 교체된 파일이다. 되돌리려면 "
                         f"{BACKUP.name} 을 복사할 것.")
    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(cur, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    for tgt, block in nat["targets"].items():
        if tgt not in cur["per_target"]:
            continue
        f = dict(block["f_rho"])
        f["measured_on"] = nat["source"]
        f["measured_by"] = "src/native_curve.py — 인스턴스 단위 최대우도"
        f["n_instances"] = block["n_instances"]
        f["r2_binned"] = round(binned_r2(block["bins"]), 4)
        f["replaces"] = ("합성 변형(apply_rho)으로 잰 값. 그 방식은 머리를 흐리게만 "
                         "만들고 작게 만들지 않아 원거리를 과대평가했다")
        cur["per_target"][tgt]["f_rho_synthetic"] = cur["per_target"][tgt]["f_rho"]
        cur["per_target"][tgt]["f_rho"] = f
        cur["per_target"][tgt]["r2_full_grid_synthetic_rho"] = \
            cur["per_target"][tgt].pop("r2_full_grid", None)
        cur["per_target"][tgt]["r2_rho_native"] = f["r2_binned"]

    cur["f_rho_source"] = "native measurement on GDUT-HWD test (변형 없음)"
    cur["g_theta_h_occ_source"] = "합성 변형 288조건 격자 (SHWD test 500장)"
    cur["r2_full_grid_synthetic_rho"] = cur.pop("r2_full_grid", None)
    cur["r2_primary_synthetic_rho"] = cur.pop("r2_primary", None)
    cur["r2_full_grid"] = None
    cur["r2_primary"] = None
    cur["r2_rho_native"] = min(
        cur["per_target"][t]["r2_rho_native"] for t in nat["targets"]
        if t in cur["per_target"])
    cur["r2_note"] = ("r2_full_grid 은 ρ 축이 합성이던 때의 지표라 더 이상 이 곡선을 "
                      "설명하지 않는다. 옛 값은 *_synthetic_rho 에 보존했다. "
                      "ρ 축 적합도는 r2_rho_native 를 볼 것")
    cur["revision"] = "2026-08-25 ρ축 실측 교체"
    cur["generated_at"] = nat.get("generated_at") or cur.get("generated_at")

    config.CURVE_PARAMS_JSON.write_text(
        json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return cur


if __name__ == "__main__":
    c = main()
    print(f"백업 -> {BACKUP.name}")
    for t, v in c["per_target"].items():
        f, s = v["f_rho"], v["f_rho_synthetic"]
        print(f"[{t}] x0 {s['x0']:.2f} -> {f['x0']:.2f}px · k {s['k']:.4f} -> {f['k']:.4f} "
              f"· L {s['L']:.4f} -> {f['L']:.4f}  (R²_binned {f['r2_binned']})")
