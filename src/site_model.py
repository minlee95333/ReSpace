# -*- coding: utf-8 -*-
"""가상 현장 생성 (CLAUDE.md §5.1).

LH 아파트 건설현장 1개 공구를 100×60m 로 모사한다. BIM 을 쓰지 않고 직육면체
조합으로 만든다. 난수를 쓰지 않으므로 몇 번을 돌려도 같은 현장이 나온다.

골조는 **진행 중인 상태**다 — 코어 벽체 + 슬래브 + 외곽 비계.
위험 가중치는 자체 산정하지 않는다(§5.1). LH·국토안전관리원 지수를 입력으로 받는
구조로 두고, 실제 값은 `data/zones.json` 에서 읽는다.
"""
from pathlib import Path
import json
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
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


@dataclass(frozen=True)
class Box:
    """축정렬 직육면체. 광선투사의 차폐물이 된다.

    `coverage` 는 이 부피가 시선을 막는 비율이다.
      1.0  벽체·슬래브·적재물처럼 속이 찬 것
      <1.0 비계처럼 수직 부재의 격자라 사이로 보이는 것

    비계를 속 찬 벽으로 두면 현장 안이 통째로 안 보인다(완전 차폐 57% 로 실측).
    실제 비계는 지주·띠장 사이가 비어 있고, 그 부분 가림은 실험의 `o` 축이
    바로 다루는 대상이다. 이진 차폐가 아니라 점유율로 넘긴다.
    """
    x1: float; y1: float; z1: float
    x2: float; y2: float; z2: float
    kind: str = "solid"
    coverage: float = 1.0
    # 연직축(z) 둘레 회전각. 0 이면 축정렬이고 기존과 완전히 같다.
    #
    # **왜 필요했나.** 실제 도면의 404·405동이 사선으로 앉아 있다. 축정렬로
    # 펴서 넣었더니 가림이 실제와 다른 방향으로 계산됐다. x1..y2 는 회전 전
    # 좌표이며, 중심을 축으로 yaw_deg 만큼 돌린 것이 실제 형상이다.
    yaw_deg: float = 0.0
    # 슬래브 관통부(엘리베이터·계단실·설비 샤프트)의 평면 사각형 목록.
    # **위험구역 도출에만 쓴다.** 광선투사는 이 구멍을 통과시키지 않는다 —
    # 슬래브를 여전히 속 찬 판으로 본다. 아래층이 위층 구멍으로 보이는 효과는
    # 모델에 없으며, 이는 가림을 실제보다 크게 잡는 쪽이라 안전 판정에서
    # 보수적인 방향이다. 한계로 명시한다.
    openings: tuple = ()
    # 한 장의 판을 여러 상자로 쪼갠 경우, 그 판을 가리키는 이름.
    # **zone_derive 가 이것으로 조각을 다시 합친다** — 안 그러면 조각 사이
    # 이음매까지 "슬래브 단부" 로 잡는다(실제 단부가 아니다).
    group: str = ""

    # ── 회전 도우미 ──────────────────────────────────────────────────
    # 회전을 쓰는 쪽이 매번 삼각함수를 다시 쓰지 않도록 여기 모은다.

    @property
    def rotated(self) -> bool:
        return abs(self.yaw_deg) > 1e-9

    @property
    def center_xy(self) -> tuple:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def half_xy(self) -> tuple:
        return ((self.x2 - self.x1) / 2.0, (self.y2 - self.y1) / 2.0)

    def to_local_xy(self, x, y):
        """세계 좌표 → 상자 중심 기준 로컬 좌표. numpy 배열도 받는다."""
        cx, cy = self.center_xy
        if not self.rotated:
            return x - cx, y - cy
        import math as _m
        c, s_ = _m.cos(_m.radians(self.yaw_deg)), _m.sin(_m.radians(self.yaw_deg))
        dx, dy = x - cx, y - cy
        return dx * c + dy * s_, -dx * s_ + dy * c

    def contains_xy(self, x: float, y: float) -> bool:
        lx, ly = self.to_local_xy(x, y)
        hx, hy = self.half_xy
        return abs(lx) <= hx and abs(ly) <= hy

    def contains(self, x: float, y: float, z: float) -> bool:
        return self.z1 <= z <= self.z2 and self.contains_xy(x, y)

    def near_xy(self, x: float, y: float, d: float) -> bool:
        """상자 바깥으로 d 만큼 부풀린 영역 안인가. 비계 곁 판정에 쓴다."""
        lx, ly = self.to_local_xy(x, y)
        hx, hy = self.half_xy
        return abs(lx) <= hx + d and abs(ly) <= hy + d

    def corners_xy(self) -> list:
        """평면 네 꼭짓점(회전 반영). 그리기와 구역 도출이 쓴다."""
        cx, cy = self.center_xy
        hx, hy = self.half_xy
        pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        if not self.rotated:
            return [(cx + a, cy + b) for a, b in pts]
        import math as _m
        c, s_ = _m.cos(_m.radians(self.yaw_deg)), _m.sin(_m.radians(self.yaw_deg))
        return [(cx + a * c - b * s_, cy + a * s_ + b * c) for a, b in pts]

    def bbox_xy(self) -> tuple:
        """회전을 반영한 축정렬 외접 사각형. 거친 걸러내기에만 쓴다."""
        xs = [p[0] for p in self.corners_xy()]
        ys = [p[1] for p in self.corners_xy()]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True)
