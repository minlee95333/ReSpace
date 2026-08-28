# -*- coding: utf-8 -*-
"""위험구역을 골조 기하에서 도출한다 (2026-08-21).

**왜 필요한가.** 종전에는 위험구역이 `data/zones.json` 의 손으로 찍은 사각형뿐이었다.
"여기가 거푸집 설치공간이라 우선 봐야 한다"는 정보가 모델 어디에도 없고, 서류에서
오지도 않았다. 좌표만 있고 근거가 없으면 심사에서 "그 사각형은 어디서 나왔냐"는
질문 하나로 무너진다.

**세 층으로 나눈다.**

  T1 도출 가능   골조 기하 + 규칙으로 나온다. 이 파일이 하는 일이다
  T2 도면 필요   골조 모델에 정보가 없어 못 낸다 (개구부·슬래브 관통부)
  T3 가설계획 필요  골조가 아니라 장비·야적 배치에서 온다 (리프트·크레인·야적장·굴착)

T1 은 자동, T2·T3 는 `zones.json` 으로 받는다. **어느 쪽이든 `source` 를 반드시
남긴다** — 도출이면 규칙 이름, 입력이면 서류의 어느 항목인지.

**선행연구.** 공정·모델에서 위험구역을 규칙으로 도출하는 것은
Zhang·Teizer·Pradhananga·Eastman, *Automation in Construction* 29 (2013) 이
확립했다. 새로 주장하지 않는다. 우리 몫은 도출이 아니라 **그 구역을 카메라가
실제로 검출할 수 있는지 판정하는 것**이다.

**규칙의 근거는 안전기준이지 우리 판단이 아니다.** 각 규칙에 근거 조문을 적었다.
가중치는 `docs/reference/위험가중치_근거.md` 의 재해유형 → 가중치 표를 따른다.
"""
from pathlib import Path
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# 재해유형 → 가중치. docs/reference/위험가중치_근거.md §2 의 유도 결과다.
HAZARD_WEIGHT = {
    "떨어짐": (10, 10), "물체에 맞음": (4, 5), "부딪힘": (3, 3),
    "끼임": (3, 3), "깔림·뒤집힘": (2, 3), "무너짐": (2, 9),
}

# 작업면 밴드 폭. 단부·개구부에서 이 거리 안이 추락 위험구역이다.
# 「산업안전보건기준에 관한 규칙」 제43조(개구부 등의 방호 조치)가 안전난간·
# 덮개를 요구하는 대상이 단부이며, 폭 수치는 규칙에 없어 잠정값이다.
EDGE_BAND_M = 2.0

# 작업자가 서는 높이대. 바닥에서 이만큼 위까지가 사람이 있는 공간이다.
WORK_BAND_M = 2.5


def _ring(x1, y1, x2, y2, t):
    """사각형 안쪽 두께 t 의 띠를 사각형 4개로 낸다."""
    return [[x1, y1, x2, y1 + t], [x1, y2 - t, x2, y2],
            [x1, y1, x1 + t, y2], [x2 - t, y1, x2, y2]]


class _Merged:
    """같은 group 의 상자들을 로컬 좌표에서 합친 하나의 상자.

    조각들은 yaw 가 같고 주축을 따라 이어 붙어 있으므로, 로컬 좌표의 외접
    상자가 곧 그 판의 바깥 윤곽이다. 요철의 홈은 이 안에 들어가므로 단부 띠가
    홈까지 덮는다 — 홈 깊이만큼 보수적이며, 이음매를 단부로 잡는 것보다 낫다.
    """
    __slots__ = ("x1", "y1", "z1", "x2", "y2", "z2", "kind",
                 "coverage", "yaw_deg", "openings")

    def __init__(self, boxes):
        import math
        b0 = boxes[0]
        self.kind, self.coverage, self.yaw_deg = b0.kind, b0.coverage, b0.yaw_deg
        self.z1 = min(b.z1 for b in boxes); self.z2 = max(b.z2 for b in boxes)
        self.openings = getattr(b0, "openings", ())
        if not self.rotated:
            self.x1 = min(b.x1 for b in boxes); self.y1 = min(b.y1 for b in boxes)
            self.x2 = max(b.x2 for b in boxes); self.y2 = max(b.y2 for b in boxes)
            return
        # 회전 상자 — 로컬 좌표에서 합치고 중심을 다시 잡는다
        r = math.radians(self.yaw_deg); c, s_ = math.cos(r), math.sin(r)
        us, vs = [], []
        for b in boxes:
            cx, cy = b.center_xy; hx, hy = b.half_xy
            for sx in (-1, 1):
                for sy in (-1, 1):
                    us.append(cx + sx * hx); vs.append(cy + sy * hy)
        # 조각들은 회전 전 좌표를 공유하므로 그대로 외접시키면 된다
        self.x1, self.x2 = min(us), max(us)
        self.y1, self.y2 = min(vs), max(vs)

    @property
    def rotated(self):
        return abs(self.yaw_deg) > 1e-9

    @property
    def center_xy(self):
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def half_xy(self):
        return ((self.x2 - self.x1) / 2, (self.y2 - self.y1) / 2)

    def corners_xy(self):
        """평면 네 꼭짓점(회전 반영). site_model.Box 와 같은 규약이어야 한다 —
        갈리면 타설면 다각형이 실제와 다른 방향으로 그려진다."""
        import math
        cx, cy = self.center_xy
        hx, hy = self.half_xy
        pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        if not self.rotated:
            return [(cx + a, cy + b) for a, b in pts]
        r = math.radians(self.yaw_deg)
        c, s_ = math.cos(r), math.sin(r)
        return [(cx + a * c - b * s_, cy + a * s_ + b * c) for a, b in pts]


