/* 설치 가능 위치 판정 (2026-08-22, 2026-08-23 개정)
 *
 * 사용자가 높이를 정하면 **그 높이에 설치할 수 있는 자리**가 정해진다.
 * 자리는 네 가지로 생긴다.
 *
 *   ① 가설 장비 위  입력된 장비의 그 지점에서만. 타워크레인이 여기 온다
 *   ② 구조물 상부   그 구조물 상단 높이(±snap)에서만. 슬래브 윗면·코어 옥상
 *   ③ 구조체 측면   벽면·단부에 브래킷. **테두리 선** 위이며 그 구조체의
 *                   높이 범위 안이면 된다
 *   ④ 폴           지면에 세운다. 골조 밖이면 어디든. 폴 높이 범위 안일 때만
 *
 * **한 가지만 돌려주지 않는다 (2026-08-23).** 종전에는 우선순위가 높은 하나만
 * 돌려주었고, 그래서 슬래브 상단과 겹치는 높이에서는 **폴을 아예 세울 수
 * 없었다.** 6m 슬래브 위 카메라와 6m 폴은 현실에서 둘 다 가능한 자리인데
 * 모델이 하나를 지운 것이다. 이제 그 높이에 성립하는 것을 **전부** 돌려주고,
 * 사용자는 화면에서 원하는 자리를 골라 클릭한다.
 *
 * 순서는 **구체적인 것부터**다 — 장비(점) → 상부(면) → 측면(선) → 폴(면).
 * 사용자 흐름도 이 순서다: 구조체에 먼저 붙이고, 남는 곳을 폴로 채운다.
 *
 * **새 규칙을 만들지 않는다.** site.json 의 `mounts` 를 그대로 읽는다.
 * ②③④ 는 src/export_site.py 가 건설 목적물(코어 벽체 · 슬래브)에서 유도하고,
 * ① 은 가설물 입력에서 온다 — 도면에 타워크레인이 없으므로 입력이 있어야 생긴다.
 *
 * 화면과 따로 두는 이유는 tools/test_mounts.mjs 가 이 규칙만 검사하기 위해서다.
 */
