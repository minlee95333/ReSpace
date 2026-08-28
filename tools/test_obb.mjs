/* engine.js 의 회전 상자 광선판정이 Python 과 같은 답을 내는가.
 *
 * 대조표는 tools/make_obb_fixture.py 가 만든다. rayHitsBox 는 engine.js 의
 * IIFE 안에 있어 밖으로 나오지 않으므로, 소스에서 해당 구간만 떼어 평가한다.
 *
 *   node tools/test_obb.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(ROOT, 'mockup/engine.js'), 'utf8');

const from = src.indexOf('function toLocalXY');
const to = src.indexOf('/* 복셀에 세운 사람 막대');
if (from < 0 || to < 0 || to <= from) {
  console.error('engine.js 에서 toLocalXY~rayHitsBox 구간을 찾지 못했다. 표식이 바뀌었는지 확인할 것.');
  process.exit(2);
}
const DEG = Math.PI / 180;
const fn = new Function('DEG', src.slice(from, to) + '; return { rayHitsBox };')(DEG);

const cases = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools/fixture_obb.json'), 'utf8'));
let bad = 0, badRot = 0;
for (const c of cases) {
  if (fn.rayHitsBox(c.p0, c.p1, c.b) !== c.hit) { bad++; if (c.b.yaw_deg) badRot++; }
}
console.log(`대조 ${cases.length}건 · 불일치 ${bad}건 (회전 상자 ${badRot}건)`);
process.exit(bad ? 1 : 0);