def _merge_groups(slabs: list) -> list:
    """`group` 이 같은 상자들을 한 장으로 합친다. group 이 없으면 그대로 둔다."""
    by, loose = {}, []
    for b in slabs:
        g = getattr(b, "group", None)
        if g:
            by.setdefault(g, []).append(b)
        else:
            loose.append(b)
    return loose + [_Merged(v) if len(v) > 1 else v[0] for v in by.values()]


def _box_ring(b, t):
    """상자 안쪽 두께 t 의 띠. **회전을 반영한다.**

    yaw 가 0 이면 종전과 똑같이 사각형 4개(kind="rect")를 낸다. 회전한
    상자는 사각형으로 표현할 수 없으므로 로컬 좌표에서 띠를 만들고 꼭짓점을
    세계 좌표로 돌려 다각형 4개(kind="poly")를 낸다. Zone 이 둘 다 받는다.

    반환: (kind, areas)
    """
    if not getattr(b, "rotated", False):
        return "rect", _ring(b.x1, b.y1, b.x2, b.y2, t)
    import math
    cx, cy = b.center_xy
    hx, hy = b.half_xy
    c, s_ = math.cos(math.radians(b.yaw_deg)), math.sin(math.radians(b.yaw_deg))

    def w(lx, ly):
        return [round(cx + lx * c - ly * s_, 3), round(cy + lx * s_ + ly * c, 3)]

    rects = [(-hx, -hy, hx, -hy + t), (-hx, hy - t, hx, hy),
             (-hx, -hy, -hx + t, hy), (hx - t, -hy, hx, hy)]
    return "poly", [[w(a, d), w(e, d), w(e, f), w(a, f)]
                    for a, d, e, f in rects]


def _box_face(b):
    """상자 상면 전체. 회전하면 다각형 하나, 아니면 사각형 하나."""
    if not getattr(b, "rotated", False):
        return "rect", [[b.x1, b.y1, b.x2, b.y2]]
    return "poly", [[[round(x, 3), round(y, 3)] for x, y in b.corners_xy()]]


def _outward_ring(x1, y1, x2, y2, t):
    """사각형 **바깥쪽** 두께 t 의 띠. 개구부 주변이 위험구역이다.

    `_ring` 은 안쪽 띠를 낸다(슬래브 단부용). 구멍은 반대다 — 사람은 구멍
    안이 아니라 구멍 가장자리에 선다.
    """
    return _ring(x1 - t, y1 - t, x2 + t, y2 + t, t)


def _slabs(solids):
    return sorted((b for b in solids if b.kind == "slab"), key=lambda b: b.z2)