(function (global) {
  'use strict';

  var ORDER = ['equipment', 'structure_top', 'structure_side', 'pole'];
  var KO = {
    equipment: '가설 장비 위', structure_top: '구조물 상부',
    structure_side: '구조체 측면', pole: '폴',
  };

  /* 이 높이에 성립하는 자리를 **전부** 모은다.
   * `kinds` 가 비면 설치할 자리가 없다. `kind` 는 그중 첫째(=가장 구체적). */
  function mountAt(d, h) {
    var M = d.mounts;
    var out = { kind: null, kinds: [], by: {}, surfaces: [], points: [],
                faces: [], note: '' };
    var notes = [];

    var eq = M.equipment;
    if (eq && eq.points) {
      var pts = eq.points.filter(function (q) { return Math.abs(q.z - h) <= eq.snap_m; });
      if (pts.length) {
        out.by.equipment = { points: pts };
        out.points = pts;
        notes.push('가설 장비 위에 붙인다 (' + pts[0].mount + ' 높이 ' + pts[0].z
                   + 'm, ' + pts.length + '곳). 입력된 가설계획에서 온다');
      }
    }

    var st = M.structure_top;
    var tops = st.surfaces.filter(function (s) { return Math.abs(s.z - h) <= st.snap_m; });
    if (tops.length) {
      out.by.structure_top = { surfaces: tops };
      out.surfaces = tops;
      notes.push('구조물 상부에 붙인다 ('
        + tops.map(function (s) { return s.kind === 'core' ? '코어' : '슬래브'; })
              .filter(function (v, i, a) { return a.indexOf(v) === i; }).join(' · ')
        + ' 상단 ' + tops[0].z + 'm)');
    }

    var sd = M.structure_side;
    if (sd && sd.faces) {
      var faces = sd.faces.filter(function (f) {
        return h >= f.z1 - sd.snap_m && h <= f.z2 + sd.snap_m;
      });
      if (faces.length) {
        out.by.structure_side = { faces: faces, band: sd.band_m };
        out.faces = faces;
        notes.push('구조체 측면에 브래킷으로 붙인다 (테두리에서 ' + sd.band_m
                   + 'm 안). 브래킷 폭은 잠정값이다');
      }
    }

    // 가설 폴 — **없을 수 있다.** config.ENABLE_POLE_MOUNT 가 거짓이면
    // export_site.py 가 이 규칙을 아예 싣지 않는다 (2026-08-23).
    var p = M.pole;
    if (p && h >= p.h_min_m && h <= p.h_max_m) {
      out.by.pole = { clearance: p.clearance_m };
      notes.push('지면에 폴을 세운다 (' + p.h_min_m + '~' + p.h_max_m
                 + 'm, 골조에서 ' + p.clearance_m + 'm 이상). 이 높이 범위는 잠정값이다');
    }

    out.kinds = ORDER.filter(function (k) { return !!out.by[k]; });
    out.kind = out.kinds.length ? out.kinds[0] : null;

    if (!out.kinds.length) {
      var tz = st.surfaces.map(function (s) { return s.z; })
        .filter(function (v, i, a) { return a.indexOf(v) === i; })
        .sort(function (a, b) { return a - b; });
      out.note = '이 높이에는 설치할 자리가 없다. 구조물 상단은 '
               + tz.map(function (z) { return z + 'm'; }).join(' / ') + ' 이고, '
               + '구조체 측면은 그 구조체의 높이 범위 안이다'
               + (p ? '. 폴은 ' + p.h_min_m + '~' + p.h_max_m + 'm' : '');
    } else {
      out.note = notes.join(' · ');
    }
    return out;
  }

  /* 폴을 세울 수 있는가 — 골조의 평면 투영에서 clearance 만큼 떨어져야 한다.
   * 슬래브가 4m 위에 있어도 그 아래는 건물 안이라 폴을 세우지 않는다. */
  function poleOK(d, x, y) {
    if (!d.mounts.pole) return false;          // 폴을 쓰지 않는 설정
    var c = d.mounts.pole.clearance_m;
    if (x < 0 || y < 0 || x > d.site.width_m || y > d.site.depth_m) return false;
    for (var i = 0; i < d.solids.length; i++) {
      var b = d.solids[i];
      if (x >= b.x1 - c && x <= b.x2 + c && y >= b.y1 - c && y <= b.y2 + c) return false;
    }
    return true;
  }

  /* 사각형 **테두리** 위인가 — 안쪽으로도 바깥쪽으로도 band 만큼 본다.
   * 브래킷은 벽에 붙는 것이라 면이 아니라 선이 자리다. */
  function onEdge(f, x, y, band) {
    if (x < f.x1 - band || x > f.x2 + band) return false;
    if (y < f.y1 - band || y > f.y2 + band) return false;
    // 안쪽 사각형(테두리에서 band 만큼 들어간 것) 밖에 있으면 테두리 위다
    return !(x > f.x1 + band && x < f.x2 - band
             && y > f.y1 + band && y < f.y2 - band);
  }

  function inRect(s, x, y) {
    return x >= s.x1 && x <= s.x2 && y >= s.y1 && y <= s.y2;
  }

  /* 이 자리에 이 방식으로 놓을 수 있는가. */
  function okFor(d, kind, m, x, y) {
    var e = m.by[kind];
    if (!e) return false;
    if (kind === 'equipment') {
      // 장비 위는 그 지점뿐이다 — 반경 1.5m 안을 그 자리로 본다
      return e.points.some(function (q) { return Math.hypot(x - q.x, y - q.y) <= 1.5; });
    }
    if (kind === 'structure_top') {
      return e.surfaces.some(function (s) { return inRect(s, x, y); });
    }
    if (kind === 'structure_side') {
      return e.faces.some(function (f) { return onEdge(f, x, y, e.band); });
    }
    return poleOK(d, x, y);
  }

  /* 이 자리를 클릭하면 무엇으로 설치되는가. 없으면 null. */
  function kindAt(d, x, y, h) {
    var m = mountAt(d, h);
    for (var i = 0; i < m.kinds.length; i++) {
      if (okFor(d, m.kinds[i], m, x, y)) return m.kinds[i];
    }
    return null;
  }

  function placeable(d, x, y, h) { return kindAt(d, x, y, h) !== null; }

  /* 벽에 붙인 카메라가 **벽 바깥을 보게** 하는 방위(도).
   *
   * 기본 방위 0°(+x)를 그대로 쓰면 벽면에 단 카메라가 벽 안쪽을 본다. 실제로
   * 그렇게 다는 사람은 없고, 화면에서도 "놓았는데 지표가 안 변한다" 로 나온다
   * (2026-08-23, 코어 벽선에 놓아 보고 확인). 가장 가까운 변의 **바깥 법선**을
   * 초기값으로 준다. 사용자는 그 뒤 방위 슬라이더로 바꾼다.
   *
   * 자리를 못 찾으면 null — 호출부가 기본값을 쓴다.
   */
  function sideYaw(d, x, y, h) {
    var m = mountAt(d, h);
    var e = m.by.structure_side;
    if (!e) return null;
    var best = null, bd = Infinity;
    e.faces.forEach(function (f) {
      if (!onEdge(f, x, y, e.band)) return;
      var cand = [[Math.abs(x - f.x1), 180], [Math.abs(x - f.x2), 0],
                  [Math.abs(y - f.y1), 270], [Math.abs(y - f.y2), 90]];
      cand.forEach(function (c) { if (c[0] < bd) { bd = c[0]; best = c[1]; } });
    });
    return best;
  }

  /* 벽면 설치의 실제 좌표 — 방위와 **벽에서 띄운 위치**.
   *
   * 벽면에 딱 붙여 놓으면(x = 벽선) 그 카메라는 아무것도 못 본다. 광선의 끝점이
   * 벽체 상자 표면에 있어 모든 쌍이 완전 차폐로 잡히기 때문이다 — Python 으로
   * 확인했다(코어 서벽 x=18.0 에서 occ 1.000, 0.5m 띄우면 0.091).
   *
   * 브래킷이 실제로 하는 일이 이것이다. 벽에서 band 만큼 내밀어 단다.
   */
  function sideMount(d, x, y, h) {
    var yaw = sideYaw(d, x, y, h);
    if (yaw === null) return null;
    var b = d.mounts.structure_side.band_m;
    var r = yaw * Math.PI / 180;
    return { x: Math.round((x + b * Math.cos(r)) * 10) / 10,
             y: Math.round((y + b * Math.sin(r)) * 10) / 10,
             yaw: yaw, offset_m: b };
  }

  /* 프리셋으로 보여줄 높이들 — 폴 범위 양끝과 구조물 상단. 오름차순. */
  function presetHeights(d) {
    var p = d.mounts.pole;
    var hs = p ? [p.h_min_m, p.h_max_m] : [];
    d.mounts.structure_top.surfaces.forEach(function (s) {
      if (hs.indexOf(s.z) < 0) hs.push(s.z);
    });
    ((d.mounts.equipment || {}).points || []).forEach(function (q) {
      if (hs.indexOf(q.z) < 0) hs.push(q.z);
    });
    return hs.sort(function (a, b) { return a - b; });
  }

  global.Mounts = { mountAt: mountAt, poleOK: poleOK, placeable: placeable,
                    kindAt: kindAt, okFor: okFor, onEdge: onEdge, sideYaw: sideYaw, sideMount: sideMount,
                    presetHeights: presetHeights, ORDER: ORDER, KO: KO };
})(typeof window !== 'undefined' ? window : globalThis);