class Zone:
    """위험구역. **사용자 입력이다** — `data/zones.json` 에서 온다.

    우리는 위험을 판단하지 않는다. 어디가 위험한지는 현장이 정하고, 그 정보는
    안전관리계획서에 이미 있다. 자동 도출은 4D BIM 안전계획 연구가 확립했으며
    그 출력을 이 형식으로 받으면 된다.

    사각형과 다각형을 받는다. z 범위는 선택이며, 타설처럼 특정 층에서만
    일어나는 작업을 자를 때 쓴다.
    """
    name: str
    label: str
    weight: int
    hazard: str
    kind: str                      # rect | poly
    areas: tuple                   # rect: (x1,y1,x2,y2) / poly: ((x,y), ...)
    z_min: float = float("-inf")
    z_max: float = float("inf")
    # 출처. 도출이면 "derived:R1_slab_edge", 입력이면 서류의 어느 항목인지다.
    # 근거 없는 사각형을 못 만들게 _zones() 가 강제한다.
    source: str = ""
    rule: str = ""
    tier: str = ""

    def contains(self, x: float, y: float, z: float = None) -> bool:
        if z is not None and not (self.z_min <= z <= self.z_max):
            return False
        for a in self.areas:
            if self.kind == "rect":
                if a[0] <= x <= a[2] and a[1] <= y <= a[3]:
                    return True
            elif _point_in_poly(x, y, a):
                return True
        return False


def _point_in_poly(x: float, y: float, pts) -> bool:
    """레이 캐스팅. 다각형 구역을 받기 위한 것이다."""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xi:
                inside = not inside
    return inside


@dataclass(frozen=True)
class Camera:
    cid: str
    x: float; y: float; z: float
    mount: str          # boundary_pole / core_top / tower_crane


@dataclass
class Site:
    width: float
    depth: float
    solids: list = field(default_factory=list)
    zones: list = field(default_factory=list)
    cameras: list = field(default_factory=list)
    voxels: list = field(default_factory=list)


# ── 골조 ──────────────────────────────────────────────────────────────────

BUILDING = config.ROOT / "data" / "building.json"


