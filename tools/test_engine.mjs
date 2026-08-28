/* mockup/engine.js 가 Python 과 같은 검출확률을 내는가.
 *
 * 화면(브라우저 계산)과 보고서(Python 계산)가 다른 말을 하면 안 된다. 대조표는
 * tools/make_engine_fixture.py 가 src/geometry.py + src/detect_model.py 로 만든다.
 *
 *   python tools/make_engine_fixture.py
 *   node   tools/test_engine.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const g = globalThis;
new Function('window', fs.readFileSync(path.join(ROOT, 'mockup/engine.js'), 'utf8')).call(g, g);

const site = JSON.parse(fs.readFileSync(path.join(ROOT, 'mockup/site.json'), 'utf8'));
const fx = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools/fixture_engine.json'), 'utf8'));
const { Engine } = g.CoverageEngine;

const eng = new Engine(site);
for (const c of fx.cams) eng.add(c);

// 복셀 id -> 표본 인덱스. engine 은 격자 인덱스로 다루므로 좌표로 되찾는다.
const S = eng.site;
const at = new Map();
for (let t = 0; t < S.n; t++) at.set(`${S.x[t]},${S.y[t]},${S.z[t]}`, t);

const TOL = 1e-6;
let checked = 0, bad = 0, worst = 0, worstAt = null, missing = 0;
for (const r of fx.sample) {
  const t = at.get(`${r.x},${r.y},${r.z}`);
  if (t === undefined) { missing++; continue; }
  for (let i = 0; i < fx.cams.length; i++) {
    const got = eng.cols[i][t], want = r.p[i];
    const diff = Math.abs(got - want);
    checked++;
    if (diff > worst) { worst = diff; worstAt = `${r.id} cam${i} js=${got} py=${want}`; }
    if (diff > TOL) bad++;
  }
}
console.log(`대조 ${checked}건 · 불일치 ${bad}건 · 최대오차 ${worst.toExponential(2)}` +
            (missing ? ` · 격자에서 못 찾음 ${missing}건` : ''));
if (worstAt) console.log(`  최대오차 지점: ${worstAt}`);
process.exit(bad || missing ? 1 : 0);
