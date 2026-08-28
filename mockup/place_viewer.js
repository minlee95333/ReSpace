/* 커버리지 뷰어 — 2D / 2.5D / 3D
 *
 * 세 모드를 따로 만들지 않는다. **투영기 하나에 프리셋 셋**을 둔다.
 *   2D    수직 내려보기(pitch 90°) · 정사영 · 층 하나만
 *   2.5D  아이소메트릭(yaw 45° / pitch 30°) · 정사영 · 층을 쌓아 본다
 *   3D    자유 회전 · 원근 · 드래그로 궤도, 휠로 줌
 *
 * 외부 라이브러리를 쓰지 않는다. 캔버스에 직접 그린다 — 복셀이 2천 개를 넘어
 * SVG 노드로 두면 회전할 때 버벅인다.
 *
 * 깊이 정렬은 화가 알고리즘이다. 면이 축정렬 사각형뿐이라 이걸로 충분하다.
 */
(function (global) {
  'use strict';

  const DEG = Math.PI / 180;

  /* 모드가 하나다 — 자유 회전 (2026-08-22).
   *
   * 종전에는 '2d'(수직 내려보기) · '2.5d'(고정 아이소메트릭) · '3d' 셋이었다.
   * '2d' 는 평면 탭이 index.html 의 Plan 클래스로 옮겨가면서 아무도 안 쓰게 됐고,
   * '2.5d' 는 orbit:false 라 **조작이 안 되는데 탭 이름은 "3D 커버리지"** 여서
   * 쓰는 사람이 고장으로 받아들였다.
   *
   * 2.5D 의 명분은 "시점이 고정이라 늘 같은 그림" 이었는데, 3D 도 시작 각도가
   * 고정이고 시점 초기화 버튼이면 같은 그림이 나온다. 정사영의 크기 비교 이점도
   * 이 화면에서는 쓰이지 않는다 — 색으로 검출확률을 읽지 복셀 크기를 재지 않는다.
   *
   * zx = 수직 과장. **부피 복셀(큐브)에서는 1 에 가깝게 둔다.** 큐브가 이미 실제
   * 높이를 차지하고 있어서 늘리면 14m 현장이 45m 로 보인다. 층별 판(work_plane)
   * 데이터일 때만 층이 뭉쳐 과장이 필요하다 — _isPlanar() 가 그것을 본다.
   */
  const PRESETS = {
    '3d': { yaw: 35, pitch: 25, persp: true, orbit: true, zx: 1.0 },
  };
  const DEFAULT_MODE = '3d';

  /* 검출확률 램프. **theme.js 가 정본이다** (2026-08-27).
   *
   * 여기 있던 적→황→녹은 적록색약 검증에서 미달↔통과 ΔE 4.1 로 떨어져
   * 교체된 램프다(tokens.css 머리말). 팀원 갈래에서 이 파일을 가져오면서
   * 그 옛 램프가 따라 들어왔다. 색을 두 곳에 적으면 하나만 고쳤을 때
   * 조용히 어긋나므로 정본에 위임한다. theme.js 가 없을 때만 옛 값으로
   * 버틴다 - 화면이 아예 안 뜨는 것보다는 낫다. */
  function heat(p) {
    if (typeof Theme !== 'undefined' && Theme.heat) return Theme.heat(p);
    const t = p <= .5 ? p / .5 : (p - .5) / .5;
    const a = p <= .5 ? [166, 42, 42] : [196, 145, 40];
    const b = p <= .5 ? [196, 145, 40] : [30, 122, 70];
    return a.map((v, i) => Math.round(v + (b[i] - v) * t));
  }

  function rgba(c, alpha) {
    return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
  }

  class Viewer {
    constructor(canvas, data, opts) {
      this.cv = canvas;
      this.ctx = canvas.getContext('2d');
      this.d = data;
      this.opts = Object.assign({ mode: DEFAULT_MODE, key: 'P_total_empirical',
                                  showCams: true, showSolids: true }, opts || {});
      this.cam = Object.assign({}, PRESETS[this.opts.mode]);
      if (this._isPlanar()) this.cam.zx *= 2.8;
      this.zoom = 1;
      this._bindOrbit();
      this.resize();
    }

    /* 시점을 프리셋 기준각으로 되돌린다.
     * 종전 setMode 자리다 — 모드가 하나뿐이라 "다른 모드로 바꾼다" 가 아니라
     * "보던 각도를 버리고 처음으로 돌아간다" 가 됐다. 스크린샷을 늘 같은 각도로
     * 남기려면 이것을 쓴다. */
    resetView() {
      this.cam = Object.assign({}, PRESETS[DEFAULT_MODE]);
      if (this._isPlanar()) this.cam.zx *= 2.8;   // 판 데이터는 층이 뭉친다
      this.zoom = 1;
      this.draw();
    }

    /* 데이터가 층별 판인가(work_plane), 부피 큐브인가(volume).
     * 서로 다른 수직 과장이 필요해 한 번 재둔다. */
    _isPlanar() {
      if (this._planar === undefined) {
        const zs = new Set(this.d.voxels.map(v => Math.round(v.z * 10)));
        this._planar = zs.size <= 4;
      }
      return this._planar;
    }

    /* 표시 해상도(LOD).
     *
     * 격자를 1m 로 내리면 복셀이 78,816 개다. 회전 모드는 복셀마다 3면을 그리고
     * 깊이 정렬까지 하므로 10만 패스가 되어 드래그가 끊긴다. **계산은 1m 그대로
     * 두고 표시만 묶는다** — stride 큐브 하나로 평균한다.
     *
     * 2D 평면은 묶지 않는다. 층 하나만 판으로 그려 부담이 적고, 애초에 격자를
     * 1m 로 내린 이유가 평면상의 분해능이기 때문이다.
     *
     * stride 를 지정하지 않으면 예산(renderBudget) 안에 들어올 때까지 올린다.
     * 데이터가 2m 면 stride 1 에서 이미 예산 안이라 종전과 동일하게 그려진다.
     */
    _drawSet() {
      const d = this.d, s0 = d.site.voxel_m;

      // z 단면 — 한 겹만 그린다 (2026-08-22). 평면이 z 1m 단면을 보여 주는데
      // 3D 는 부피 전부라, 같은 자리를 두 화면에서 견줄 수 없었다.
      // 한 겹은 수천 개라 묶을 이유가 없다 — 격자 그대로 그린다.
      const zk = this.opts.zSlice;
      if (zk !== null && zk !== undefined) {
        return { voxels: this._sliceAt(zk), size: s0, stride: 1, slice: zk };
      }

      const budget = this.opts.renderBudget || 6000;
      let stride = this.opts.renderStride;
      if (!stride) {
        stride = 1;
        while (stride < 8 && this._lodAt(stride).length > budget) stride++;
      }
      // 돌리는 동안에는 한 단계 더 굵게 그린다. 손을 떼면 원래대로 돌아온다.
      // 프레임당 폴리곤이 1/3 로 줄어 드래그가 끊기지 않는다.
      if (this._dragging && stride < 8) stride++;

      // 정밀 표시 — **손을 뗀 뒤에만** 격자 그대로 그린다 (2026-08-22).
      // 1m 한 프레임이 약 0.8초다(82,440개, 실측). 돌리는 동안 이걸 쓰면
      // 초당 한 장을 겨우 그려 회전이 불가능하므로, 돌릴 때는 예산대로 굵게
      // 두고 멈춘 뒤 한 번만 정밀하게 다시 그린다.
      if (this.opts.fine && !this._dragging) stride = 1;
      return { voxels: this._lodAt(stride), size: s0 * stride, stride };
    }

    /* stride 큐브로 묶은 복셀 배열. 한 번 만들면 재사용한다.
     *
     * 색(P)은 **occupiable 멤버만으로 평균한다.** 블록 안에 허공이 섞여 있을 때
     * 그것까지 넣어 평균하면 사람이 설 수 있는 자리의 검출확률이 허공으로
     * 희석된다 — 지표의 분모가 occupiable 뿐인 것과 같은 이유다.
     * onlyOccupiable 을 꺼서 허공까지 볼 때는 전체 평균을 쓴다.
     *
     * 가중치는 최댓값을 잇는다(구역 판정과 같은 규칙). 개수 n 은 툴팁용이다.
     */
    /* z 한 겹만 골라낸다. 겹마다 한 번 만들어 재사용한다. */
    _sliceAt(k) {
      this._slices = this._slices || {};
      if (this._slices[k]) return this._slices[k];
      const s0 = this.d.site.voxel_m;
      return (this._slices[k] = this.d.voxels.filter(
        v => Math.round((v.z - s0 / 2) / s0) === k));
    }

    _lodAt(stride) {
      this._lod = this._lod || {};
      if (this._lod[stride]) return this._lod[stride];
      const d = this.d, s0 = d.site.voxel_m;
      if (stride === 1) return (this._lod[1] = d.voxels);

      const g = s0 * stride;
      // P_total_live 는 사용자가 배치할 때마다 다시 계산되는 값이다.
      // 여기 넣는 것은 **평균**되는 값이다. 가중치(w)와 관측 대수(vis)는
      // 세는 값이라 평균하면 뜻이 흐려진다 — 아래에서 최댓값으로 잇는다.
      const KEYS = ['P_total_geometric', 'P_total_assumed', 'P_total_empirical',
                    'P_total_live'];
      const cells = new Map();
      d.voxels.forEach(v => {
        const k = Math.floor(v.x / g) + '_' + Math.floor(v.y / g) + '_'
                + Math.floor(v.z / g);
        let c = cells.get(k);
        if (!c) {
          c = { x: 0, y: 0, z: 0, n: 0, w: 0, vis: 0, occ: false, level: v.level,
                so: {}, co: {}, sa: {}, ca: {} };
          cells.set(k, c);
        }
        c.x += v.x; c.y += v.y; c.z += v.z; c.n++;
        if (v.w > c.w) c.w = v.w;
        if ((v.vis || 0) > c.vis) c.vis = v.vis;
        const live = v.occupiable !== false;
        if (live) c.occ = true;
        KEYS.forEach(kk => {
          const val = v[kk];
          if (val === undefined || val === null) return;
          c.sa[kk] = (c.sa[kk] || 0) + val; c.ca[kk] = (c.ca[kk] || 0) + 1;
          if (live) { c.so[kk] = (c.so[kk] || 0) + val; c.co[kk] = (c.co[kk] || 0) + 1; }
        });
      });

      const out = [];
      cells.forEach(c => {
        const o = { x: c.x / c.n, y: c.y / c.n, z: c.z / c.n,
                    level: c.level, occupiable: c.occ, w: c.w, vis: c.vis, n: c.n };
        KEYS.forEach(kk => {
          if (c.occ && c.co[kk]) o[kk] = c.so[kk] / c.co[kk];
          else if (c.ca[kk]) o[kk] = c.sa[kk] / c.ca[kk];
        });
        out.push(o);
      });
      return (this._lod[stride] = out);
    }

    set(k, v) {
      this.opts[k] = v;
      // 표시 해상도를 바꾸면 묶어둔 캐시는 유효하지만, 데이터를 갈아끼우면 버린다.
      if (k === 'data') { this.d = v; this._lod = null; this._slices = null;
                          this._planar = undefined; }
      this.draw();
    }

    /* 지금 몇 m 블록으로 그리고 있는가. 화면에 밝히는 용도다. */
    drawScale() { return (this._stride || 1) * this.d.site.voxel_m; }

    /* 복셀 값이 바뀌었다 — 묶어둔 것을 버린다.
     * 사용자가 카메라를 놓을 때마다 P 가 다시 계산되는데, 캐시를 그대로 두면
     * 처음 그린 색이 계속 남는다. */
    invalidate() { this._lod = null; this._slices = null; }

    /* 데이터를 갈아끼운다. **뷰어를 다시 만들지 않는다** — 생성자는 resize 와
     * LOD 재생성(36ms)을 부르므로, 카메라를 놓을 때마다 새로 만들면 그만큼
     * 느려진다. 시점·확대는 그대로 두어 보던 각도가 유지된다. */
    setData(d, opts) {
      this.d = d;
      if (opts) Object.assign(this.opts, opts);
      this._lod = null;
      this._slices = null;
      this._planar = undefined;
      this.draw();
    }

    resize() {
      const r = this.cv.getBoundingClientRect();
      const dpr = global.devicePixelRatio || 1;
      this.cv.width = Math.max(1, Math.round(r.width * dpr));
      this.cv.height = Math.max(1, Math.round(r.height * dpr));
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.W = r.width; this.H = r.height;
      this.draw();
    }

    _bindOrbit() {
      let drag = null;
      this.cv.addEventListener('pointerdown', e => {
        if (!this.cam.orbit) return;
        drag = { x: e.clientX, y: e.clientY, yaw: this.cam.yaw, pitch: this.cam.pitch };
        this._dragging = true;              // 돌리는 동안은 굵게 그린다
        this.cv.setPointerCapture(e.pointerId);
      });
      this.cv.addEventListener('pointermove', e => {
        if (!drag) return;
        // 위로 끌면 카메라가 올라가 위에서 내려다본다 — OrbitControls·CAD 관례다.
        // 종전에는 부호가 반대라 위를 보려고 위로 끌면 오히려 옆으로 누웠다.
        // 음의 pitch 는 아래에서 올려다보는 것이다. 상부 슬래브에 가린 위층을
        // 확인하려면 이 각도가 필요하다. 면 선택(_cubeFaces)이 부호를 본다.
        this.cam.yaw = drag.yaw + (e.clientX - drag.x) * 0.4;
        this.cam.pitch = Math.max(-85, Math.min(85, drag.pitch - (e.clientY - drag.y) * 0.3));
        this.draw();
      });
      const stop = () => {
        if (!drag) return;
        drag = null;
        this._dragging = false;             // 손을 떼면 원래 해상도로 다시 그린다
        this.draw();
      };
      this.cv.addEventListener('pointerup', stop);
      this.cv.addEventListener('pointercancel', stop);
      this.cv.addEventListener('wheel', e => {
        if (!this.cam.orbit) return;
        e.preventDefault();
        this.zoomBy(e.deltaY, e.deltaMode);
        this.draw();
      }, { passive: false });
    }

    /* 휠 확대.
     *
     * 종전에는 이벤트 하나마다 무조건 ×1.1 / ×0.9 였다. 문제가 셋이었다.
     *   ① 휠 굴린 양을 무시한다 — 트랙패드는 작은 델타를 초당 수십 번 보내는데
     *      그때마다 10% 씩 튄다. "너무 예민하다" 는 것이 이것이다
     *   ② 1.1 × 0.9 = 0.99 라 올렸다 내리면 제자리로 안 온다
     *   ③ deltaMode 를 안 본다 — 줄 단위(1)·페이지 단위(2)로 오는 브라우저에서는
     *      델타가 3 이나 1 이라 사실상 무시되거나 반대로 튄다
     *
     * 굴린 양에 비례한 지수로 바꾼다. 표준 한 칸(deltaY 100)에 약 5%,
     * 방향을 뒤집으면 정확히 되돌아온다. 한 이벤트가 크게 튀지 않게 배율을
     * [0.8, 1.25] 로 자른다.
     */
    zoomBy(deltaY, deltaMode) {
      const unit = deltaMode === 1 ? 16 : (deltaMode === 2 ? 100 : 1);
      const f = Math.exp(-deltaY * unit * 0.0005);
      const step = Math.max(0.8, Math.min(1.25, f));
      this.zoom = Math.max(0.4, Math.min(3, this.zoom * step));
      return this.zoom;
    }

    /* 세계좌표 → 투영 평면. 화면 크기는 여기서 모른다.
     * z 도 피벗(_pivotZ, 그릴 것의 높이 중앙)을 빼고 돌린다. 안 빼면 회전축이
     * 지면에 놓여 위아래로 드래그할 때 모델이 축을 중심으로 휘둘린다. */
    _raw(x, y, z) {
      const S = this.d.site;
      const cx = S.width_m / 2, cy = S.depth_m / 2;
      const yaw = this.cam.yaw * DEG, pit = this.cam.pitch * DEG;
      const dx = x - cx, dy = y - cy;
      const dz = (z - (this._pivotZ || 0)) * (this.cam.zx || 1);

      const rx = dx * Math.cos(yaw) - dy * Math.sin(yaw);
      const ry = dx * Math.sin(yaw) + dy * Math.cos(yaw);

      const sy = ry * Math.sin(pit) - dz * Math.cos(pit);
      const depth = ry * Math.cos(pit) + dz * Math.sin(pit);   // 정렬용

      let sx = rx, sy2 = sy;
      if (this.cam.persp) {
        const dist = Math.max(S.width_m, S.depth_m) * 1.6;
        const k = dist / (dist + depth);
        sx *= k; sy2 *= k;
      }
      return { x: sx, y: sy2, depth };
    }

    /* 투영 평면 → 화면. _fit 은 draw() 가 매번 다시 잰다.
     * 수직 과장·회전·원근이 섞이면 결과 크기를 미리 알 수 없어, 고정 배율로
     * 두면 캔버스 밖으로 넘친다. 그래서 실제 투영 결과에 맞춘다. */
    _project(x, y, z) {
      const r = this._raw(x, y, z);
      const f = this._fit;
      return { x: f.ox + r.x * f.s, y: f.oy + r.y * f.s, depth: r.depth };
    }

    /* 그릴 것의 월드 경계를 훑어 회전 피벗과 배율·중심을 정한다.
     *
     * **궤도 모드에서 투영 경계로 매 프레임 다시 맞추면 안 된다.** 각도가 바뀌면
     * 실루엣이 바뀌고, 배율과 중심이 그것을 따라다닌다. 이 데이터로 실측하니
     * yaw 한 바퀴에 배율이 7.23~10.37 로 **43% 출렁이고** bbox 중심이 **19.3m**
     * 미끄러졌다. 회전이 부자연스럽게 보이는 원인이 이것이다.
     *
     * 그래서 궤도 모드에서는 **yaw 전 구간의 최악값**으로 배율을 고정하고 중심을
     * 캔버스 한가운데에 못박는다. yaw 를 아무리 돌려도 배율·중심이 상수라
     * 모델이 제자리에서 돈다. 최악값은 월드 AABB 의 8꼭짓점만 훑으면 되고
     * (정사영이 아핀이며 원근 왜곡이 완만하다), 이 데이터에서 전 각도·전 점이
     * 캔버스 안에 들어옴을 확인했다. 대가는 가장 유리한 각도 대비 32% 작게
     * 보이는 것이다 — 종전 최소 배율보다는 2% 작을 뿐이다.
     *
     * 고정 각도인 2D·2.5D 는 종전대로 실제 투영 경계에 맞춘다. 각도가 안 바뀌니
     * 흔들릴 일이 없고, 화면을 꽉 채우는 편이 읽기 좋다.
     */
    _measure() {
      const S = this.d.site, d = this.d;
      const onlyOcc = this.opts.onlyOccupiable !== false;
      // 화면에 맞추는 대상은 **실제로 그리는 것**이라야 한다. LOD 로 묶은 뒤에도
      // 같은 배열을 써야 배율과 피벗이 그림과 어긋나지 않는다.
      const ds = this._drawSet();
      const dv = ds.voxels;
      const hh = ds.size / 2;
      const pad = 26;

      // ① 그릴 것의 월드 AABB. 피벗을 여기서 얻는다.
      let wx0 = Infinity, wy0 = Infinity, wz0 = Infinity;
      let wx1 = -Infinity, wy1 = -Infinity, wz1 = -Infinity;
      const world = (x, y, z) => {
        if (x < wx0) wx0 = x; if (x > wx1) wx1 = x;
        if (y < wy0) wy0 = y; if (y > wy1) wy1 = y;
        if (z < wz0) wz0 = z; if (z > wz1) wz1 = z;
      };
      dv.forEach(v => {
        if (onlyOcc && v.occupiable === false) return;
        world(v.x, v.y, v.z - hh);
        world(v.x, v.y, v.z + hh);
      });
      const solids = this.opts.showSolids && d.solids;
      if (solids) {
        d.solids.forEach(b => {
          world(b.x1, b.y1, b.z1); world(b.x2, b.y2, b.z2);
          world(b.x1, b.y2, b.z2); world(b.x2, b.y1, b.z1);
        });
      }
      if (!isFinite(wx0)) {           // 그릴 것이 없다 — 현장 크기로 대신한다
        wx0 = 0; wx1 = S.width_m; wy0 = 0; wy1 = S.depth_m; wz0 = 0; wz1 = 0;
      }
      this._pivotZ = (wz0 + wz1) / 2;

      const span = (pts) => {          // 현재 각도에서 투영 경계
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        pts.forEach(p => {
          const q = this._raw(p[0], p[1], p[2]);
          if (q.x < x0) x0 = q.x; if (q.x > x1) x1 = q.x;
          if (q.y < y0) y0 = q.y; if (q.y > y1) y1 = q.y;
        });
        return [x0, y0, x1, y1];
      };
      const scale = (b) => Math.min((this.W - pad*2) / Math.max(1e-6, b[2] - b[0]),
                                    (this.H - pad*2) / Math.max(1e-6, b[3] - b[1]));

      if (this.cam.orbit) {
        // ② 궤도 — 배율·중심을 각도와 **완전히 분리**한다.
        // 프리셋 기준각에서 yaw 한 바퀴의 최악값을 한 번만 재고, 모드·옵션·줌·
        // 캔버스 크기가 바뀔 때까지 그대로 쓴다. 드래그로는 절대 다시 재지 않으므로
        // 회전 중 배율이 변하지 않는다. 극단적인 각도에서는 가장자리가 넘칠 수
        // 있는데, 휠 줌으로 조절하는 편이 회전이 출렁이는 것보다 낫다.
        const key = [this.opts.showSolids, onlyOcc,
                     Math.round(this.W), Math.round(this.H),
                     this.zoom.toFixed(3)].join('|');
        if (this._fitKey !== key) {
          const corners = [];
          for (const x of [wx0, wx1])
            for (const y of [wy0, wy1])
              for (const z of [wz0, wz1]) corners.push([x, y, z]);
          const keepY = this.cam.yaw, keepP = this.cam.pitch;
          this.cam.pitch = PRESETS[this.opts.mode].pitch;   // 기준각 — 재현 가능하게
          let s = Infinity;
          for (let a = 0; a < 360; a += 15) {
            this.cam.yaw = a;
            s = Math.min(s, scale(span(corners)));
          }
          this.cam.yaw = keepY; this.cam.pitch = keepP;
          this._fitKey = key;
          this._fit = { s: s * this.zoom, ox: this.W / 2, oy: this.H / 2 };
        }
        return;
      }

      // ③ 고정 각도 — 실제 투영 경계에 맞춘다
      const pts = [];
      dv.forEach(v => {
        if (onlyOcc && v.occupiable === false) return;
        pts.push([v.x, v.y, v.z - hh], [v.x, v.y, v.z + hh]);
      });
      if (solids) {
        d.solids.forEach(b => {
          pts.push([b.x1,b.y1,b.z1], [b.x2,b.y2,b.z2],
                   [b.x1,b.y2,b.z2], [b.x2,b.y1,b.z1]);
        });
      }
      let b = pts.length ? span(pts)
                         : [-S.width_m/2, -S.depth_m/2, S.width_m/2, S.depth_m/2];
      const s = scale(b) * this.zoom;
      this._fit = { s, ox: this.W/2 - (b[0] + b[2])/2 * s,
                       oy: this.H/2 - (b[1] + b[3])/2 * s };
    }

    /* 큐브의 **보이는 면만** 돌려준다.
     * 6면을 다 그리면 복셀 1만 개에 6만 폴리곤이라 회전이 버벅인다.
     * 정사영·원근 모두 카메라를 등진 면은 어차피 앞면에 가리므로 셋이면 된다.
     * 어느 셋인지는 yaw·pitch 부호로 정해진다. */
    _cubeFaces(x, y, z, s) {
      const h = s / 2;
      const P = (a, b, c) => this._project(a, b, c);
      const yaw = ((this.cam.yaw % 360) + 360) % 360;
      const east = (yaw > 180);            // +x 면이 보이는가
      const north = (yaw > 90 && yaw < 270);
      const sx = east ? h : -h, sy = north ? h : -h;
      // 위에서 보면 윗면, 아래에서 올려다보면 밑면이 보인다
      const sz = this.cam.pitch >= 0 ? h : -h;
      return [
        [P(x-h,y-h,z+sz), P(x+h,y-h,z+sz), P(x+h,y+h,z+sz), P(x-h,y+h,z+sz)],
        // x 쪽 옆면
        [P(x+sx,y-h,z-h), P(x+sx,y+h,z-h), P(x+sx,y+h,z+h), P(x+sx,y-h,z+h)],
        // y 쪽 옆면
        [P(x-h,y+sy,z-h), P(x+h,y+sy,z-h), P(x+h,y+sy,z+h), P(x-h,y+sy,z+h)],
      ];
    }

    _boxFaces(b) {
      const c = [[b.x1, b.y1, b.z1], [b.x2, b.y1, b.z1], [b.x2, b.y2, b.z1], [b.x1, b.y2, b.z1],
                 [b.x1, b.y1, b.z2], [b.x2, b.y1, b.z2], [b.x2, b.y2, b.z2], [b.x1, b.y2, b.z2]];
      const idx = [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
      return idx.map(f => f.map(i => this._project(c[i][0], c[i][1], c[i][2])));
    }

    /* 건설 목적물 — 실체가 있으므로 면을 채우되 **덩어리로 그리지 않는다.**
     *
     * `_boxFaces` 로 6면을 다 채우면 무엇이든 큐브로 보인다. 코어 벽체는 수직
     * 구조체이고 슬래브는 수평 판이라 읽히는 방향이 다르다. 각자 **의미 있는
     * 면만** 그린다.
     *
     * `_boxFaces` 의 면 순서는 [바닥, 상단, 옆면 ×4] 다.
     */
    /* 면의 테두리만 선으로 올린다. 채우기를 늘리지 않고 형태를 세울 때 쓴다. */
    _edges(list, face, stroke, lw) {
      for (let i = 0; i < face.length; i++) {
        const a = face[i], b = face[(i + 1) % face.length];
        list.push({ depth: 0, pts: [a, b], fill: null, stroke, lw, line: true });
      }
    }

    /* 가설 펜스 — 현장을 두르는 가설울타리. **선으로 그린다.**
     *
     * 상자로 채우면 현장 전체가 회색 테두리로 둘러싸여 안이 안 보인다. 실제로도
     * 판이 아니라 기둥에 판넬을 끼운 것이라 얇은 벽이다. 카메라를 다는 구조체로
     * 쓰되 **가림 계산에는 넣지 않는다**(coverage 0, 추후 과제).
     */
    _drawFence(over, b) {
      const c = [110, 138, 158];
      const long = (b.x2 - b.x1) >= (b.y2 - b.y1);
      const n = Math.max(2, Math.round((long ? b.x2 - b.x1 : b.y2 - b.y1) / 4));
      const mx = (b.x1 + b.x2) / 2, my = (b.y1 + b.y2) / 2;
      // 윗선 하나 + 기둥. 면을 만들지 않으므로 히트맵을 가리지 않는다.
      const a0 = this._project(long ? b.x1 : mx, long ? my : b.y1, b.z2);
      const a1 = this._project(long ? b.x2 : mx, long ? my : b.y2, b.z2);
      over.push({ depth: (a0.depth + a1.depth) / 2, pts: [a0, a1], line: true,
                  fill: null, stroke: rgba(c, 0.7), lw: 1.2 });
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const px = long ? b.x1 + (b.x2 - b.x1) * t : mx;
        const py = long ? my : b.y1 + (b.y2 - b.y1) * t;
        const g = this._project(px, py, b.z1), h = this._project(px, py, b.z2);
        over.push({ depth: (g.depth + h.depth) / 2, pts: [g, h], line: true,
                    fill: null, stroke: rgba(c, 0.45), lw: 1 });
      }
    }

    _drawStructure(items, over, b) {
      const f = this._boxFaces(b);
      const dep = (q) => q.reduce((a, p) => a + p.depth, 0) / q.length;
      const push = (q, fill, stroke, lw) => items.push({
        depth: dep(q) - 0.01, pts: q, fill, stroke, lw,
      });

      // **채우기는 아끼고 윤곽으로 세운다.** 이 화면의 본론은 복셀의 검출확률
      // 색이라, 구조체를 진하게 채우면 정작 봐야 할 것이 가려진다. 특히 슬래브는
      // 64×32m 판이라 불투명하면 그 층 아래가 통째로 사라진다.
      // 대신 선을 굵고 진하게 두면 **가리는 면적을 늘리지 않고** 형태가 또렷해진다.
      if (b.kind === 'slab') {
        // 슬래브 — **윗면 한 장.** 사람이 딛는 면이 그것이고, 두께 0.21m 를
        // 상자로 그리면 판이 아니라 얇은 블록으로 보인다.
        //
        // 복셀을 걷은 '현장만' 화면에서는 가릴 히트맵이 없다. 그때는 판을
        // 진하게 채운다 — 안 그러면 층이 어디 있는지 보이지 않아, 무엇을
        // 놓고 재는지 확인하려고 만든 화면이 제 몫을 못 한다.
        const c = [140, 149, 159];
        const bare = this.opts.showVoxels === false;
        push(f[1], rgba(c, bare ? 0.22 : 0.06), rgba(c, 0.75), 1.4);
        this._edges(over, f[1], rgba(c, 0.75), 1.2);   // 층 경계는 늘 보이게
        return;
      }
      if (b.kind === 'stack') {
        // 적치물 — 낮은 덩어리. 윗면과 옆면만.
        const c = [138, 118, 78];
        push(f[1], rgba(c, 0.22), rgba(c, 0.80), 1.2);
        for (let i = 2; i < 6; i++) push(f[i], rgba(c, 0.14), rgba(c, 0.60), 1.0);
        return;
      }
      // 코어 벽체 — **옆면(벽)만 채우고 상단은 윤곽만.** 수직 구조체로 읽힌다.
      // 실제 코어는 승강로·계단실이라 속이 빈 벽체 통이며, 광선이 통과하지
      // 못하는 것은 솔리드와 같다. 다만 **모델은 솔리드로 두어 내부 복셀을
      // 만들지 않는다** — 속이 비었다고 주장하지 않으려고 상단을 열지 않는다.
      //
      // 코어는 12×16m 로 작아 진하게 채워도 히트맵을 조금만 가린다. 건물이
      // 어디인지 세우는 기준이므로 여기만 불투명에 가깝게 둔다(0.26 -> 0.55).
      const c = [92, 100, 110];
      for (let i = 2; i < 6; i++) push(f[i], rgba(c, 0.55), rgba(c, 0.92), 1.6);
      push(f[1], rgba(c, 0.18), rgba(c, 0.95), 1.8);
      // 복셀 3만 개가 앞을 가려 채우기만으로는 형태가 안 선다. **윤곽만** 위층에
      // 올린다 — 가리는 면적은 그대로 두고 어디가 건물인지 또렷해진다.
      this._edges(over, f[1], rgba(c, 0.95), 1.6);     // 상단 테두리
      for (let i = 2; i < 6; i++) this._edges(over, f[i], rgba(c, 0.75), 1.0);
    }

    /* 가설물(비계) — **면을 채우지 않고 수직 부재로 그린다.**
     * 비계는 판이 아니라 지주 다발이다. 지주 간격 1.8m 는 임의값이 아니라
     * 실험의 스트라이프 주기를 유도할 때 쓴 값과 같다(CLAUDE.md §4.2).
     * 상하 띠장을 함께 그려 뼈대로 읽히게 한다. */
    _drawScaffold(items, b) {
      const c = [110, 138, 158];
      const P = (x, y, z) => this._project(x, y, z);
      const push = (a, z2) => {
        items.push({ depth: 0, pts: [a, z2],
                     fill: null, stroke: rgba(c, 0.75), lw: 1.0, line: true });
      };
      const STEP = 1.8;                       // 지주 간격 (m)
      const long = (b.x2 - b.x1) >= (b.y2 - b.y1);
      const n = Math.max(2, Math.round((long ? b.x2 - b.x1 : b.y2 - b.y1) / STEP));
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const x = long ? b.x1 + (b.x2 - b.x1) * t : (b.x1 + b.x2) / 2;
        const y = long ? (b.y1 + b.y2) / 2 : b.y1 + (b.y2 - b.y1) * t;
        push(P(x, y, b.z1), P(x, y, b.z2));   // 지주
      }
      // 띠장 — 바닥·중간·상단 세 줄
      for (const z of [b.z1, (b.z1 + b.z2) / 2, b.z2]) {
        const a = P(b.x1, (b.y1 + b.y2) / 2, z);
        const e = P(b.x2, (b.y1 + b.y2) / 2, z);
        const a2 = P((b.x1 + b.x2) / 2, b.y1, z);
        const e2 = P((b.x1 + b.x2) / 2, b.y2, z);
        push(long ? a : a2, long ? e : e2);
      }
    }

    /* 위험구역 — 실체가 아니라 **영역 라벨**이다. 속을 채우지 않고
     * 바닥·상단 윤곽과 모서리 기둥만 그려 "여기부터 저기까지" 를 표시한다.
     * 채우면 실물 구조로 오해되고 복셀 색도 덮는다. */
    _drawZoneCage(items, z) {
      const c = [166, 42, 42];
      const z1 = (z.z1 == null) ? 0 : z.z1;
      const z2 = (z.z2 == null) ? (this.d.site.z_max_m || 14) : z.z2;
      const P = (x, y, zz) => this._project(x, y, zz);
      const corner = [[z.x1, z.y1], [z.x2, z.y1], [z.x2, z.y2], [z.x1, z.y2]];
      const line = (a, b2, w) => items.push({
        depth: 0, pts: [a, b2],
        fill: null, stroke: rgba(c, 0.7), lw: w, line: true,
      });
      for (const zz of [z1, z2]) {            // 바닥·상단 윤곽
        for (let i = 0; i < 4; i++) {
          const a = corner[i], b2 = corner[(i + 1) % 4];
          line(P(a[0], a[1], zz), P(b2[0], b2[1], zz), 1.1);
        }
      }
      for (const q of corner) line(P(q[0], q[1], z1), P(q[0], q[1], z2), 0.8);
    }

    draw() {
      const ctx = this.ctx, d = this.d;
      ctx.clearRect(0, 0, this.W, this.H);
      this._measure();
      const items = [];

      // ── 현장을 이루는 것들 ──────────────────────────────────────────
      //
      // 셋을 **같은 상자로 그리지 않는다.** 성격이 다르기 때문이다.
      //
      //   건설 목적물  실체 있는 콘크리트          -> 면을 채운다
      //   가설물       임시 구조, 비계는 수직 부재  -> 지주 선으로 그린다
      //   위험구역     실체가 아니라 영역 라벨      -> 빈 케이지로 두른다
      //
      // 채우느냐 비우느냐가 구분의 축이다. 셋이 전부 반투명 상자였을 때는
      // 한 화면에서 무엇이 실물이고 무엇이 표시인지 읽히지 않았다.
      // 건설 목적물은 실체라 **깊이 정렬에 참여한다** — 앞의 복셀에 가려야 맞다.
      // 가설물·위험구역은 성격이 주석이라 별도 층(over)에 모아 **맨 위에 그린다.**
      // 복셀 3만 개 사이에 섞이면 선이 파묻혀 안 보인다. 공간 관계를 조금 잃는
      // 대신 "비계가 어디를 감싸고 위험구역이 어디인가" 가 읽힌다.
      const over = [];
      if (this.opts.showSolids && d.solids) {
        d.solids.forEach(b => {
          if (b.kind === 'scaffold') this._drawScaffold(over, b);
          else if (b.kind === 'fence') this._drawFence(over, b);
          else this._drawStructure(items, over, b);
        });
      }
      if (this.opts.showZones !== false && d.zones) {
        d.zones.forEach(z => this._drawZoneCage(over, z));
      }

      // ── 복셀 ──
      const key = this.opts.key;
      const onlyOcc = this.opts.onlyOccupiable !== false;
      const ds = this._drawSet();
      const s = ds.size;                      // LOD 로 묶였으면 그만큼 큰 큐브다
      this._stride = ds.stride;
      // 큐브를 꽉 채우면 안쪽이 안 보인다. 살짝 줄여 사이가 비게 둔다.
      const cs = s * 0.86;
      const shade = [1.0, 0.82, 0.66];        // 윗면 / 옆면 둘 — 입체감

      // 복셀을 끄면 현장 자체만 남는다 — 골조·가설물·위험구역·카메라.
      // 히트맵이 덮고 있어 무엇을 입력했는지 안 보인다는 문제 때문이다.
      ds.voxels.forEach(v => {
        if (this.opts.showVoxels === false) return;
        if (onlyOcc && v.occupiable === false) return;
        const p = v[key];
        if (p === undefined || p === null) return;

        // 지도마다 값도 색도 다르다. 가중치·관측 대수는 그대로 칠한다.
        const risk = this.opts.key === 'w';
        const vis = this.opts.key === 'vis';
        // 취약도 w·(1−P). 눈금은 0~5 고정이며 0 인 칸은 그리지 않는다 —
        // 평면도와 같은 규칙이어야 두 화면이 같은 말을 한다.
        const miss = this.opts.key === 'miss';
        if (miss && p < 0.5) return;
        // 상한은 현장의 최대 위험가중치다 — 5 로 박으면 w10 구역에서 포화된다.
        const mm = this.opts.missMax || 5;
        const base = risk ? riskColor(p)
                   : miss ? riskColor(1 + 4 * Math.min(1, p / mm))
                   : vis ? visColor(p) : heat(p);
        const alpha = risk ? 0.25 + 0.5 * ((Math.min(5, p) - 1) / 4)
                    : miss ? 0.10 + 0.74 * Math.pow(Math.min(1, p / mm), 1.7)
                    : vis ? (p <= 0 ? 0.22 : 0.35 + 0.25 * Math.min(1, (p - 1) / 2))
                    : 0.30 + 0.55 * (1 - p);
        this._cubeFaces(v.x, v.y, v.z, cs).forEach((f, fi) => {
          const dep = f.reduce((a, q) => a + q.depth, 0) / f.length;
          const c = base.map(ch => Math.round(ch * shade[fi]));
          items.push({ depth: dep, pts: f, fill: rgba(c, alpha), stroke: null });
        });
      });

      // 화가 알고리즘 — 먼 것부터
      items.sort((a, b) => b.depth - a.depth);
      const paint = (list) => list.forEach(it => {
        ctx.beginPath();
        it.pts.forEach((q, i) => i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y));
        // 선분(지주·케이지)은 닫지 않는다. 닫으면 삼각형이 생긴다.
        if (!it.line) ctx.closePath();
        if (it.fill) { ctx.fillStyle = it.fill; ctx.fill(); }
        if (it.stroke) { ctx.strokeStyle = it.stroke; ctx.lineWidth = it.lw || 1; ctx.stroke(); }
      });
      paint(items);
      paint(over);          // 가설물·위험구역 — 복셀에 파묻히지 않게 맨 위에

      // ── 카메라 (항상 맨 위) ──
      if (this.opts.showCams && d.cameras) {
        const chosen = new Set(this.opts.cameraIds || []);
        d.cameras.forEach(c => {
          const on = chosen.size === 0 || chosen.has(c.id);
          const p = this._project(c.x, c.y, c.z);
          if (on) {
            const ang = (c.yaw_deg || 0) * DEG;
            const half = (d.aim ? d.aim.hfov_deg : 90) * DEG / 2, R = 16;
            const g = this._project(c.x, c.y, 0);
            ctx.beginPath(); ctx.moveTo(g.x, g.y);
            for (let t = -half; t <= half + 1e-6; t += half / 8) {
              const q = this._project(c.x + R * Math.cos(ang + t),
                                      c.y + R * Math.sin(ang + t), 0);
              ctx.lineTo(q.x, q.y);
            }
            ctx.closePath();
            ctx.fillStyle = 'rgba(56,62,72,.12)'; ctx.fill();
            ctx.strokeStyle = 'rgba(56,62,72,.40)'; ctx.lineWidth = 1; ctx.stroke();
            // 설치 높이를 기둥으로 — 3D 에서 카메라가 떠 있는 게 보여야 한다
            ctx.beginPath(); ctx.moveTo(g.x, g.y); ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = 'rgba(56,62,72,.45)'; ctx.stroke();
          }
          ctx.beginPath();
          ctx.arc(p.x, p.y, on ? 5 : 3, 0, Math.PI * 2);
          ctx.fillStyle = on ? 'rgba(24,28,34,1)' : 'rgba(180,188,197,1)';
          ctx.fill();
          ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();
        });
      }
    }
  }

  /* 위험 가중치 색 — 1(옅음) → 5(진함).
   *
   * **검출확률과 다른 색띠를 쓴다.** 검출확률은 붉음(0) → 초록(1) 인데, 위험도는
   * 높을수록 나쁘므로 같은 붉은색을 쓰면 두 지도가 정반대를 뜻하면서 같은 색이
   * 된다. 위험도는 **호박색 → 진홍**으로 간다.
   */
  function riskColor(w) {
    const t = Math.max(0, Math.min(1, (w - 1) / 4));    // w 1~5 -> 0~1
    // 호박 -> 자주. 붉은색으로 끝내면 **검출확률 0(가장 나쁨)과 같은 색**이 되어
    // 두 지도가 정반대를 뜻하면서 똑같이 보인다(실측: w5 가 heat(0) 과 거의 동일).
    return [Math.round(238 - 129 * t), Math.round(205 - 172 * t),
            Math.round(140 - 61 * t)];
  }

  /* 관측 대수 색 — 0(관측 불가) → 3 이상.
   *
   * 검출확률(붉음→초록)·위험도(호박→자주)와 또 갈라야 한다. 관측은 세는 값이라
   * 연속 색띠가 아니라 **계단**이 맞다. 단색 청색의 농도로 올린다. */
  function visColor(n) {
    if (n <= 0) return [176, 183, 191];          // 관측 불가 — 무채
    const t = Math.min(1, (Math.min(3, n) - 1) / 2);
    return [Math.round(122 - 111 * t), Math.round(170 - 91 * t),
            Math.round(212 - 74 * t)];
  }

  global.CoverageViewer = { Viewer, PRESETS, heat, riskColor, visColor };
})(window);