def _solids(scaffold_coverage: float = None) -> list:
    """골조 직육면체. **`data/building.json` 에서 온다.**

    BIM 을 직접 읽지 않는다. 이 모델이 골조에서 필요로 하는 것은 광선을 막는
    축정렬 직육면체 목록뿐이고, IFC 를 파싱해도 얻는 것은 벽·슬래브다. 정작
    가림의 주범인 비계·동바리는 설계 BIM 에 들어 있지 않아 어차피 손으로
    넣어야 한다. 그래서 형상을 계약으로 받고, IFC·DWG·실측은 그 계약을 채우는
    어댑터 자리에 둔다.

    `coverage` 는 세 가지로 갈린다. **키가 없으면 1.0**(속이 찬 것), **명시적
    null 이면 `config.SCAFFOLD_COVERAGE`**(민감도 스윕 대상이라 파일에 고정하지
    않는다), 숫자면 그 값이다. 둘을 뭉개면 코어·슬래브까지 비계 점유율을 갖는다.
    """
    if scaffold_coverage is None:
        scaffold_coverage = config.SCAFFOLD_COVERAGE
    doc = json.loads(BUILDING.read_text(encoding="utf-8"))

    levels = [float(z) for z in doc["storey_levels_m"]]
    if levels != [float(z) for z in config.SLAB_LEVELS_M]:
        raise ValueError(
            f"{BUILDING.name} 의 storey_levels_m {levels} 가 "
            f"config.SLAB_LEVELS_M {config.SLAB_LEVELS_M} 과 다르다. "
            "복셀화가 층 높이를 config 에서 읽으므로 둘이 어긋나면 "
            "슬래브 판과 작업면이 따로 논다. 한쪽을 맞춰라.")

    s = []
    for item in doc["solids"]:
        b = item["box"]
        if "coverage" not in item:
            cov = 1.0                       # 키 없음 = 속이 찬 것
        elif item["coverage"] is None:
            cov = scaffold_coverage         # 명시적 null = 스윕 대상
        else:
            cov = float(item["coverage"])
        ops = tuple(tuple(float(v) for v in o) for o in item.get("openings", ()))
        s.append(Box(*[float(v) for v in b], item.get("kind", "solid"), cov,
                     float(item.get("yaw_deg", 0.0)), ops,
                     str(item.get("group", ""))))
    return s


# ── 위험구역 ──────────────────────────────────────────────────────────────

ZONES_JSON = config.ROOT / "data" / "zones.json"


WEIGHT_PROFILE = "weight"        # "weight"(통계) | "weight_severity_adj"(심각도 보정)


def _zones(path: Path = None, profile: str = None, solids: list = None) -> list:
    """위험구역. **두 곳에서 온다.**

      T1  `zone_derive.derive(solids)` — 골조 기하에서 규칙으로 도출한다.
          슬래브 단부·갱폼 작업면·타설면. 근거 조문이 규칙마다 붙는다.
      T2/T3  `data/zones.json` — 골조 모델에 정보가 없어 못 내는 것.
          개구부(도면 필요), 굴착면·리프트·크레인·야적장(가설계획 필요).

    **모든 구역은 `source` 를 가져야 한다.** 도출이면 규칙 이름, 입력이면 서류의
    어느 항목인지다. 없으면 raise 한다 — 근거 없는 사각형은 "그 좌표는 어디서
    나왔냐"는 질문 하나로 무너진다.

    `solids` 를 주지 않으면 T1 을 건너뛴다(단위 시험용).
    """
    import zone_derive

    prof = profile or WEIGHT_PROFILE
    items = []
    if solids is not None:
        items += zone_derive.derive(solids)

    path = Path(path or ZONES_JSON)
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        derived_names = {z["name"] for z in items}
        for z in doc["zones"]:
            if z["name"] in derived_names:
                raise ValueError(
                    f"{path.name} 의 '{z['name']}' 은 골조에서 도출되는 구역이다"
                    " (zone_derive). 손으로 찍은 좌표가 도출값을 가려 어느 쪽이"
                    " 쓰였는지 알 수 없게 되므로 둘 중 하나만 남겨라.")
            items.append(z)

    zones = []
    for z in items:
        if not z.get("source"):
            raise ValueError(
                f"위험구역 '{z['name']}' 에 source 가 없다. 어느 서류의 어느"
                " 항목에서 왔는지 적어라. data/zones.json 의 _source 참고.")
        kind = z.get("kind", "rect")
        zones.append(Zone(
            name=z["name"], label=z.get("label", z["name"]),
            weight=int(z.get(prof, z["weight"])), hazard=z.get("hazard", ""),
            kind=kind, areas=[list(a) for a in z["areas"]],
            z_min=float(z.get("z_min", -1e9)), z_max=float(z.get("z_max", 1e9)),
            source=z["source"], rule=z.get("rule", ""),
            tier=z.get("tier", "T1 골조에서 도출"),
        ))
    return zones


