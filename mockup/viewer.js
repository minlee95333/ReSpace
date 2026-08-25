/* 커버리지 뷰어 — 2D / 2.5D / 3D
 *
 * 세 모드를 따로 만들지 않는다. **투영기 하나에 프리셋 셋**을 둔다.
 *   2D    수직 내려보기(pitch 90°) · 정사영 · 층 하나만
 *   2.5D  아이소메트릭(yaw 45° / pitch 30°) · 정사영 · 층을 쌓아 본다
 *   3D    자유 회전 · 원근 · 드래그로 궤도, 휠로 줌
 *
 * 외부 라이브러리를 쓰지 않는다. 캔버스에 직접 그린다.
 *
 * 깊이 정렬은 화가 알고리즘이다. 면이 축정렬 사각형뿐이라 이걸로 충분하다.
 *
 * ── 성능 (2026-08-21) ────────────────────────────────────────────────
 * 복셀을 1m 로 내리면서 그리는 복셀이 36,348개 · 면이 83,528개가 됐고,
 * 3D 드래그가 프레임당 340~670ms 였다. 계측해서 넷을 고쳤다.
 *
 *   투영 132ms  정점마다 sin/cos 를 네 번 불렀다. 정점이 프레임당 334,000개니
 *               삼각함수만 1,336,000회다. **각도는 프레임 안에서 상수다** —
 *               프레임 시작에 한 번 구해 쓴다.
 *               그리고 투영이 (x,y,z) 에 대해 선형이라, 큐브 여덟 꼭짓점의
 *               화면 오프셋도 프레임당 상수다. **복셀당 투영 12회 → 1회.**
 *
 *   캔버스 201ms  면의 대부분이 안 보이는 면이었다. 실측하니 그리는 복셀의
 *               **43.8%(15,920개)가 이웃 여섯이 다 찬 완전 내부**고, 열린 면은
 *               6면 218,088개 중 22,344개(10.2%)뿐이다. 껍질만 그린다.
 *
 *   정렬 36ms   면 83,528개를 비교 정렬했다. 큐브는 안 겹치니 **복셀 하나에
 *               깊이 하나**면 되고, 비교 대신 버킷 계수정렬이면 O(n) 이다.
 *
 *   합침       pointermove 마다 draw() 를 동기로 불렀다. 포인터는 초당 100회
 *               넘게 뛰는데 한 프레임이 300ms 라 이벤트가 밀려 쌓인다.
 *               rAF 로 합쳐 프레임당 한 번만 그린다.
 *
 * 컬링 규칙은 §안전 쪽으로 비대칭이다 — 이웃이 있어도 그 이웃이 clear(안 칠하는
 * 구간)면 뒤가 비쳐야 하므로 그린다. **미달 복셀은 아예 컬링하지 않는다.**
 * 못 보는 곳을 화면에서 지우는 실수를 하지 않기 위해서다.
 */