def derive(solids: list, top_slab_only: bool = True) -> list:
    """T1 구역을 낸다. 반환 형식은 `data/zones.json` 의 zones 항목과 같다.

    **한 구역이 여러 층에 걸치면 같은 `name` 으로 여러 항목을 낸다.** 층마다
    이름을 나누면 공정표(`schedule.json`)가 층 이름을 알아야 하고, 층이 늘 때마다
    공정표를 고쳐야 한다. 이름은 구역 종류로 두고 층은 `z_min`/`z_max` 로 가른다.
    """
    out = []
    slabs = _slabs(solids)
    # **세 규칙 모두 판 한 장 단위다.** 한 장이 여러 상자로 쪼개져 있으면
    # 합쳐서 본다 - 조각마다 돌리면 이음매가 단부가 되고, 같은 구멍이 조각
    # 수만큼 중복된다(실측: 단부 236개·개구부 236개가 생겼다).
    plates = _merge_groups(slabs)
    scaffolds = [b for b in solids if b.kind == "scaffold"]

    # ── R1 슬래브 단부 ────────────────────────────────────────────────
    # 슬래브 상면 가장자리에서 EDGE_BAND_M 안쪽까지. 떨어짐.
    # 근거: 산업안전보건기준에 관한 규칙 제43조 — 작업발판 끝·개구부에
    #       안전난간·덮개 등 방호 조치 의무. 그 대상 자리가 곧 위험구역이다.
    # **한 판이 여러 상자로 쪼개져 있으면 합쳐서 본다** (2026-08-27).
    #
    # 도면의 요철을 살리려고 슬래브 한 장을 여러 상자로 나눈 뒤, 상자마다
    # 테두리를 두르니 **조각 사이 이음매까지 단부가 됐다.** 실제 단부가 아니다
    # (236개가 생겼다). building.json 이 `group` 으로 한 장임을 밝히면 그
    # 바깥 테두리만 단부로 본다. group 이 없으면 종전대로 상자마다 두른다.
    for b in plates:
        out.append({
            "name": "slab_edge",
            "label": f"슬래브 단부 (EL {b.z2:g}m)",
            "hazard": "떨어짐", "kind": _box_ring(b, EDGE_BAND_M)[0],
            "areas": _box_ring(b, EDGE_BAND_M)[1],
            "z_min": round(b.z2, 3), "z_max": round(b.z2 + WORK_BAND_M, 3),
            "source": "derived:R1_slab_edge",
            "rule": f"슬래브 상면 가장자리 {EDGE_BAND_M}m 밴드. "
                    "산업안전보건기준에 관한 규칙 제43조 방호 대상",
        })

    # ── R2 갱폼·거푸집 작업면 ────────────────────────────────────────
    # 외곽 비계 안쪽 밴드. 외벽 거푸집을 다루는 자리다. 떨어짐.
    # 근거: 같은 규칙 제43조 + 갱폼이 비계 라인에 붙어 오르내린다는 시공 사실.
    if scaffolds:
        x1 = min(b.x1 for b in scaffolds); y1 = min(b.y1 for b in scaffolds)
        x2 = max(b.x2 for b in scaffolds); y2 = max(b.y2 for b in scaffolds)
        t = min(b.x2 - b.x1 for b in scaffolds if b.x2 - b.x1 < (x2 - x1) / 2)
        ix1, iy1, ix2, iy2 = x1 + t, y1 + t, x2 - t, y2 - t
        for b in plates:
            out.append({
                "name": "gangform_workface",
                "label": f"갱폼 작업면 (EL {b.z2:g}m)",
                "hazard": "떨어짐", "kind": "rect",
                "areas": _ring(ix1, iy1, ix2, iy2, EDGE_BAND_M),
                "z_min": round(b.z2, 3), "z_max": round(b.z2 + WORK_BAND_M, 3),
                "source": "derived:R2_gangform",
                "rule": f"외곽 비계 안쪽 {EDGE_BAND_M}m 밴드 × 각 층 작업면",
            })

    # ── R3 타설·거푸집 설치면 ────────────────────────────────────────
    # 최상층 슬래브 상면 전체. 거푸집·동바리를 세우고 콘크리트를 붓는 자리다.
    # **어느 층인지는 기하가 아니라 공정표가 정한다** — data/schedule.json 이
    # 그 시간대를 켠다. 기하는 "어디"만 답하고 "언제"는 공정이 답한다.
    # 근거: 같은 규칙 제334조(콘크리트 타설 작업) 거푸집·동바리 붕괴 방지.
    if plates:
        # **최상층의 판 전부**다. 종전에는 `slabs[-1:]` — 목록의 마지막 상자
        # 하나였다. 판 하나가 상자 하나이던 시절에는 그것이 곧 최상층 한 동의
        # 판이었지만, 도면의 요철을 살리며 판을 여러 상자로 쪼갠 뒤로는 조각
        # 하나만 잡혀 구역이 1,280셀에서 10셀로 줄었다(2026-08-27 실측).
        # 높이로 고른다 — 목록 순서에 기대지 않는다.
        zmax = max(b.z2 for b in plates)
        targets = [b for b in plates if abs(b.z2 - zmax) < 1e-6]                   if top_slab_only else plates
        for b in targets:
            out.append({
                "name": "concrete_pour",
                "label": f"타설·거푸집 설치면 (EL {b.z2:g}m)",
                "hazard": "무너짐", "kind": _box_face(b)[0],
                "areas": _box_face(b)[1],
                "z_min": round(b.z2, 3), "z_max": round(b.z2 + WORK_BAND_M, 3),
                "source": "derived:R3_pour_deck",
                "rule": "최상층 슬래브 상면 전체. 층 선택은 공정표(schedule.json)가 한다. "
                        "산업안전보건기준에 관한 규칙 제334조",
            })

    # ── R4 슬래브 개구부(관통부) 주변 ────────────────────────────────
    # 슬래브를 뚫는 구멍 가장자리에서 EDGE_BAND_M 바깥까지. 떨어짐.
    # 근거: R1 과 같은 조문이다 — 산업안전보건기준에 관한 규칙 제43조가
    #       "작업발판 끝·**개구부**" 를 한 조문에서 같이 방호 대상으로 든다.
    #       R1 이 판의 바깥 테두리를, R4 가 구멍의 테두리를 맡는다.
    # **구멍 좌표는 도출이 아니라 입력이다**(T2). building.json 이 주지 않으면
    #       이 규칙은 아무것도 내지 않는다 — 없는 구멍을 지어내지 않는다.
    for b in plates:
        for k, op in enumerate(getattr(b, "openings", ()) or ()):
            ox1, oy1, ox2, oy2 = op
            out.append({
                "name": "opening_perimeter",
                "label": f"개구부 주변 (EL {b.z2:g}m)",
                "hazard": "떨어짐", "kind": "rect",
                "areas": _outward_ring(ox1, oy1, ox2, oy2, EDGE_BAND_M),
                "z_min": round(b.z2, 3), "z_max": round(b.z2 + WORK_BAND_M, 3),
                "source": "derived:R4_opening",
                "rule": f"슬래브 관통부 바깥 {EDGE_BAND_M}m 밴드. "
                        "산업안전보건기준에 관한 규칙 제43조 방호 대상. "
                        "구멍 좌표는 building.json 의 도면 입력",
            })

    for z in out:
        st, sv = HAZARD_WEIGHT[z["hazard"]]
        z["weight"], z["weight_severity_adj"] = st, sv
    return out