def zone_weights(zones: list = None) -> dict:
    """이름 → 가중치. schedule 이 시간대별 가중치를 만들 때 쓴다."""
    return {z.name: z.weight for z in (zones if zones is not None else _zones())}


# ── 카메라 후보 ───────────────────────────────────────────────────────────

def _cameras(spacing_m: float = None, solids: list = None) -> list:
    """설치 가능한 자리에 후보를 **격자로 깐다** (2026-08-20).

    종전에는 24개를 손으로 찍었다. 그러면 재배치 처방이 그 24곳 안에서만
    나와 *"(37.4m, 22.8m, z 8m) 에 달아라"* 같은 답을 못 한다. 현장에 폴을
    세울 수 있는 자리가 딱 24곳일 리 없으니 실무적으로 약했다.

    연속 최적화(좌표를 실수 변수로 두고 경사하강) 대신 **후보를 촘촘히 까는**
    쪽을 골랐다. 구조를 바꾸지 않고, 탐욕의 (1-1/e) 보장이 그대로 유지되며,
    "후보 안에서 불가능" 판정이 실제 물리적 한계에 가까워진다.

    설치 가능 영역 넷:
      경계 폴    현장 둘레. 높이 6m
      코어 상부  코어 슬래브 위. 높이 13m
      비계       외곽 비계 상단 난간. 높이 8·12m — 실제로 카메라를 다는 자리다
      타워크레인 중앙 마스트 주변. 높이 25m

    간격은 `config.CAMERA_SPACING_M`. 좁힐수록 임의 위치에 가까워지지만
    광선투사가 후보 수에 비례해 늘어난다.
    """
    sp = spacing_m or config.CAMERA_SPACING_M
    W, D = config.SITE_WIDTH_M, config.SITE_DEPTH_M
    if solids is None:
        solids = _solids()
    cams, seen = [], set()

    def add(x, y, z, mount, tag):
        key = (round(x, 1), round(y, 1), round(z, 1))
        if key in seen:
            return
        seen.add(key)
        cams.append(Camera(f"c_{tag}{len(cams):03d}", x, y, z, mount))

    # ① 경계 폴 — 네 변을 spacing 간격으로
    n_x = max(2, int(round(W / sp)))
    n_y = max(2, int(round(D / sp)))
    for i in range(n_x):
        x = W * (i + 0.5) / n_x
        add(x, 1.0, 6.0, "boundary_pole", "b")
        add(x, D - 1.0, 6.0, "boundary_pole", "b")
    for j in range(n_y):
        y = D * (j + 0.5) / n_y
        add(1.0, y, 6.0, "boundary_pole", "b")
        add(W - 1.0, y, 6.0, "boundary_pole", "b")

    # ② 코어 상부 — 코어 윗면 둘레
    #
    # **골조에서 유도한다** (2026-08-27). 종전에는 코어를 (30,30)·(70,30) 으로,
    # 비계를 (16,12)-(84,48) 로 이 함수 안에 박아 두었다. 현장을 실제 도면으로
    # 바꾸는 순간 카메라 후보가 건물과 따로 놀았다. 형상이 바뀌면 설치 가능
    # 자리도 따라 바뀌어야 한다 — 그것이 이 도구가 받는 입력의 성질이다.
    for b in [x for x in solids if x.kind == "core"]:
        # 꼭짓점 넷과 변 중점 넷. **회전을 반영한다** — 사선으로 앉은 동의
        # 코어 위에 축정렬로 점을 찍으면 카메라가 허공에 뜬다.
        cs = b.corners_xy()
        mids = [((cs[i][0] + cs[(i + 1) % 4][0]) / 2,
                 (cs[i][1] + cs[(i + 1) % 4][1]) / 2) for i in range(4)]
        for x, y in cs + mids:
            add(x, y, b.z2 - 1.0, "core_top", "k")

    # ③ 비계 상단 난간 — 실제로 카메라를 다는 자리다
    sc = [x for x in solids if x.kind == "scaffold"]
    if sc:
        # 회전을 반영한 외접 사각형을 쓴다. 동이 여럿이면 전체를 감싼다.
        bb = [x.bbox_xy() for x in sc]
        ox1 = min(b[0] for b in bb); oy1 = min(b[1] for b in bb)
        ox2 = max(b[2] for b in bb); oy2 = max(b[3] for b in bb)
        top = max(x.z2 for x in sc)
        nx = max(2, int(round((ox2 - ox1) / sp)))
        ny = max(2, int(round((oy2 - oy1) / sp)))
        # 비계 난간은 층마다 있다. 슬래브 레벨 중 비계 안에 드는 것을 쓴다.
        rails = [z for z in config.SLAB_LEVELS_M if 2.0 < z < top - 1.0] or [top / 2]
        for z in rails:
            for i in range(nx):
                x = ox1 + (ox2 - ox1) * (i + 0.5) / nx
                add(x, oy1, z, "scaffold_rail", "s")
                add(x, oy2, z, "scaffold_rail", "s")
            for j in range(ny):
                y = oy1 + (oy2 - oy1) * (j + 0.5) / ny
                add(ox1, y, z, "scaffold_rail", "s")
                add(ox2, y, z, "scaffold_rail", "s")

    # ④ 타워크레인 마스트 주변 — 마스트 좌표는 zones.json 의 인양반경과 같은 점이다
    mx, my = config.TOWER_CRANE_MAST_XY
    for dx in (-8.0, 0.0, 8.0):
        for dy in (-8.0, 0.0, 8.0):
            if dx == 0.0 and dy == 0.0:
                continue
            x, y = mx + dx, my + dy
            if 0.0 <= x <= W and 0.0 <= y <= D:
                add(x, y, config.TOWER_CRANE_CAM_Z_M, "tower_crane", "t")

    return cams


