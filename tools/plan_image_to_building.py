# -*- coding: utf-8 -*-
"""종합가설계획도 이미지 → `data/building.json` 의 동 평면 (2026-08-27).

**왜 만들었나.** 종전 `building.json` 은 동 하나를 **사각형 하나**로 두었다.
실제 도면을 다시 보니 셋이 틀렸다.

  ① 각도  401·402·403 이 -23.6° 로 기울어 있는데 모델은 0° 였다
  ② 형상  404·405 는 **ㄱ자(두 덩어리)** 인데 사각형 하나였다
  ③ 요철  판상형이라 외곽이 톱니인데 매끈한 사각형이었다.
          사각형은 실제 바닥면적을 **80% 과대평가**한다 — 그만큼 가림을
          부풀려 계산해 왔다는 뜻이다

**어떻게.** 도면에서 동은 단색(109,139,225)으로 칠해져 있다. 그 색을 골라
연결 성분으로 나누고, 성분마다 주축을 찾아 그 좌표계로 돌린 뒤 장축을 따라
얇게 썰어 같은 폭이 이어지는 구간을 상자로 묶는다. 요철이 그대로 남는다.

**자동 도면 인식이 아니다.** 채움색 하나를 아는 상태에서 골라내는 것이며,
축척도 사람이 준다. `mockup/digitize.html` 이 클릭으로 하는 일을 이 도면에서는
색으로 할 수 있어 그렇게 한 것뿐이다.

**축척은 앵커로 준다.** 이 도면에는 축척 막대가 없다. 401동 장축을 46.0 m 로
두는데, 이는 종전 `building.json` 이 건축물현황도(축척 1:2000)에서 읽은 값이다.
**따라서 이 변환은 그 값의 오차를 물려받는다.**

**대지 경계는 이번에 다시 잡지 않는다.** 210 x 125 m 를 그대로 두고 동들을
도면상 상대 위치대로 그 안에 앉힌다. 경계까지 손대면 복셀 격자와 지표의 분모가
함께 바뀌어 비교가 끊긴다.

    python tools/plan_image_to_building.py <도면.png>            # 갱신
    python tools/plan_image_to_building.py <도면.png> --dry      # 미리보기만
    python tools/plan_image_to_building.py <도면.png> --verify   # 겹쳐 그려 확인

**--verify 는 최종 building.json 을 site_model 로 읽어 그린다.** 중간 계산을
그리면 안 된다 — 실제로 한 번 속았다. 생성기가 상자 중심을 회전시키지 않아
기운 판들이 가로축을 따라 줄지어 섰는데, 검증 그림은 제 중간 좌표를 그려서
멀쩡해 보였다. 계산이 쓰는 것과 같은 경로로만 검증한다.
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

import numpy as np
from PIL import Image
from scipy import ndimage

OUT = ROOT / "data" / "building.json"

FILL_RGB = (109, 139, 225)      # 동 채움색
FILL_TOL = 90                   # |ΔR|+|ΔG|+|ΔB| 허용
MIN_BLOB_PX = 800               # 이보다 작은 덩어리는 라벨·부대시설로 본다

SLICE_M = 2.0                   # 장축을 이 간격으로 썬다
MERGE_TOL_M = 1.5               # 폭이 이만큼 안에서 같으면 한 상자로 합친다
ANCHOR_M = 46.0                 # 401동 장축 (종전 building.json 값)

SITE_W, SITE_D = 210.0, 125.0   # 대지 - 이번에 다시 잡지 않는다
STOREY_H = 2.9
N_STOREY = 5                    # 지상 + 4개 층 (골조 공사 중)
SLAB_T = 0.3
CORE_W, CORE_D = 6.0, 8.0       # 코어 평면 - 종전 값을 잇는다
SCAFFOLD_GAP, SCAFFOLD_W = 1.0, 0.9

# 덩어리 → 동 이름. 도면을 보고 사람이 짝지은 것이며 자동이 아니다.
# 면적 내림차순 상위 7개에 대해, 도면상 위치(중심 좌표)로 가른다.
def name_blobs(info: dict) -> dict:
    """중심 좌표로 동을 짝짓는다. 도면 배치가 바뀌면 여기를 고쳐야 한다."""
    ordered = sorted(info.items(), key=lambda kv: -kv[1]["n"])
    out = {}
    for k, o in ordered:
        x, y = o["cx"], o["cy"]
        if y < 260:                       out[k] = ("401동", 0)
        elif x > 470 and y < 430:         out[k] = ("402동", 0)
        elif x > 560 and y > 500:         out[k] = ("403동", 0)
        elif y > 500:                     out[k] = ("404동", 1 if x < 360 else 2)
        elif x < 470:                     out[k] = ("405동", 1 if x < 310 else 2)
    return out


def blobs(path: Path) -> tuple:
    a = np.array(Image.open(path).convert("RGB")).astype(int)
    d = np.abs(a - np.array(FILL_RGB)).sum(axis=2)
    m = d < FILL_TOL
    # 라벨 글자가 채움 위에 얹혀 구멍을 낸다. 닫고 메운다.
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, np.ones((5, 5))))
    lab, n = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = {}
    for i, s in enumerate(sizes):
        if s < MIN_BLOB_PX:
            continue
        k = i + 1
        ys, xs = np.where(lab == k)
        pts = np.stack([xs, ys], 1).astype(float)
        c = pts.mean(0)
        e = np.linalg.svd(pts - c, full_matrices=False)[2][0]
        keep[k] = {"cx": float(c[0]), "cy": float(c[1]), "n": int(s),
                   "e": e, "pts": pts}
    return lab, keep


def slice_boxes(pts: np.ndarray, e: np.ndarray, mpp: float) -> tuple:
    """주축 좌표계에서 썰어 상자 목록을 낸다. (중심px, 각도, [(u0,u1,v0,v1)])"""
    c = pts.mean(0)
    R = np.array([e, [-e[1], e[0]]])
    loc = (pts - c) @ R.T * mpp
    u, v = loc[:, 0], loc[:, 1]
    n = max(1, int(round((u.max() - u.min()) / SLICE_M)))
    ed = np.linspace(u.min(), u.max(), n + 1)
    out = []
    for i in range(n):
        sel = (u >= ed[i]) & (u <= ed[i + 1])
        if sel.sum() < 4:
            continue
        s = [ed[i], ed[i + 1], float(v[sel].min()), float(v[sel].max())]
        if out and abs(out[-1][2] - s[2]) < MERGE_TOL_M \
              and abs(out[-1][3] - s[3]) < MERGE_TOL_M:
            out[-1][1] = s[1]
            out[-1][2] = min(out[-1][2], s[2])
            out[-1][3] = max(out[-1][3], s[3])
        else:
            out.append(s)
    return c, math.degrees(math.atan2(e[1], e[0])), out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("사용: python tools/plan_image_to_building.py <도면.png> [--dry]")
    img = Path(args[0])
    dry = "--dry" in sys.argv

    lab, info = blobs(img)
    names = name_blobs(info)
    if not names:
        raise SystemExit("동을 하나도 찾지 못했다. FILL_RGB 를 확인할 것")

    # 축척 — 401동 장축을 앵커로
    a401 = next(k for k, (nm, _) in names.items() if nm == "401동")
    p = info[a401]["pts"]; e = info[a401]["e"]
    c = p.mean(0); R = np.array([e, [-e[1], e[0]]])
    span_px = float(np.ptp(((p - c) @ R.T)[:, 0]))
    mpp = ANCHOR_M / span_px
    print(f"축척 앵커 401동 {ANCHOR_M} m / {span_px:.1f}px  ->  1px = {mpp:.4f} m")

    # 조각마다 상자를 뽑아 세계 좌표(미터, y 위쪽)로 옮긴다
    parts = []
    for k, (nm, part) in names.items():
        cpx, ang_img, boxes = slice_boxes(info[k]["pts"], info[k]["e"], mpp)
        yaw = -ang_img                       # 이미지 y 는 아래로 간다
        parts.append({"dong": nm, "part": part, "cpx": cpx, "yaw": yaw,
                      "boxes": boxes})

    # 원점 잡기 — 도면상 상대 위치를 지키며 대지 안에 가운데로 앉힌다
    xs, ys = [], []
    for pt in parts:
        cx, cy = pt["cpx"]
        r = math.radians(pt["yaw"]); co, si = math.cos(r), math.sin(r)
        for (u0, u1, v0, v1) in pt["boxes"]:
            for (u, v) in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
                xs.append(cx * mpp + u * co - v * si)
                ys.append(-cy * mpp + u * si + v * co)
    ox = (SITE_W - (max(xs) - min(xs))) / 2 - min(xs)
    oy = (SITE_D - (max(ys) - min(ys))) / 2 - min(ys)
    print(f"동 전체 범위 {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} m "
          f"-> 대지 {SITE_W:.0f} x {SITE_D:.0f} m 안에 가운데 정렬")

    levels = [round(i * STOREY_H, 2) for i in range(N_STOREY)]
    top = levels[-1] + SLAB_T
    solids, n_box = [], 0

    for pt in parts:
        cx, cy = pt["cpx"]
        wx, wy = cx * mpp + ox, -cy * mpp + oy
        tag = pt["dong"] + ("" if pt["part"] == 0 else f"-{'AB'[pt['part']-1]}")
        rr = math.radians(pt["yaw"]); rco, rsi = math.cos(rr), math.sin(rr)
        for bi, (u0, u1, v0, v1) in enumerate(pt["boxes"]):
            n_box += 1
            # box 는 **회전 전** 좌표이고 site_model 이 상자마다 제 중심을 축으로
            # yaw 만큼 돌린다. 그러므로 **중심은 미리 돌려서 놓아야 한다** -
            # 안 돌리면 기운 판들이 가로축을 따라 줄지어 서고(실측: 조각 배열
            # 방향 +0.6°, yaw -23.6°) 건물이 계단 모양이 된다.
            # 반너비는 그대로다. 상자의 u·v 축이 회전 뒤 제 방향을 갖는다.
            lu, lv = (u0 + u1) / 2, (v0 + v1) / 2
            bx = lu * rco - lv * rsi
            by = lu * rsi + lv * rco
            hx, hy = (u1 - u0) / 2, (v1 - v0) / 2
            for z in levels:
                if z <= 0:
                    continue
                solids.append({
                    "kind": "slab",
                    "box": [round(wx + bx - hx, 2), round(wy + by - hy, 2),
                            round(z - SLAB_T, 2),
                            round(wx + bx + hx, 2), round(wy + by + hy, 2),
                            round(z, 2)],
                    "yaw_deg": round(pt["yaw"], 2),
                    # **한 판을 여러 상자로 쪼갠 것임을 밝힌다.**
                    # 안 밝히면 zone_derive 가 조각 사이 이음매까지 "슬래브
                    # 단부" 로 잡는다 - 실제 단부가 아닌데 236개가 생겼다.
                    # 같은 group 은 한 장의 판이며 바깥 테두리만 단부다.
                    "group": f"{tag}@{z:g}",
                    "note": f"{tag} 슬래브 {bi+1} (두께 {SLAB_T}m)",
                    "source": "종합가설계획도 색분리",
                })
        # 코어 - 조각 가운데. 도면에서 코어를 가려낼 수 없어 종전 규약을 잇는다.
        # **슬래브 관통부로도 등록한다** - zone_derive 의 R4 가 이 구멍
        # 좌표에서 '개구부 주변'(떨어짐, w10) 위험구역을 낸다. 안 넣으면 그
        # 구역이 통째로 사라진다.
        core_op = [round(-CORE_W/2 + wx, 2), round(-CORE_D/2 + wy, 2),
                   round(CORE_W/2 + wx, 2), round(CORE_D/2 + wy, 2)]
        for sd in solids:
            if sd["kind"] == "slab" and sd.get("group", "").startswith(tag + "@"):
                sd["openings"] = [core_op]
                sd["openings_source"] = "코어 관통부 (도면에서 코어를 가려낼 수 없어 규약)"
        solids.append({
            "kind": "core",
            "box": [round(wx - CORE_W/2, 2), round(wy - CORE_D/2, 2), 0.0,
                    round(wx + CORE_W/2, 2), round(wy + CORE_D/2, 2), round(top, 2)],
            "yaw_deg": round(pt["yaw"], 2),
            "note": f"{tag} 계단실·엘리베이터 코어",
            "source": "종전 규약 (도면에서 코어를 가려낼 수 없다)",
        })
        # 외곽 비계 - 조각의 외접 상자를 1m 띄운 네 띠
        uu0 = min(b[0] for b in pt["boxes"]); uu1 = max(b[1] for b in pt["boxes"])
        vv0 = min(b[2] for b in pt["boxes"]); vv1 = max(b[3] for b in pt["boxes"])
        g, w = SCAFFOLD_GAP, SCAFFOLD_W
        for si_, (a0, b0, a1, b1) in enumerate((
                (uu0-g-w, vv0-g-w, uu1+g+w, vv0-g), (uu0-g-w, vv1+g, uu1+g+w, vv1+g+w),
                (uu0-g-w, vv0-g, uu0-g, vv1+g),     (uu1+g, vv0-g, uu1+g+w, vv1+g))):
            solids.append({
                "kind": "scaffold",
                "box": [round(wx+a0, 2), round(wy+b0, 2), 0.0,
                        round(wx+a1, 2), round(wy+b1, 2), round(top, 2)],
                "yaw_deg": round(pt["yaw"], 2), "coverage": None,
                "note": f"{tag} 외곽 비계 {si_+1}", "source": "가설계획 모사",
            })

    doc = {
        "_about": "골조 형상 — 사용자 입력",
        "_source": f"종합가설계획도 색분리 ({img.name}) — 신내역 금강펜테리움 "
                   "센트럴파크(서울 중랑구 망우동 610)",
        "_derivation": f"동 채움색 {FILL_RGB} 을 골라 연결성분으로 나누고, 성분마다 "
                       f"주축 좌표계에서 {SLICE_M}m 간격으로 썰어 폭이 "
                       f"{MERGE_TOL_M}m 안에서 같은 구간을 상자로 묶었다. 축척은 "
                       f"401동 장축을 {ANCHOR_M}m 로 두는 앵커이며 이 값은 종전 "
                       f"건축물현황도(1:2000) 판독에서 온다 — 그 오차를 물려받는다. "
                       f"tools/plan_image_to_building.py",
        "_limits": "요철을 상자로 근사하므로 바닥면적이 실제보다 약 17% 크다 "
                   "(사각형 하나로 두면 80% 컸다). 코어는 도면에서 가려낼 수 없어 "
                   "조각 가운데에 종전 규약대로 넣었다. 외곽 비계는 1m 띄운 띠의 "
                   "모사이며 실제 설치 범위가 아니다. **대지 경계는 이번에 다시 "
                   "잡지 않았고** 210x125m 를 그대로 두었다.",
        "_rotation": "연직축 회전만 쓴다. box 는 회전 전 좌표이며 중심을 축으로 "
                     "yaw_deg 만큼 돌린 것이 실형상이다.",
        "_coverage": "1.0 은 속이 찬 것, null 이면 config.SCAFFOLD_COVERAGE 를 쓴다.",
        "_units": "미터. 원점은 대지 좌하단, z 는 지면에서 위로",
        "site": {"width_m": SITE_W, "depth_m": SITE_D,
                 "note": "신내역 금강펜테리움 센트럴파크 전체 단지"},
        "storey_levels_m": levels,
        "solids": solids,
    }

    from collections import Counter
    print(f"평면 상자 {n_box}개 -> 솔리드 {len(solids)}개 "
          f"{dict(Counter(s['kind'] for s in solids))}")
    for pt in sorted(parts, key=lambda p: (p["dong"], p["part"])):
        print(f"  {pt['dong']}{'' if pt['part']==0 else '-'+'AB'[pt['part']-1]:<3} "
              f"yaw {pt['yaw']:+7.2f}°  상자 {len(pt['boxes'])}")
    if dry:
        print("\n--dry: 파일을 쓰지 않았다")
        return
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {OUT}")

    if "--verify" in sys.argv:
        _verify(img, mpp, ox, oy, levels[1] if len(levels) > 1 else levels[0])


def _verify(img: Path, mpp: float, ox: float, oy: float, z: float) -> None:
    """**최종 산출물**을 site_model 로 읽어 도면 위에 겹쳐 그린다.

    중간 계산을 그리면 안 된다 — 실제로 한 번 속았다. 생성기가 상자 중심을
    회전시키지 않아 기운 판들이 가로축을 따라 줄지어 섰는데(배열 +0.6°,
    yaw -23.6°), 검증 그림은 제 중간 좌표를 그려서 멀쩡해 보였다.
    **계산이 쓰는 것과 같은 경로로만 검증한다.**
    """
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / "src"))
    import importlib
    import site_model
    importlib.reload(site_model)
    s = site_model.build()
    slabs = [b for b in s.solids if b.kind == "slab" and abs(b.z2 - z) < 1e-6]
    im = Image.open(img).convert("RGB")
    d = ImageDraw.Draw(im)
    for b in slabs:
        d.polygon([((X - ox) / mpp, -(Y - oy) / mpp) for X, Y in b.corners_xy()],
                  outline=(220, 20, 20))
    out = img.with_name(img.stem + "_추출검증.png")
    im.save(out)
    print(f"검증 겹침 (EL {z:g}m 슬래브 {len(slabs)}장) -> {out}")


if __name__ == "__main__":
    main()