(function (global) {
  'use strict';

  const DEG = Math.PI / 180;

  const PRESETS = {
    // zx = 수직 과장.
    // **부피 복셀(큐브)에서는 1에 가깝게 둔다.** 큐브가 이미 실제 높이를 차지하고
    // 있어서 늘리면 14m 현장이 45m 로 보인다. 층별 판(work_plane)일 때만 층이
    // 뭉쳐 보여 과장이 필요했다. 데이터가 어느 쪽인지 보고 정한다.
    '2d':   { yaw: 0,  pitch: 90, persp: false, orbit: false, single: true,  zx: 1 },
    '2.5d': { yaw: 45, pitch: 30, persp: false, orbit: false, single: false, zx: 1.15 },
    // pitch 는 클수록 위에서 내려다본다(2D 가 90). 45 = 스카이뷰.
    //
    // **원근을 끈다(persp: false).** 이게 핵심이다. 부감각을 48 로 올려도
    // 원근이 켜져 있으면 외곽 비계(높이 14m)의 안쪽 면이 벌어져 보여서
    // "현장 안에서 올려다본" 그림으로 읽힌다. 실제로 그 지적을 두 번 받았다.
    // 평행투영(축측)으로 바꾸면 그 착시가 사라지고 건축 배치도처럼 읽힌다.
    // perspK 는 persp 가 true 일 때만 쓰인다 — 궤도 조작으로 켤 수 있어 남긴다.
    '3d':   { yaw: 35, pitch: 45, persp: false, orbit: true,  single: false,
              zx: 1.0, perspK: 3.2 },
  };

  /* 색은 theme.js 한 곳에서만 나온다. 종전에는 이 함수가 index.html 에도
   * 복제돼 있어 한쪽만 고치면 조용히 어긋났다. */
  const heat = (p) => Theme.heat(p);

  function rgba(c, alpha) {
    return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
  }

  const FAIL = 0, MID = 1, CLEAR = 2;

  // 면 방향 비트. 0:+x 1:-x 2:+y 3:-y 4:+z 5:-z
  // 꼭짓점 번호는 c = (ix<<2)|(iy<<1)|iz, 각 비트가 -h/+h 다.
  const FACE_CORNERS = [
    [4, 6, 7, 5],   // +x
    [0, 2, 3, 1],   // -x
    [2, 6, 7, 3],   // +y
    [0, 4, 5, 1],   // -y
    [1, 5, 7, 3],   // +z (윗면)
    [0, 4, 6, 2],   // -z
  ];
  const CORNER_SIGN = [];         // [ix, iy, iz] 를 -1/+1 로
  for (let c = 0; c < 8; c++) {
    CORNER_SIGN.push([(c & 4) ? 1 : -1, (c & 2) ? 1 : -1, (c & 1) ? 1 : -1]);
  }

  const DEPTH_BUCKETS = 2048;

  class Viewer {
    constructor(canvas, data, opts) {
      this.cv = canvas;
      this.ctx = canvas.getContext('2d');
      this.d = data;
      this.opts = Object.assign({ mode: '2.5d', level: 0, key: 'P_total_empirical',
                                  showCams: true, showSolids: true }, opts || {});
      this.cam = Object.assign({}, PRESETS[this.opts.mode]);
      if (this._isPlanar()) this.cam.zx *= 2.8;
      this.zoom = 1;
      this._raf = 0;
      this._prep = null;          // 카메라와 무관한 전처리 (아래 _ensurePrep)
      this._fbuf = null;          // 면 버퍼 — 프레임마다 재사용한다
      this._bindOrbit();
      this.resize();
    }

    setMode(mode) {
      this.opts.mode = mode;
      this.cam = Object.assign({}, PRESETS[mode]);
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

    set(k, v) { this.opts[k] = v; this.draw(); }

    resize() {
      const r = this.cv.getBoundingClientRect();
      const dpr = global.devicePixelRatio || 1;
      this.cv.width = Math.max(1, Math.round(r.width * dpr));
      this.cv.height = Math.max(1, Math.round(r.height * dpr));
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.W = r.width; this.H = r.height;
      this.draw();
    }

    /* 그리기 요청을 프레임에 합친다.
     * 종전에는 pointermove 마다 draw() 를 동기로 불렀다. 한 프레임이 300ms 인데
     * 포인터는 그보다 훨씬 자주 뛰니 이벤트 큐에 draw 가 쌓여, 손을 떼도 한참
     * 더 도는 상태가 됐다. 이것이 체감 렉의 절반이었다. */
    invalidate() {
      if (this._raf) return;
      this._raf = global.requestAnimationFrame(() => { this._raf = 0; this.draw(); });
    }

    _bindOrbit() {
      let drag = null;
      this.cv.addEventListener('pointerdown', e => {
        if (!this.cam.orbit) return;
        drag = { x: e.clientX, y: e.clientY, yaw: this.cam.yaw, pitch: this.cam.pitch };
        this.cv.setPointerCapture(e.pointerId);
      });
      this.cv.addEventListener('pointermove', e => {
        if (!drag) return;
        // 위로 끌면 카메라가 올라가 위에서 내려다본다 — OrbitControls·CAD 관례다.
        // 종전에는 부호가 반대라 위를 보려고 위로 끌면 오히려 옆으로 누웠다.
        // 음의 pitch 는 아래에서 올려다보는 것이다. 상부 슬래브에 가린 위층을
        // 확인하려면 이 각도가 필요하다. 면 선택이 부호를 본다.
        this.cam.yaw = drag.yaw + (e.clientX - drag.x) * 0.4;
        this.cam.pitch = Math.max(-85, Math.min(85, drag.pitch - (e.clientY - drag.y) * 0.3));
        this.invalidate();
      });
      const stop = () => { if (drag) { drag = null; this.invalidate(); } };
      this.cv.addEventListener('pointerup', stop);
      this.cv.addEventListener('pointercancel', stop);
      this.cv.addEventListener('wheel', e => {
        if (!this.cam.orbit) return;
        e.preventDefault();
        this.zoom = Math.max(0.4, Math.min(3, this.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
        this.invalidate();
      }, { passive: false });
    }

    /* 세계좌표 → 투영 평면. 화면 크기는 여기서 모른다.
     * z 도 피벗(_pivotZ, 그릴 것의 높이 중앙)을 빼고 돌린다. 안 빼면 회전축이
     * 지면에 놓여 위아래로 드래그할 때 모델이 축을 중심으로 휘둘린다.
     *
     * **뜨거운 경로는 여기를 쓰지 않는다.** 복셀 수만 개는 아래 _drawVoxels 가
     * 삼각함수를 프레임당 한 번만 구해 처리한다. 이 함수는 골조·카메라·_measure
     * 처럼 호출이 수백 번인 곳에만 남긴다 — 읽기 쉬운 쪽이 낫다. */
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
        const dist = Math.max(S.width_m, S.depth_m) * (this.cam.perspK || 1.6);
        const k = dist / (dist + depth);
        sx *= k; sy2 *= k;
      }
      return { x: sx, y: sy2, depth };
    }

    /* 투영 평면 → 화면. _fit 은 draw() 가 매번 다시 잰다. */
    _project(x, y, z) {
      const r = this._raw(x, y, z);
      const f = this._fit;
      return { x: f.ox + r.x * f.s, y: f.oy + r.y * f.s, depth: r.depth };
    }

    /* ── 카메라와 무관한 전처리 ──────────────────────────────────────
     *
     * 색·밴드·열린 면은 각도가 바뀌어도 안 바뀐다. 그런데 종전에는 프레임마다
     * heat() 를 부르고 rgba 문자열을 새로 만들었다. 여기로 옮겨 한 번만 한다.
     * 옵션(지표·층·표시 범위)이 바뀔 때만 다시 만든다.
     *
     * 열린 면 = 그 방향 이웃이 없거나, 있어도 clear(안 칠하는 구간)라 뒤가
     * 비치는 경우. 미달 복셀은 판정을 가리지 않도록 여섯 면을 다 열어둔다.
     */
    _ensurePrep() {
      const d = this.d, o = this.opts;
      const single = this.cam.single;
      const onlyOcc = o.onlyOccupiable !== false;
      const key = [o.key, single ? o.level : 'all', onlyOcc, d.threshold].join('|');
      if (this._prep && this._prepKey === key) return this._prep;

      const step = d.site.voxel_m;
      const Q = (v) => Math.round(v / step);          // 격자 인덱스
      const src = [];
      for (const v of d.voxels) {
        if (single && v.level !== o.level) continue;
        if (onlyOcc && v.occupiable === false) continue;
        const p = v[o.key];
        if (p === undefined || p === null) continue;
        src.push(v);
      }
      const n = src.length;
      const px = new Float32Array(n), py = new Float32Array(n), pz = new Float32Array(n);
      const bnd = new Uint8Array(n), open = new Uint8Array(n), lw = new Float32Array(n);
      const fill = [new Array(n), new Array(n), new Array(n)];   // 윗면 / x옆 / y옆
      const stroke = new Array(n);

      const failInk = Theme.ui('--color-ink');
      const clearInk = Theme.ui('--color-rule');
      const shade = [1.0, 0.82, 0.66];
      // 색 문자열을 재사용한다. P 를 1/128 로 양자화하면 서로 다른 문자열이
      // 최대 129x3 개뿐이라, 캔버스가 같은 문자열을 다시 파싱하지 않는다.
      // 양자화 폭은 램프에서 1px 도 안 되는 차이라 눈에 띄지 않는다.
      const memo = new Map();
      const colorOf = (p, fi) => {
        const q = Math.round(p * 128);
        const mk = q * 3 + fi;
        let s = memo.get(mk);
        if (s === undefined) {
          const a = Theme.fillAlpha(q / 128, d.threshold);
          if (a <= 0) s = null;
          else {
            const base = heat(q / 128);
            s = rgba(base.map(ch => Math.round(ch * shade[fi])), +a.toFixed(3));
          }
          memo.set(mk, s);
        }
        return s;
      };

      const idx = new Map();
      for (let i = 0; i < n; i++) {
        const v = src[i];
        px[i] = v.x; py[i] = v.y; pz[i] = v.z;
        idx.set(Q(v.x) + ',' + Q(v.y) + ',' + Q(v.z), i);
      }
      const failStroke = rgba(failInk, 0.55);
      const clearStroke = rgba(clearInk, 0.55);
      for (let i = 0; i < n; i++) {
        const p = src[i][o.key];
        const b = Theme.band(p, d.threshold);
        bnd[i] = b === 'fail' ? FAIL : (b === 'clear' ? CLEAR : MID);
        stroke[i] = b === 'fail' ? failStroke : (b === 'clear' ? clearStroke : null);
        lw[i] = b === 'fail' ? 0.8 : 0.5;
        for (let f = 0; f < 3; f++) fill[f][i] = colorOf(p, f);
      }
      // 열린 면.
      // 규칙은 **불투명도 순위**다 — 이웃이 나보다 진하거나 같으면 그 면은
      // 어차피 가려지므로 안 그린다. 이웃이 나보다 옅으면(특히 clear 는 아예
      // 안 칠한다) 뒤가 비쳐야 하므로 그린다.
      //   fail 0.60~0.88 > mid 0.08~0.30 > clear 0
      // 이 규칙이면 **미달이 옅은 이웃 뒤에서 사라지는 일이 없다.** 미달이
      // 지워지는 방향은 미달끼리 서로 가릴 때뿐이고, 그건 눈에 안 보이는 면이다.
      const RANK = new Uint8Array(3);
      RANK[FAIL] = 2; RANK[MID] = 1; RANK[CLEAR] = 0;
      const NB = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]];
      for (let i = 0; i < n; i++) {
        const qx = Q(px[i]), qy = Q(py[i]), qz = Q(pz[i]);
        const mine = RANK[bnd[i]];
        let m = 0;
        for (let f = 0; f < 6; f++) {
          const j = idx.get((qx + NB[f][0]) + ',' + (qy + NB[f][1]) + ',' + (qz + NB[f][2]));
          if (j === undefined || RANK[bnd[j]] < mine) m |= (1 << f);
        }
        open[i] = m;
      }

      // 그릴 것의 월드 AABB. _measure 가 프레임마다 78,816개를 훑던 것을 뺀다.
      let x0 = Infinity, y0 = Infinity, z0 = Infinity;
      let x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
      const hh = step / 2;
      for (let i = 0; i < n; i++) {
        if (px[i] < x0) x0 = px[i]; if (px[i] > x1) x1 = px[i];
        if (py[i] < y0) y0 = py[i]; if (py[i] > y1) y1 = py[i];
        if (pz[i] - hh < z0) z0 = pz[i] - hh; if (pz[i] + hh > z1) z1 = pz[i] + hh;
      }

      this._prepKey = key;
      this._prep = { n, px, py, pz, bnd, open, fill, stroke, lw,
                     aabb: [x0, y0, z0, x1, y1, z1] };
      return this._prep;
    }

    /* 그릴 것의 월드 경계를 훑어 회전 피벗과 배율·중심을 정한다.
     *
     * **궤도 모드에서 투영 경계로 매 프레임 다시 맞추면 안 된다.** 각도가 바뀌면
     * 실루엣이 바뀌고, 배율과 중심이 그것을 따라다닌다. 이 데이터로 실측하니
     * yaw 한 바퀴에 배율이 7.23~10.37 로 **43% 출렁이고** bbox 중심이 **19.3m**
     * 미끄러졌다. 회전이 부자연스럽게 보이는 원인이 이것이다.
     *
     * 그래서 궤도 모드에서는 **yaw 전 구간의 최악값**으로 배율을 고정하고 중심을
     * 캔버스 한가운데에 못박는다. 최악값은 월드 AABB 의 8꼭짓점만 훑으면 된다.
     *
     * 고정 각도인 2D·2.5D 는 실제 투영 경계에 맞춘다. 각도가 안 바뀌니 흔들릴
     * 일이 없고, 화면을 꽉 채우는 편이 읽기 좋다.
     */
    _measure() {
      const S = this.d.site, d = this.d;
      const single = this.cam.single;
      const P = this._ensurePrep();
      const pad = 26;

      let [wx0, wy0, wz0, wx1, wy1, wz1] = P.aabb;
      const solids = this.opts.showSolids && d.solids && !single;
      if (solids) {
        d.solids.forEach(b => {
          wx0 = Math.min(wx0, b.x1, b.x2); wx1 = Math.max(wx1, b.x1, b.x2);
          wy0 = Math.min(wy0, b.y1, b.y2); wy1 = Math.max(wy1, b.y1, b.y2);
          wz0 = Math.min(wz0, b.z1, b.z2); wz1 = Math.max(wz1, b.z1, b.z2);
        });
      }
      if (!isFinite(wx0)) {           // 그릴 것이 없다 — 현장 크기로 대신한다
        wx0 = 0; wx1 = S.width_m; wy0 = 0; wy1 = S.depth_m; wz0 = 0; wz1 = 0;
      }
      this._pivotZ = (wz0 + wz1) / 2;

      const corners = [];
      for (const x of [wx0, wx1])
        for (const y of [wy0, wy1])
          for (const z of [wz0, wz1]) corners.push([x, y, z]);

      const span = (pts) => {          // 현재 각도에서 투영 경계
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const p of pts) {
          const q = this._raw(p[0], p[1], p[2]);
          if (q.x < x0) x0 = q.x; if (q.x > x1) x1 = q.x;
          if (q.y < y0) y0 = q.y; if (q.y > y1) y1 = q.y;
        }
        return [x0, y0, x1, y1];
      };
      const scale = (b) => Math.min((this.W - pad*2) / Math.max(1e-6, b[2] - b[0]),
                                    (this.H - pad*2) / Math.max(1e-6, b[3] - b[1]));

      if (this.cam.orbit) {
        // 배율·중심을 각도와 **완전히 분리**한다. 드래그로는 절대 다시 재지
        // 않으므로 회전 중 배율이 변하지 않는다.
        const key = [this.opts.mode, this._prepKey, this.opts.showSolids,
                     Math.round(this.W), Math.round(this.H),
                     this.zoom.toFixed(3)].join('|');
        if (this._fitKey !== key) {
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

      // 고정 각도 — 실제 투영 경계에 맞춘다.
      // AABB 꼭짓점만 보면 안 된다. 점유 가능 복셀이 AABB 를 다 채우지 않으면
      // 중심이 빈 곳으로 끌려가 화면이 한쪽으로 쏠린다. 복셀 중심을 다 훑되,
      // 삼각함수를 밖으로 빼 36,348개를 1ms 안에 처리한다.
      const yw = this.cam.yaw * DEG, pt = this.cam.pitch * DEG;
      const cyw = Math.cos(yw), syw = Math.sin(yw);
      const cpt = Math.cos(pt), spt = Math.sin(pt);
      const zx = this.cam.zx || 1, hz = (this.d.site.voxel_m / 2) * zx;
      const cxm = S.width_m / 2, cym = S.depth_m / 2;
      let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
      for (let i = 0; i < P.n; i++) {
        const ddx = P.px[i] - cxm, ddy = P.py[i] - cym;
        const rx = ddx * cyw - ddy * syw;
        const ry = ddx * syw + ddy * cyw;
        const zc = (P.pz[i] - this._pivotZ) * zx;
        if (rx < bx0) bx0 = rx; if (rx > bx1) bx1 = rx;
        for (const dz of [zc - hz, zc + hz]) {
          const yy = ry * spt - dz * cpt;
          if (yy < by0) by0 = yy; if (yy > by1) by1 = yy;
        }
      }
      const pts = [];
      if (solids) {
        d.solids.forEach(b => {
          pts.push([b.x1,b.y1,b.z1], [b.x2,b.y2,b.z2],
                   [b.x1,b.y2,b.z2], [b.x2,b.y1,b.z1]);
        });
      }
      if (pts.length) {
        const sb = span(pts);
        bx0 = Math.min(bx0, sb[0]); by0 = Math.min(by0, sb[1]);
        bx1 = Math.max(bx1, sb[2]); by1 = Math.max(by1, sb[3]);
      }
      if (!isFinite(bx0)) { bx0 = -S.width_m/2; bx1 = S.width_m/2;
                            by0 = -S.depth_m/2; by1 = S.depth_m/2; }
      const b = [bx0, by0, bx1, by1];
      const s = scale(b) * this.zoom;
      this._fit = { s, ox: this.W/2 - (b[0] + b[2])/2 * s,
                       oy: this.H/2 - (b[1] + b[3])/2 * s };
    }

    _boxFaces(b) {
      const c = [[b.x1, b.y1, b.z1], [b.x2, b.y1, b.z1], [b.x2, b.y2, b.z1], [b.x1, b.y2, b.z1],
                 [b.x1, b.y1, b.z2], [b.x2, b.y1, b.z2], [b.x2, b.y2, b.z2], [b.x1, b.y2, b.z2]];
      const idx = [[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]];
      return idx.map(f => f.map(i => this._project(c[i][0], c[i][1], c[i][2])));
    }

    /* ── 면 버퍼 ─────────────────────────────────────────────────────
     * 프레임마다 객체 수십만 개를 새로 만들면 GC 가 프레임을 잡아먹는다.
     * 타입 배열 하나를 만들어 계속 다시 쓴다. */
    _buf(cap) {
      let b = this._fbuf;
      if (!b || b.cap < cap) {
        const c = Math.max(cap, 4096);
        b = this._fbuf = {
          cap: c,
          x: new Float32Array(c * 4), y: new Float32Array(c * 4),
          depth: new Float32Array(c),
          fill: new Array(c), stroke: new Array(c), lw: new Float32Array(c),
          order: new Uint32Array(c), bi: new Int32Array(c),
          bucket: new Int32Array(DEPTH_BUCKETS + 1),
        };
      }
      b.n = 0;
      return b;
    }

    draw() {
      const ctx = this.ctx, d = this.d;
      ctx.clearRect(0, 0, this.W, this.H);
      this._measure();

      const P = this._ensurePrep();
      const single = this.cam.single;
      const flat = this.cam.pitch >= 89;      // 2D 는 판으로 그리는 게 읽기 쉽다
      const solids = this.opts.showSolids && d.solids;
      const buf = this._buf(P.n * 3 + (solids ? d.solids.length * 6 : 0) + 16);

      const push = (x0,y0,x1,y1,x2,y2,x3,y3, depth, fill, stroke, lw) => {
        const i = buf.n++, o = i * 4;
        buf.x[o]=x0; buf.y[o]=y0; buf.x[o+1]=x1; buf.y[o+1]=y1;
        buf.x[o+2]=x2; buf.y[o+2]=y2; buf.x[o+3]=x3; buf.y[o+3]=y3;
        buf.depth[i]=depth; buf.fill[i]=fill; buf.stroke[i]=stroke; buf.lw[i]=lw;
      };

      // ── 골조 ── (10개뿐이라 읽기 쉬운 경로를 그대로 쓴다)
      if (solids) {
        const tone = { core: [150,157,166], slab: [176,183,191],
                       scaffold: [140,160,175], stack: [163,150,130] };
        // 면을 채우면 위층 복셀 색을 덮는다. 골조는 **윤곽 위주**로 그린다.
        const solid2d = this.cam.pitch >= 89;
        d.solids.forEach(b => {
          const c = tone[b.kind] || [160,160,160];
          const faint = b.kind === 'slab' || b.kind === 'scaffold';
          const fillS = rgba(c, solid2d ? 0.18 : (faint ? 0.03 : 0.10));
          const strokeS = rgba(c, faint ? 0.30 : 0.55);
          this._boxFaces(b).forEach(f => {
            const dep = (f[0].depth + f[1].depth + f[2].depth + f[3].depth) / 4;
            push(f[0].x,f[0].y, f[1].x,f[1].y, f[2].x,f[2].y, f[3].x,f[3].y,
                 dep - 0.01, fillS, strokeS, 0.7);
          });
        });
      }

      // ── 복셀 ── 뜨거운 경로
      this._pushVoxels(P, buf, push, flat, single);

      // ── 깊이 정렬 (먼 것부터) ──
      // 비교 정렬 대신 버킷 계수정렬이다. O(n log n) → O(n).
      // 버킷 폭은 깊이 범위/2048 이라 1m 큐브보다 훨씬 잘아 같은 버킷에 든 면은
      // 사실상 같은 깊이다.
      const n = buf.n;
      const order = buf.order, bk = buf.bucket;
      if (n) {
        let lo = Infinity, hi = -Infinity;
        for (let i = 0; i < n; i++) {
          const v = buf.depth[i];
          if (v < lo) lo = v; if (v > hi) hi = v;
        }
        const span = hi - lo || 1;
        const K = DEPTH_BUCKETS;
        bk.fill(0);
        const bi = buf.bi;
        for (let i = 0; i < n; i++) {
          // 먼 것(depth 큰 것)이 먼저 나오도록 뒤집는다
          let b = (K - 1) - ((buf.depth[i] - lo) / span * (K - 1)) | 0;
          if (b < 0) b = 0; else if (b >= K) b = K - 1;
          bi[i] = b; bk[b + 1]++;
        }
        for (let b = 0; b < K; b++) bk[b + 1] += bk[b];
        for (let i = 0; i < n; i++) order[bk[bi[i]]++] = i;
      }

      // ── 그리기 ──
      // 깊이 순서에서 **스타일이 같은 동안은 한 경로에 모아** 한 번에 칠한다.
      // 순서를 바꾸지 않으므로 화가 알고리즘은 그대로다.
      //
      // 색별로 전부 몰아 담는 방식은 시도했다가 버렸다 — 서브패스 2만 개를 한
      // 번에 stroke 하면 420ms 로 **개별 호출(55ms)보다 8배 느리다.** 크롬이
      // 경로 전체의 bbox 로 래스터라이즈 범위를 잡는 탓이다.
      let curFill = null, curStroke = null, curLw = -1, openPath = false;
      const flush = () => {
        if (!openPath) return;
        if (curFill) { ctx.fillStyle = curFill; ctx.fill(); }
        if (curStroke) { ctx.strokeStyle = curStroke; ctx.lineWidth = curLw; ctx.stroke(); }
        openPath = false;
      };
      for (let k = 0; k < n; k++) {
        const i = order[k], o = i * 4;
        const f = buf.fill[i], st = buf.stroke[i], w = buf.lw[i];
        if (!f && !st) continue;
        if (!openPath || f !== curFill || st !== curStroke || w !== curLw) {
          flush();
          ctx.beginPath();
          curFill = f; curStroke = st; curLw = w; openPath = true;
        }
        ctx.moveTo(buf.x[o], buf.y[o]);
        ctx.lineTo(buf.x[o+1], buf.y[o+1]);
        ctx.lineTo(buf.x[o+2], buf.y[o+2]);
        ctx.lineTo(buf.x[o+3], buf.y[o+3]);
        ctx.closePath();
      }
      flush();

      this._drawCameras();
    }

    /* 복셀을 면 버퍼에 채운다.
     *
     * 투영은 (x,y,z) 에 대해 선형이다(원근의 k 만 예외). 그래서 큐브 꼭짓점의
     * 화면 오프셋은 **복셀이 달라도 같다** — 프레임마다 여덟 개만 구해두고
     * 복셀당 중심 하나만 투영해 더한다. 12회가 1회가 된다.
     *
     * 원근 k 는 원래 꼭짓점마다 달랐다. 여기서는 중심의 k 를 여덟 꼭짓점에
     * 함께 쓴다. 큐브 반변이 0.5m 이고 시거리가 160m 라 차이가 0.3% 밑이며,
     * 오히려 큐브가 덜 일그러진다.
     */
    _pushVoxels(P, buf, push, flat, single) {
      const S = this.d.site;
      const f = this._fit;
      const yaw = this.cam.yaw * DEG, pit = this.cam.pitch * DEG;
      const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
      const cpit = Math.cos(pit), spit = Math.sin(pit);
      const zx = this.cam.zx || 1;
      const cx = S.width_m / 2, cy = S.depth_m / 2, pz0 = this._pivotZ || 0;
      const persp = this.cam.persp;
      const dist = Math.max(S.width_m, S.depth_m) * (this.cam.perspK || 1.6);
      const step = S.voxel_m;

      // 꼭짓점 오프셋 (투영 평면 기준, 원근 전)
      const half = (flat ? step : step * 0.86) / 2;
      const ox = new Float64Array(8), oy = new Float64Array(8);
      for (let c = 0; c < 8; c++) {
        const sg = CORNER_SIGN[c];
        const dx = sg[0] * half, dy = sg[1] * half, dz = sg[2] * (flat ? 0 : half) * zx;
        const rx = dx * cyaw - dy * syaw;
        const ry = dx * syaw + dy * cyaw;
        ox[c] = rx;
        oy[c] = ry * spit - dz * cpit;
      }

      // 카메라를 향한 세 면. 종전 _cubeFaces 와 같은 규칙이다.
      const yn = ((this.cam.yaw % 360) + 360) % 360;
      const dirX = (yn > 180) ? 0 : 1;                  // +x 면이 보이는가
      const dirY = (yn > 90 && yn < 270) ? 2 : 3;
      const dirZ = (this.cam.pitch >= 0) ? 4 : 5;
      // 그리는 순서 = 음영 인덱스 순서 [윗면, x옆, y옆]
      const dirs = [dirZ, dirX, dirY];

      const sx = new Float64Array(8), sy = new Float64Array(8);
      const n = P.n;
      for (let i = 0; i < n; i++) {
        const b = P.bnd[i];
        const m = P.open[i];
        // clear 는 윗면 하나만 그린다 — 세 면을 다 그으면 격자 노이즈가 된다
        const nf = (b === CLEAR) ? 1 : 3;
        if (!flat) {
          let any = 0;
          for (let t = 0; t < nf; t++) if (m & (1 << dirs[t])) { any = 1; break; }
          if (!any) continue;              // 껍질 밖 — 안 보이는 복셀
        }

        const dx = P.px[i] - cx, dy = P.py[i] - cy, dz = (P.pz[i] - pz0) * zx;
        const rx = dx * cyaw - dy * syaw;
        const ry = dx * syaw + dy * cyaw;
        const cySc = ry * spit - dz * cpit;
        const depth = ry * cpit + dz * spit;
        const k = persp ? dist / (dist + depth) : 1;
        const ks = k * f.s;

        if (flat) {
          // 2D — 판 하나. 윗면 네 꼭짓점을 z 오프셋 없이 쓴다.
          const cc = FACE_CORNERS[4];
          for (let t = 0; t < 4; t++) {
            const c = cc[t];
            sx[t] = f.ox + (rx + ox[c]) * ks;
            sy[t] = f.oy + (cySc + oy[c]) * ks;
          }
          push(sx[0],sy[0], sx[1],sy[1], sx[2],sy[2], sx[3],sy[3], depth,
               P.fill[0][i], P.stroke[i], P.lw[i]);
          continue;
        }

        for (let c = 0; c < 8; c++) {
          sx[c] = f.ox + (rx + ox[c]) * ks;
          sy[c] = f.oy + (cySc + oy[c]) * ks;
        }
        for (let t = 0; t < nf; t++) {
          const dir = dirs[t];
          if (!(m & (1 << dir))) continue;
          const cc = FACE_CORNERS[dir];
          const a0 = cc[0], a1 = cc[1], a2 = cc[2], a3 = cc[3];
          push(sx[a0],sy[a0], sx[a1],sy[a1], sx[a2],sy[a2], sx[a3],sy[a3],
               depth, P.fill[t][i], P.stroke[i], P.lw[i]);
        }
      }
    }

    _drawCameras() {
      const ctx = this.ctx, d = this.d;
      const chromeInk = Theme.ui('--color-chrome');
      if (!(this.opts.showCams && d.cameras)) return;
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
          // 카메라는 **데이터가 아니라 주석**이다. 램프의 파랑을 쓰면 통과극과
          // 섞인다(검증기 ΔE 4.9). UI 크롬은 전부 무채색으로 내린다.
          ctx.fillStyle = rgba(chromeInk, 0.10); ctx.fill();
          ctx.strokeStyle = rgba(chromeInk, 0.38); ctx.lineWidth = 1; ctx.stroke();
          // 설치 높이를 기둥으로 — 3D 에서 카메라가 떠 있는 게 보여야 한다
          ctx.beginPath(); ctx.moveTo(g.x, g.y); ctx.lineTo(p.x, p.y);
          ctx.strokeStyle = rgba(chromeInk, 0.42); ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, on ? 5 : 3, 0, Math.PI * 2);
        ctx.fillStyle = on ? Theme.css(chromeInk) : Theme.css(Theme.ui('--color-rule'));
        ctx.fill();
        ctx.strokeStyle = Theme.css(Theme.ui('--color-paper-2'));
        ctx.lineWidth = 1.5; ctx.stroke();
      });
    }
  }

  global.CoverageViewer = { Viewer, PRESETS, heat };
})(window);