# ── 복셀 ──────────────────────────────────────────────────────────────────

def _occupiable(x: float, y: float, z: float, solids: list) -> bool:
    """이 자리에 사람이 있을 수 있는가.

    CCTV 는 공중도 보지만 **검출 대상은 사람**이다. 부피 전체를 분모로 삼으면
    아무도 못 가는 허공이 커버리지를 희석한다. 그래서 복셀마다 이 판정을 달고
    지표는 여기 해당하는 것만으로 낸다. 시각화는 전부 그린다.

    사람이 있을 수 있는 자리는 둘이다.
      ① 바닥(지면·슬래브) 위 작업 높이대
      ② 비계·갱폼 작업발판 곁 — 건설현장에서 추락 위험이 큰 자리가 여기다
    """
    lo, hi = config.OCCUPIABLE_BAND_M
    for floor_z in config.SLAB_LEVELS_M:
        if floor_z + lo <= z <= floor_z + hi:
            if floor_z == 0.0:
                return True                     # 지면은 현장 전역
            for b in solids:                    # 상부층은 슬래브 위만
                if (b.kind == "slab" and abs(b.z2 - floor_z) < 1e-6
                        and b.contains_xy(x, y)):
                    return True

    d = config.OCCUPIABLE_NEAR_SCAFFOLD_M
    for b in solids:                            # 비계 작업발판 곁
        if b.kind != "scaffold":
            continue
        if b.near_xy(x, y, d) and b.z1 <= z <= b.z2:
            return True
    return False


