/* 현장 평면도 — 평가 대상이 무엇인지 먼저 보여주는 화면.
 *
 * 나머지 화면은 전부 **결과**(히트맵·미달구역·WDR)다. 그런데 심사자가 먼저
 * 묻는 것은 "그래서 어떤 현장을 잰 건가" 다. 그 입력을 보여주는 화면이 없었다.
 *
 * **골조는 실제 도면에서 왔다** (2026-08-27 정정). 종전에는 site_model.py 가
 * 수치를 박아 만든 가상 현장이었고 이 주석도 그렇게 적혀 있었다. 지금은
 * 신내역 금강펜테리움 센트럴파크의 건축물현황도를 축척 1:2000 으로 읽어
 * data/building.json 에 옮긴 것이다. **카메라 배치만 실제 계획서가 아니다** —
 * 경계 등간격의 실무 관행 모사이며, 화면에도 그렇게 적는다.
 *
 * 새 수치를 만들지 않는다. solids 의 kind, voxels 의 zones, cameras 의 yaw_deg
 * 를 그대로 읽어 그린다.
 */
(function (global) {
  'use strict';

  const DEG = Math.PI / 180;

  // 골조 종류별 표기. 도면이므로 채우기보다 선으로 구분한다.
  /* **골조는 무채색으로 내렸다.** 종전 비계 파랑·적치물 황토는 히트맵 판정
   * 램프(적↔회색↔청)와 겹쳐, 방금 히트맵을 본 사람에게 도면의 파랑이
   * "통과"로 읽혔다. 도면은 원래 선 두께·파선·해칭으로 구분한다 — 색은
   * 위험구역에만 남긴다. */
  const KINDS = {
    core:     { label: '코어 벽체',   line: '#16191d', fill: 'rgba(22,25,29,.14)',  w: 1.6, hatch: true },
    slab:     { label: '슬래브',      line: '#5c6570', fill: 'rgba(92,101,112,.05)', w: 1.0, dash: [6, 4] },
    scaffold: { label: '외곽 비계',   line: '#3b424b', fill: 'rgba(59,66,75,.07)',   w: 1.2, dash: [2, 3] },
    stack:    { label: '적치물',      line: '#6b7280', fill: 'rgba(107,114,128,.10)', w: 1.0 },
  };

  /* 위험구역은 **황토 70° 한 색상의 명도 계단**이다. 가중치 5 가 가장 진하다.
   * 종전의 적·주·청·녹·황토 다섯 색상은 두 가지가 틀렸다 — 램프와 색이 겹쳤고,
   * 가중치가 1~5 순서형인데 임의 색상이라 순서가 사라졌다. 램프가 쓰지 않는
   * 색상 하나에 순서를 명도로 싣는다. */
  const ZONES = {
    gangform_workface:  { label: '갱폼 작업면 (5)',     c: '#6d4a06' },
    opening_perimeter:  { label: '개구부 주변 (5)',     c: '#6d4a06' },
    lift_landing:       { label: '리프트 승강구 (4)',   c: '#8a6212' },
    tower_crane_radius: { label: '타워크레인 반경 (3)', c: '#a67f2c' },
    material_yard:      { label: '자재 야적장 (2)',     c: '#c2a05c' },
  };

  const MOUNTS = {
    boundary_pole: '경계 폴',
    core_top:      '코어 상부',
    tower_crane:   '타워크레인',
  };

  class SitePlan {
    constructor(canvas, data, opts) {
      this.cv = canvas;
      this.ctx = canvas.getContext('2d');
      this.d = data;
      this.opts = Object.assign({ chosen: [], showZones: true, showCams: true }, opts || {});
      // resize 리스너를 여기서 달지 않는다. render() 가 캔버스를 다시 만들며
      // 인스턴스도 새로 생기는데, 그때마다 붙이면 죽은 캔버스를 붙든 핸들러가
      // 쌓인다. 바깥에서 한 번만 등록해 PLAN.resize() 를 부른다.
      this.resize();
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

    /* 현장 좌표(m) → 화면(px). y 를 뒤집어 도면 관례대로 위가 +y 다. */
    _fit() {
      const S = this.d.site;
      const pad = { l: 46, r: 20, t: 20, b: 42 };   // 치수선·범례 자리
      const s = Math.min((this.W - pad.l - pad.r) / S.width_m,
                         (this.H - pad.t - pad.b) / S.depth_m);
      const w = S.width_m * s, h = S.depth_m * s;
      return { s, ox: pad.l + ((this.W - pad.l - pad.r) - w) / 2,
                  oy: pad.t + ((this.H - pad.t - pad.b) - h) / 2, w, h };
    }
    _p(x, y) {
      const f = this.f;
      return { x: f.ox + x * f.s, y: f.oy + f.h - y * f.s };
    }

    draw() {
      const ctx = this.ctx, d = this.d, S = d.site;
      if (!ctx) return;
      this.f = this._fit();
      ctx.clearRect(0, 0, this.W, this.H);

      this._grid();
      if (this.opts.showZones) this._zones();
      this._solids();
      this._boundary();
      this._dims();
      if (this.opts.showCams) this._cameras();
    }

    /* 10m 격자 — 도면의 눈금이다. 복셀 격자(2m)와 혼동되지 않게 성기게 둔다. */
    _grid() {
      const ctx = this.ctx, S = this.d.site;
      ctx.save();
      ctx.strokeStyle = '#e7ebef'; ctx.lineWidth = 1;
      for (let x = 0; x <= S.width_m; x += 10) {
        const a = this._p(x, 0), b = this._p(x, S.depth_m);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      for (let y = 0; y <= S.depth_m; y += 10) {
        const a = this._p(0, y), b = this._p(S.width_m, y);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.restore();
    }

    /* 위험구역 — 복셀에 붙은 zones 태그의 발자국이다.
     * 층을 합쳐 union 으로 그린다. 평면도에서 "어디가 위험한가" 만 보이면 된다. */
    _zones() {
      const ctx = this.ctx, d = this.d, hs = d.site.voxel_m / 2;
      const seen = {};                       // zone → Set("x,y")
      d.voxels.forEach(v => {
        (v.zones || []).forEach(z => {
          (seen[z] || (seen[z] = new Set())).add(v.x + ',' + v.y);
        });
      });
      ctx.save();
      Object.keys(seen).forEach(z => {
        const st = ZONES[z] || { c: '#5c6570' };
        ctx.fillStyle = st.c; ctx.globalAlpha = 0.13;
        seen[z].forEach(k => {
          const [x, y] = k.split(',').map(Number);
          const a = this._p(x - hs, y + hs);
          ctx.fillRect(a.x, a.y, hs * 2 * this.f.s, hs * 2 * this.f.s);
        });
      });
      ctx.restore();
    }

    _solids() {
      const ctx = this.ctx;
      // 아래에서 위로 — 슬래브를 먼저 깔고 벽체·비계를 얹는다
      const order = ['slab', 'stack', 'scaffold', 'core'];
      const list = (this.d.solids || []).slice()
        .sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
      list.forEach(b => {
        const st = KINDS[b.kind] || { line: '#5c6570', fill: 'rgba(0,0,0,.06)', w: 1 };
        const p1 = this._p(b.x1, b.y2), p2 = this._p(b.x2, b.y1);
        const w = p2.x - p1.x, h = p2.y - p1.y;
        ctx.save();
        /* **사선으로 앉은 동을 눕혀 그리지 않는다** (2026-08-27).
         *
         * `yaw_deg` 는 계산에는 줄곧 들어갔는데(geometry 가 광선을 상자의 로컬
         * 좌표로 돌려 푼다) 그리기만 축정렬로 남아 있었다. 404·405동이
         * -24°/-27° 라, 도면에는 반듯한 건물이 서 있는데 히트맵에는 비스듬한
         * 그림자가 지는 어긋남이 났다. 상자 중심을 축으로 돌린다.
         * 화면 y 가 아래로 가므로 부호가 반대다. */
        if (b.yaw_deg) {
          const cx = p1.x + w / 2, cy = p1.y + h / 2;
          ctx.translate(cx, cy); ctx.rotate(-b.yaw_deg * DEG); ctx.translate(-cx, -cy);
        }
        ctx.fillStyle = st.fill; ctx.fillRect(p1.x, p1.y, w, h);
        if (st.hatch) {                       // 코어는 해칭 — 도면 관례
          ctx.save();
          ctx.beginPath(); ctx.rect(p1.x, p1.y, w, h); ctx.clip();
          ctx.strokeStyle = 'rgba(22,25,29,.35)'; ctx.lineWidth = 0.8;
          for (let i = -h; i < w; i += 7) {
            ctx.beginPath(); ctx.moveTo(p1.x + i, p1.y + h); ctx.lineTo(p1.x + i + h, p1.y);
            ctx.stroke();
          }
          ctx.restore();
        }
        ctx.strokeStyle = st.line; ctx.lineWidth = st.w;
        ctx.setLineDash(st.dash || []);
        ctx.strokeRect(p1.x, p1.y, w, h);
        ctx.restore();
      });
    }

    _boundary() {
      const ctx = this.ctx, S = this.d.site;
      const a = this._p(0, S.depth_m), b = this._p(S.width_m, 0);
      ctx.save();
      ctx.strokeStyle = '#16191d'; ctx.lineWidth = 1.8;
      ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
      ctx.restore();
    }

    /* 치수선과 축척 — 도면으로 읽히려면 이게 있어야 한다. */
    _dims() {
      const ctx = this.ctx, S = this.d.site, f = this.f;
      ctx.save();
      ctx.strokeStyle = '#5c6570'; ctx.fillStyle = '#5c6570';
      ctx.lineWidth = 1; ctx.font = '11px ui-monospace,Menlo,Consolas,monospace';

      const bot = f.oy + f.h + 20;
      ctx.beginPath(); ctx.moveTo(f.ox, bot); ctx.lineTo(f.ox + f.w, bot); ctx.stroke();
      [[f.ox, bot], [f.ox + f.w, bot]].forEach(([x, y]) => {
        ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4); ctx.stroke();
      });
      ctx.textAlign = 'center';
      ctx.fillText(S.width_m + ' m', f.ox + f.w / 2, bot + 14);

      const lft = f.ox - 22;
      ctx.beginPath(); ctx.moveTo(lft, f.oy); ctx.lineTo(lft, f.oy + f.h); ctx.stroke();
      [[lft, f.oy], [lft, f.oy + f.h]].forEach(([x, y]) => {
        ctx.beginPath(); ctx.moveTo(x - 4, y); ctx.lineTo(x + 4, y); ctx.stroke();
      });
      ctx.save();
      ctx.translate(lft - 6, f.oy + f.h / 2); ctx.rotate(-Math.PI / 2);
      ctx.fillText(S.depth_m + ' m', 0, 0);
      ctx.restore();

      // 방위 — 도면에는 북이 있어야 한다. +y 를 북으로 둔다(도면 좌표계의 규약)
      const nx = f.ox + f.w - 14, ny = f.oy + 14;
      ctx.strokeStyle = '#16191d'; ctx.fillStyle = '#16191d';
      ctx.beginPath(); ctx.moveTo(nx, ny + 12); ctx.lineTo(nx, ny - 6);
      ctx.lineTo(nx - 3.5, ny - 1); ctx.moveTo(nx, ny - 6); ctx.lineTo(nx + 3.5, ny - 1);
      ctx.stroke();
      ctx.textAlign = 'center'; ctx.fillText('N', nx, ny + 24);
      ctx.restore();
    }

    /* 카메라 — 후보 24 는 흐리게, 선정분은 진하게 + 화각 부채꼴. */
    _cameras() {
      const ctx = this.ctx, d = this.d;
      const hf = ((d.aim && d.aim.hfov_deg) || 90) * DEG / 2;
      const chosen = new Set(this.opts.chosen || []);
      const R = 14;                                  // 부채꼴 길이(m)

      (d.cameras || []).forEach(c => {
        const on = chosen.has(c.id);
        const p = this._p(c.x, c.y);
        if (on && c.yaw_deg !== undefined && c.yaw_deg !== null) {
          const a = c.yaw_deg * DEG;
          ctx.save();
          ctx.beginPath(); ctx.moveTo(p.x, p.y);
          for (let t = -hf; t <= hf + 1e-6; t += hf / 8) {
            const q = this._p(c.x + R * Math.cos(a + t), c.y + R * Math.sin(a + t));
            ctx.lineTo(q.x, q.y);
          }
          ctx.closePath();
          ctx.fillStyle = 'rgba(59,66,75,.10)'; ctx.fill();
          ctx.strokeStyle = 'rgba(59,66,75,.38)'; ctx.lineWidth = 0.8; ctx.stroke();
          ctx.restore();
        }
        ctx.save();
        ctx.beginPath(); ctx.arc(p.x, p.y, on ? 5 : 3, 0, Math.PI * 2);
        ctx.fillStyle = on ? '#3b424b' : '#c3cad2';
        ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.restore();
      });
    }

    /* 범례 HTML — 캔버스 밖에 둔다. 도면 위에 글자를 얹으면 지저분하다. */
    legendHTML() {
      const kinds = new Set((this.d.solids || []).map(b => b.kind));
      const zs = new Set();
      (this.d.voxels || []).forEach(v => (v.zones || []).forEach(z => zs.add(z)));
      const mounts = {};
      (this.d.cameras || []).forEach(c => { mounts[c.mount] = (mounts[c.mount] || 0) + 1; });

      const sw = (css) => `<span class="sw" style="${css}"></span>`;
      const parts = [];
      [...kinds].forEach(k => {
        const st = KINDS[k]; if (!st) return;
        parts.push(sw(`background:${st.fill};border:1px solid ${st.line}`) + st.label);
      });
      [...zs].forEach(z => {
        const st = ZONES[z]; if (!st) return;
        parts.push(sw(`background:${st.c};opacity:.35`) + st.label);
      });
      const mtxt = Object.entries(mounts)
        .map(([k, n]) => `${MOUNTS[k] || k} ${n}`).join(' · ');
      return parts.join(' ') +
        `<span style="margin-left:10px">카메라 후보 ${(this.d.cameras || []).length}
         (${mtxt}) · 진한 점 = 선정 ${(this.opts.chosen || []).length}대, 부채꼴 = 수평화각
         ${(this.d.aim && this.d.aim.hfov_deg) || 90}°</span>`;
    }
  }

  global.SitePlan = { SitePlan, KINDS, ZONES, MOUNTS };
})(window);
