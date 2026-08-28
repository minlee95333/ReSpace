/* 검출확률 엔진 — 브라우저판 (2026-08-22)
 *
 * 사용자가 CCTV 를 직접 놓으므로 미리 계산해 둔 배치가 없다. 놓는 즉시 브라우저가
 * 계산한다. `src/geometry.py` 와 `src/detect_model.py` 를 옮긴 것이며,
 * **값이 갈리면 화면과 보고서가 다른 말을 하게 되므로** tools/test_engine.mjs 가
 * Python 산출값(tools/fixture_engine.json)과 대조한다.
 *
 * 성능 — 기본 현장은 솔리드 4개뿐이라 카메라 1대가 79,392복셀에 대해 Python 에서
 * 2.36초다. 여기서는 그보다 빠르다.
 *
 * 결합은 1-Π(1-P) 다. 중첩은 이득이며 페널티가 아니다(CLAUDE.md §5.3).
 * 카메라를 더하고 빼는 것이 miss 벡터의 곱하기·나누기 한 번이라 증분이 공짜다.
 */
(function (global) {
  'use strict';

  const DEG = Math.PI / 180;

  // Python 의 geometry.pair 가 기록할 때 쓰는 것과 같은 자리에서 반올림한다.
  // 곡선에 넣기 전에 맞춰야 두 구현의 값이 갈리지 않는다.
  const round1 = (v) => Math.round(v * 10) / 10;
  const round2 = (v) => Math.round(v * 100) / 100;
  const round3 = (v) => Math.round(v * 1000) / 1000;

  /* ── 런렝스 펴기 ──────────────────────────────────────────────────────── */
  function expandRLE(rle, n) {
    const out = new Float64Array(n);
    let i = 0;
    for (const pair of rle) {
      const val = pair[0], cnt = pair[1];
      for (let k = 0; k < cnt; k++) out[i++] = val;
    }
    if (i !== n) throw new Error('RLE 길이가 ' + i + ', 기대 ' + n);
    return out;
  }

  /* ── 현장 ─────────────────────────────────────────────────────────────── */
  class Site {
    constructor(d) {
      this.d = d;
      const S = d.site, V = d.voxels;
      this.n = V.count;
      this.s = S.voxel_m;
      this.nx = S.nx;
      this.ny = S.ny;

      // 좌표는 싣지 않는다. 격자 인덱스에서 되살린다 (site.json 이 28MB -> 0.47MB)
      this.x = new Float64Array(this.n);
      this.y = new Float64Array(this.n);
      this.z = new Float64Array(this.n);
      for (let t = 0; t < this.n; t++) {
        const idx = V.index[t];
        const i = idx % this.nx;
        const j = Math.floor(idx / this.nx) % this.ny;
        const k = Math.floor(idx / (this.nx * this.ny));
        this.x[t] = (i + 0.5) * this.s;
        this.y[t] = (j + 0.5) * this.s;
        this.z[t] = (k + 0.5) * this.s;
      }
      // 입력 전에는 전부 살아 있다. 가설물이 들어오면 그 안쪽이 죽는다.
      this.alive = new Uint8Array(this.n).fill(1);
      this.zones = [];
      this.obstructions = [];
      this.occupiable = expandRLE(V.occupiable_rle, this.n);
      this.w = expandRLE(V.w_rle, this.n);
      this.level = expandRLE(V.level_rle, this.n);
      // 사람이 딛고 서는 면. 막대 밑동이다. 없으면 상부층 가림이 통째로 틀린다.
      this.standZ = expandRLE(V.stand_z_rle, this.n);

      this.solids = d.solids;
      this.groups = groupSolids(d.solids);   // 광선 판정은 묶음으로 한다

      // 지표의 분모는 사람이 있을 수 있는 자리뿐이다. 허공은 빠진다.
      this.wSum = 0;
      this.liveCount = 0;
      for (let t = 0; t < this.n; t++) {
        if (this.occupiable[t]) { this.wSum += this.w[t]; this.liveCount++; }
      }

      const C = d.camera;
      // f_px = (W/2) / tan(HFOV/2),  rho = f_px * H_head / d
      this.fPx = (C.img_w / 2) / Math.tan(C.hfov_deg * DEG / 2);
      this.hHead = C.h_head_m;
      this.halfHfov = C.hfov_deg / 2;
      this.occSamples = C.occ_samples;
      this.occBarH = C.occ_bar_h_m;
    }
  }

  /* ── 광선-상자 교차 (슬랩 방식). geometry._ray_hits_box 와 같다 ────────── */
  /* 세계 좌표 → 상자 중심 기준 로컬 좌표.
   * `src/site_model.py` 의 Box.to_local_xy 와 **부호까지 같아야 한다** —
   * 갈리면 사선 동의 가림이 반대편으로 계산되고 test_engine.mjs 가 잡는다. */
  function toLocalXY(b, x, y) {
    const cx = (b.x1 + b.x2) / 2, cy = (b.y1 + b.y2) / 2;
    const dx = x - cx, dy = y - cy;
    if (!b.yaw_deg) return [dx, dy];
    const r = b.yaw_deg * DEG, c = Math.cos(r), s = Math.sin(r);
    return [dx * c + dy * s, -dx * s + dy * c];
  }

  function rayHitsBox(p0, p1, b) {
    let tMin = 0.0, tMax = 1.0;
    let lo, hi;
    if (b.yaw_deg) {
      // 회전 상자는 두 끝점을 로컬 좌표로 옮겨 같은 슬랩 판정을 쓴다
      // (src/geometry.py `_ray_hits_box`). 404·405동이 사선 배치라 필요하다.
      const a = toLocalXY(b, p0[0], p0[1]);
      const c = toLocalXY(b, p1[0], p1[1]);
      p0 = [a[0], a[1], p0[2]];
      p1 = [c[0], c[1], p1[2]];
      const hx = (b.x2 - b.x1) / 2, hy = (b.y2 - b.y1) / 2;
      lo = [-hx, -hy, b.z1];
      hi = [hx, hy, b.z2];
    } else {
      lo = [b.x1, b.y1, b.z1];
      hi = [b.x2, b.y2, b.z2];
    }
    for (let i = 0; i < 3; i++) {
      const o = p0[i], dd = p1[i] - p0[i];
      if (Math.abs(dd) < 1e-12) {
        if (o < lo[i] || o > hi[i]) return false;
        continue;
      }
      let t1 = (lo[i] - o) / dd, t2 = (hi[i] - o) / dd;
      if (t1 > t2) { const t = t1; t1 = t2; t2 = t; }
      tMin = Math.max(tMin, t1);
      tMax = Math.min(tMax, t2);
      if (tMin > tMax) return false;
    }
    return true;
  }

  /* 복셀에 세운 사람 막대가 얼마나 가려지는가.
   *
   * `standZ` 는 딛는 면의 높이이며 막대는 거기서 시작한다. 종전 Python 구현은
   * 이 인자가 없어 막대를 항상 지면에 세웠고, 상부층 가림이 틀렸다(2026-08-22 수정).
   *
   * 여러 겹을 지나면 가장 많이 막는 것을 쓴다 — 곱으로 누적하면 비계 두 겹만
   * 지나도 사실상 불투명이 되어 실제보다 어둡게 잡힌다.
   */
  /* 같은 평면(xy·yaw)을 공유하는 솔리드를 묶는다.
   *
   * **왜.** 동 하나가 층마다 슬래브를 갖는다. 도면에서 요철을 살리면서
   * 평면 상자가 59개가 됐고, 층 5개를 곱해 솔리드가 271개가 됐다(종전 59).
   * 광선 하나가 어떤 평면을 비껴가면 그 평면의 층 전부를 비껴간다 - 그런데
   * 층마다 따로 물어보고 있었다. 카메라 한 대가 9.4초까지 늘어났다.
   *
   * 묶음 상자는 근사가 아니다 - xy 와 yaw 가 같으므로 z 만 위아래로 편
   * **정확한 합집합**이다. 그래서 값이 바뀌지 않는다
   * (tools/test_engine.mjs 가 Python 과 대조해 확인한다). */
  function groupSolids(solids) {
    const by = new Map();
    for (const b of solids) {
      const k = b.x1 + ',' + b.y1 + ',' + b.x2 + ',' + b.y2 + ',' + (b.yaw_deg || 0);
      let g = by.get(k);
      if (!g) { by.set(k, g = { x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2,
                                yaw_deg: b.yaw_deg || 0,
                                z1: b.z1, z2: b.z2, members: [] }); }
      if (b.z1 < g.z1) g.z1 = b.z1;
      if (b.z2 > g.z2) g.z2 = b.z2;
      g.members.push(b);
    }
    // 많이 막는 묶음을 먼저 본다 - best 가 1.0 에 빨리 닿아 조기 종료가 는다.
    const out = [...by.values()];
    out.forEach(g => {
      g.maxCov = Math.max(...g.members.map(m => m.coverage));
      // 회전을 반영한 세계 xy 범위. 광선의 xy 범위와 겹치지 않으면 그 광선은
      // 이 묶음을 맞힐 수 없다 - 근사가 아니라 정확한 배제다.
      const cx = (g.x1 + g.x2) / 2, cy = (g.y1 + g.y2) / 2;
      const r = (g.yaw_deg || 0) * DEG, co = Math.cos(r), si = Math.sin(r);
      let X0 = Infinity, Y0 = Infinity, X1 = -Infinity, Y1 = -Infinity;
      for (const [x, y] of [[g.x1,g.y1],[g.x2,g.y1],[g.x2,g.y2],[g.x1,g.y2]]) {
        const dx = x - cx, dy = y - cy;
        const wx = cx + dx * co - dy * si, wy = cy + dx * si + dy * co;
        if (wx < X0) X0 = wx; if (wx > X1) X1 = wx;
        if (wy < Y0) Y0 = wy; if (wy > Y1) Y1 = wy;
      }
      g.bx0 = X0; g.by0 = Y0; g.bx1 = X1; g.by1 = Y1;
    });
    out.sort((a, b) => b.maxCov - a.maxCov);
    return out;
  }

  function occlusionRatio(vx, vy, cam, groups, standZ, n, barH) {
    let total = 0.0;
    const p1 = [cam.x, cam.y, cam.z];
    /* **광선의 xy 범위로 먼저 쳐낸다.**
     *
     * 표본점 11개는 xy 가 모두 같다(막대는 연직이다). 그러니 후보 추리기는
     * 복셀당 한 번이면 된다. 단지가 넓어 어떤 광선이든 대부분의 묶음과
     * 무관한데, 종전에는 전부에게 슬랩 판정을 물었다. */
    const rx0 = vx < cam.x ? vx : cam.x, rx1 = vx < cam.x ? cam.x : vx;
    const ry0 = vy < cam.y ? vy : cam.y, ry1 = vy < cam.y ? cam.y : vy;
    const near = [];
    for (let gi = 0; gi < groups.length; gi++) {
      const g = groups[gi];
      if (g.bx1 < rx0 || g.bx0 > rx1 || g.by1 < ry0 || g.by0 > ry1) continue;
      near.push(g);
    }
    if (!near.length) return 0.0;
    for (let i = 0; i < n; i++) {
      const p0 = [vx, vy, standZ + barH * i / (n - 1)];
      let best = 0.0;
      for (let gi = 0; gi < near.length; gi++) {
        const g = near[gi];
        if (g.maxCov <= best) continue;           // 이 묶음으로는 더 못 막는다
        if (!rayHitsBox(p0, p1, g)) continue;     // 평면을 비껴갔다 - 층 전부 건너뛴다
        const ms = g.members;
        if (ms.length === 1) { if (ms[0].coverage > best) best = ms[0].coverage; }
        else for (let m = 0; m < ms.length; m++) {
          const b = ms[m];
          if (b.coverage > best && rayHitsBox(p0, p1, b)) best = b.coverage;
        }
        // 속 찬 것에 한 번 막히면 더 볼 것이 없다 — 가장 많이 막는 것을 쓰므로
        // 1.0 을 넘길 수 있는 솔리드가 없다. 골조 뒤 복셀에서 크게 아낀다.
        if (best >= 1.0) break;
      }
      total += best;
    }
    return total / n;
  }

  function bearingDeg(cam, vx, vy) {
    const a = Math.atan2(vy - cam.y, vx - cam.x) / DEG;
    return ((a % 360) + 360) % 360;
  }

  function inFov(bearing, yaw, halfHfov) {
    const diff = Math.abs(((((bearing - yaw + 180) % 360) + 360) % 360) - 180);
    return diff <= halfHfov;
  }

  /* ── 곡선 ─────────────────────────────────────────────────────────────── */
  class Curve {
    constructor(c) {
      const f = c.f_rho;
      this.L = f.L; this.k = f.k; this.x0 = f.x0;
      this.rhoMin = f.measured_range_px[0];
      this.rhoMax = f.measured_range_px[1];

      const g = c.g_theta;
      this.gForm = g.form;
      this.gParams = g.params;
      this.thetaMax = (g.measured_range_deg || [0, 90])[1];

      const h = c.h_occ;
      this.lam = h.lambda;
      this.occMax = (h.measured_range || [0, 1])[1];
    }

    /* 세 축 모두 측정 범위 밖으로 외삽하지 않는다. 밖이면 0 이다. */
    f(rho) {
      if (rho < this.rhoMin) return 0.0;
      const r = Math.min(rho, this.rhoMax);   // 위쪽은 포화라 잘라도 무해하다
      return this.L / (1.0 + Math.exp(-this.k * (r - this.x0)));
    }

    g(theta) {
      if (theta > this.thetaMax) return 0.0;
      let v;
      if (this.gForm === 'quadratic') {
        v = 1.0 + this.gParams.a * theta + this.gParams.b * theta * theta;
      } else if (this.gForm === 'logistic') {
        const k = this.gParams.k, x0 = this.gParams.x0;
        v = (1.0 + Math.exp(-k * x0)) / (1.0 + Math.exp(k * (theta - x0)));
      } else {
        v = Math.exp(-this.gParams.lambda * theta);
      }
      return Math.max(0, Math.min(1, v));
    }

    h(occ) {
      if (occ > this.occMax) return 0.0;
      return Math.max(0, Math.min(1, Math.exp(-this.lam * occ)));
    }
  }

  /* ── 엔진 ─────────────────────────────────────────────────────────────── */
  class Engine {
    constructor(data) {
      this.site = new Site(data);
      this.curve = new Curve(data.curve);
      this.threshold = data.threshold;
      this.cams = [];     // 사용자가 놓은 카메라
      this.cols = [];     // 카메라별 P 열
      this.visCols = [];  // 카메라별 관측 가능 열 (1/0)
      this.miss = new Float64Array(this.site.n).fill(1);
    }

    /* 위험구역·가설계획 입력이 바뀌었다.
     *
     * 복셀의 성질이 전부 달라진다 — 가설물 안쪽은 없어지고, 설 자리가 늘고,
     * 딛는 면이 옮겨가고, 가중치가 붙는다. 가림원(solids)도 늘어난다.
     * **놓아 둔 카메라의 P 열이 전부 무효가 되므로 다시 계산한다.**
     *
     * 규칙은 site_rules.js 에 있다 — src/site_model.py 를 옮긴 것이고
     * tools/test_rules.mjs 가 Python 값과 대조한다.
     */
    setInputs(zones, obstructions) {
      var r = SiteRules.recompute(this.site.d, zones, obstructions);
      var S = this.site;
      S.alive = r.alive;
      S.occupiable = r.occupiable;
      S.w = r.w;
      S.standZ = r.standZ;
      S.solids = r.solids;
      S.groups = groupSolids(r.solids);
      S.zones = zones || [];
      S.obstructions = obstructions || [];

      // 지표의 분모를 다시 센다. 없어진 복셀은 빠진다.
      S.wSum = 0; S.liveCount = 0;
      for (var t = 0; t < S.n; t++) {
        if (S.alive[t] && S.occupiable[t]) { S.wSum += S.w[t]; S.liveCount++; }
      }
      this.visCols = this.cams.map(function () {
        return new Uint8Array(this.site.n);
      }, this);
      this.cols = this.cams.map(function (c, i) {
        return this.column(c, this.visCols[i]);
      }, this);
      this.rebuild();
      return this.metrics();
    }

    /* 카메라 하나가 전 복셀에 대해 만드는 검출확률 열.
     * geometry.pair 와 같은 순서로 판정한다 — 화각 밖이면 즉시 0,
     * 완전 차폐면 0, 그 다음에 곡선을 적용한다. */
    column(cam, visOut) {
      const S = this.site, C = this.curve;
      const out = new Float64Array(S.n);
      for (let t = 0; t < S.n; t++) {
        if (!S.alive[t]) continue;              // 가설물 안 — 없는 복셀이다
        // **사람이 못 서는 자리는 아예 계산하지 않는다** (2026-08-27).
        // metrics() 가 occupiable 만 세고, 관측 가능 판정도 작업자 위치 가능
        // 공간을 대상으로 한다(제안서 6.7.1). Python 쪽도 그 자리에 확률을
        // 두지 않고 None 을 넣는다(aggregate.evaluate). 값이 쓰이지 않는데
        // 광선만 쏘고 있었다 — 이 현장에서 복셀의 67% 가 그것이다.
        if (!S.occupiable[t]) continue;
        const vx = S.x[t], vy = S.y[t], vz = S.z[t];
        const dx = vx - cam.x, dy = vy - cam.y, dz = vz - cam.z;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d < 1e-6) continue;
        if (!inFov(bearingDeg(cam, vx, vy), cam.yaw, S.halfHfov)) continue;

        const occ = round3(occlusionRatio(vx, vy, cam, S.groups, S.standZ[t],
                                          S.occSamples, S.occBarH));
        if (occ >= 1.0) continue;               // 완전 차폐
        // **관측 가능**은 여기까지다 — 화각 안이고 완전 차폐가 아니면 보인다.
        // AI 성능은 아직 보지 않는다(제안서 6.2). 곡선이 0 을 주는 것과
        // 안 보이는 것은 다른 이야기라 따로 기록한다.
        if (visOut) visOut[t] = 1;

        const rho = round2(S.fPx * S.hHead / d);
        const sin = Math.max(-1, Math.min(1, (cam.z - vz) / d));
        const theta = round1(Math.asin(sin) / DEG);
        out[t] = C.f(rho) * C.g(theta) * C.h(occ);
      }
      return out;
    }

    add(cam) {
      const vis = new Uint8Array(this.site.n);
      const col = this.column(cam, vis);
      this.cams.push(cam);
      this.cols.push(col);
      this.visCols.push(vis);
      for (let t = 0; t < this.miss.length; t++) this.miss[t] *= (1 - col[t]);
      return this.metrics();
    }

    /* 카메라를 빼는 것은 다시 곱해 되돌리는 것이다.
     * P=1 인 항이 있으면 나눗셈이 0 으로 나누기가 되므로 그때만 전체를 다시 짓는다. */
    remove(i) {
      const col = this.cols[i];
      this.cams.splice(i, 1);
      this.cols.splice(i, 1);
      this.visCols.splice(i, 1);
      let safe = true;
      for (let t = 0; t < col.length; t++) {
        if (col[t] >= 1 - 1e-12) { safe = false; break; }
      }
      if (this.cams.length === 0) {
        // 곱하기·나누기를 되풀이하면 잔차가 남는다(실측 2.2e-16). 그 자체는
        // 무해하나 WDR 이 -8.4e-19 처럼 **음수**로 나와 화면에 -0.0000000% 가
        // 찍힌다. 카메라가 없으면 정의상 정확히 1 이므로 그때는 다시 세운다.
        this.miss.fill(1);
      } else if (safe) {
        for (let t = 0; t < this.miss.length; t++) this.miss[t] /= (1 - col[t]);
      } else {
        this.rebuild();
      }
      return this.metrics();
    }

    rebuild() {
      this.miss = new Float64Array(this.site.n).fill(1);
      for (const col of this.cols) {
        for (let t = 0; t < col.length; t++) this.miss[t] *= (1 - col[t]);
      }
    }

    /* 복셀마다 **몇 대가 관측하는가**. 검출확률과 다른 이야기다 —
     * 보이지만 AI 가 못 알아보는 자리가 있고, 그 구분이 제안서 6.2~6.3 의
     * 뼈대다. 0 = 관측 불가, 1 = 한 대, 2 이상 = 중복 관측. */
    visCount() {
      const n = this.site.n;
      const out = new Uint8Array(n);
      for (const v of this.visCols) {
        for (let t = 0; t < n; t++) out[t] += v[t];
      }
      return out;
    }

    /* P_total = 1 - Π(1-P). 중첩은 이득이다 — 0.35 짜리 두 대가 0.58 이 된다. */
    pTotal() {
      const p = new Float64Array(this.site.n);
      // 잔차로 [0,1] 을 벗어나는 것을 막는다. 확률이 음수로 표시되면 안 된다.
      for (let t = 0; t < p.length; t++) {
        p[t] = Math.max(0, Math.min(1, 1 - this.miss[t]));
      }
      return p;
    }

    metrics() {
      const S = this.site, thr = this.threshold;
      const p = this.pTotal();
      let wp = 0, wOk = 0, nOk = 0;
      for (let t = 0; t < S.n; t++) {
        if (!S.alive[t] || !S.occupiable[t]) continue;   // 허공은 분모에서 빠진다
        wp += S.w[t] * p[t];
        if (p[t] >= thr) { wOk += S.w[t]; nOk++; }
      }
      return {
        n_cameras: this.cams.length,
        WDR: S.wSum ? wp / S.wSum : null,
        risk_coverage: S.wSum ? wOk / S.wSum : null,
        spatial_coverage: S.liveCount ? nOk / S.liveCount : null,
        covered_voxels: nOk,
        fail_voxels: S.liveCount - nOk,
        denominator_voxels: S.liveCount,
      };
    }
  }

  global.CoverageEngine = {
    Engine, Site, Curve,
    rayHitsBox, occlusionRatio, bearingDeg, inFov, expandRLE,
    round1, round2, round3,
  };
})(typeof window !== 'undefined' ? window : globalThis);