def _level_of(z: float) -> int:
    """이 높이가 몇 층대인가. 2D 모드의 층 선택에 쓴다."""
    lvl = 0
    for i, fz in enumerate(config.SLAB_LEVELS_M):
        if z >= fz:
            lvl = i
    return lvl


def _voxels(solids: list, zones: list) -> list:
    """현장을 복셀로 자른다.

    `config.VOXEL_MODE` 가
      "volume"      부피 전체를 큐브로 (CCTV 는 공중도 본다)
      "work_plane"  층별 작업면만 (가볍다)

    골조 솔리드 안은 사람이 들어갈 수 없으므로 아예 만들지 않는다.
    """
    step = config.VOXEL_M
    nx = int(config.SITE_WIDTH_M / step)
    ny = int(config.SITE_DEPTH_M / step)
    out = []

    if config.VOXEL_MODE == "volume":
        zs = [(k + 0.5) * step for k in range(int(config.VOXEL_Z_MAX_M / step))]
    else:
        zs = [fz + config.WORK_PLANE_OFFSET_M for fz in config.SLAB_LEVELS_M]

    slabs = [b for b in solids if b.kind == "slab"]

    for zi, z in enumerate(zs):
        for j in range(ny):
            for i in range(nx):
                x, y = (i + 0.5) * step, (j + 0.5) * step

                if any(s.kind in ("core", "slab", "stack")
                       and s.contains(x, y, z) for s in solids):
                    continue                    # 골조 안 — 들어갈 수 없다

                if config.VOXEL_MODE == "volume":
                    occ = _occupiable(x, y, z, solids)
                    lvl = _level_of(z)
                else:
                    if zi > 0:
                        floor_z = config.SLAB_LEVELS_M[zi]
                        if not any(b.contains_xy(x, y)
                                   and abs(b.z2 - floor_z) < 1e-6 for b in slabs):
                            continue
                    occ, lvl = True, zi

                w = config.RISK_WEIGHT_DEFAULT
                names = []
                for zn in zones:
                    if zn.contains(x, y, z):
                        w = max(w, zn.weight)
                        names.append(zn.name)

                out.append({"id": f"v_{len(out):04d}", "x": x, "y": y, "z": z,
                            "level": lvl,
                            "floor_z": config.SLAB_LEVELS_M[
                                min(lvl, len(config.SLAB_LEVELS_M) - 1)],
                            "occupiable": occ, "w": w, "zones": names})
    return out



def build(scaffold_coverage: float = None, weight_profile: str = None) -> Site:
    solids = _solids(scaffold_coverage)
    zones = _zones(profile=weight_profile, solids=solids)
    return Site(
        width=config.SITE_WIDTH_M,
        depth=config.SITE_DEPTH_M,
        solids=solids,
        zones=zones,
        cameras=_cameras(solids=solids),
        voxels=_voxels(solids, zones),
    )


if __name__ == "__main__":
    s = build()
    import collections
    wc = collections.Counter(v["w"] for v in s.voxels if v["occupiable"])
    print(f"현장 {s.width:.0f}×{s.depth:.0f}m · 복셀 {config.VOXEL_M:.0f}m 격자")
    print(f"  솔리드 {len(s.solids)} · 위험구역 {len(s.zones)} · 카메라 후보 {len(s.cameras)}")
    occ = [v for v in s.voxels if v["occupiable"]]
    print(f"  복셀 {len(s.voxels)}개 (골조 내부 제외) · 그중 사람이 있을 수 있는 "
          f"자리 {len(occ)}개 ({len(occ)/len(s.voxels)*100:.1f}%)")
    print("  가중치 분포:", dict(sorted(wc.items())))
    print(f"  가중치 총합 Σw = {sum(v['w'] for v in s.voxels if v['occupiable'])}"
          f"  (occupiable 만)")