# 골조 기하로는 낼 수 없는 것들. 왜 못 내는지 적어둔다 — 심사 답변이 된다.
#
# `opening_perimeter` 는 2026-08-21 여기서 빠졌다. 구멍 좌표가 building.json
# 으로 들어오면서 R4 가 도출한다. **구멍 자체는 여전히 도출이 아니라 입력이다**
# — 도면이나 IFC(IfcRelVoidsElement)가 준다. 규칙이 하는 일은 그 구멍에서
# 위험 밴드를 만드는 것뿐이다.
NOT_DERIVABLE = {
    "excavation_face": ("T3 가설계획 필요", "굴착 범위·심도는 골조가 아니라 흙막이 계획에서 온다"),
    "lift_landing":    ("T3 가설계획 필요", "건설용 리프트 설치 위치는 가설계획서 소관이다"),
    "tower_crane_radius": ("T3 가설계획 필요", "마스트 위치와 지브 길이가 있어야 반경이 정해진다"),
    "material_yard":   ("T3 가설계획 필요", "야적 위치는 현장 운영이 정하고 공정에 따라 옮긴다"),
}


def main():
    import site_model
    solids = site_model._solids()
    d = derive(solids)
    print(f"골조에서 도출한 위험구역 {len(d)}개\n")
    for z in d:
        print(f"  {z['label']:<28} w={z['weight']:>2} {z['hazard']:<8} "
              f"영역{len(z['areas'])} z {z['z_min']}~{z['z_max']}")
        print(f"      {z['rule']}")
    print(f"\n골조로 낼 수 없는 것 {len(NOT_DERIVABLE)}개")
    for k, (tier, why) in NOT_DERIVABLE.items():
        print(f"  {k:<22} [{tier}] {why}")


if __name__ == "__main__":
    main()
