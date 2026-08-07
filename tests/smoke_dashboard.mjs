// 대시보드 JS 스모크 테스트. 최소 DOM 스텁으로 4개 탭을 모두 렌더한다.
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(process.argv[2], "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length !== 2) throw new Error(`script 블록 ${scripts.length}개 (2개 기대)`);

const store = { nav: "", headline: "", view: "" };
let known = new Set(["nav", "headline", "view"]);

function refreshKnown() {
  known = new Set(["nav", "headline", "view"]);
  for (const m of (store.view + store.headline).matchAll(/id="([^"]+)"/g)) known.add(m[1]);
}

const makeEl = id => ({
  id,
  value: "",
  dataset: {},
  set innerHTML(v) { if (id in store) store[id] = v; refreshKnown(); },
  get innerHTML() { return store[id] ?? ""; },
  set onclick(f) {}, set onchange(f) {}, set oninput(f) {},
});

const document = {
  getElementById: id => (known.has(id) ? makeEl(id) : null),
  querySelectorAll: () => [],
};

const location = { hash: "" };
const history = { replaceState: (_a, _b, h) => { location.hash = h; } };

const ctx = { document, console, location, history };
ctx.window = ctx;
ctx.globalThis = ctx;
vm.createContext(ctx);

vm.runInContext(scripts[0], ctx);                       // 데이터
vm.runInContext(
  scripts[1] + "\nglobalThis.__go = (t,b,s,f) => { state.tab=t; " +
  "if(b!=null)state.building=b; if(s!==undefined)state.strategy=s; " +
  "if(f!=null)state.floor=f; render(); };" +
  "\nglobalThis.__D = D;",
  ctx
);

const D = ctx.__D;
console.log(`건물 ${D.buildings.length}개 · rules ${D.rules_version} · 격자 ${D.grid_mm}mm`);

const TABS = ["후보 목록", "상세분석", "대안 비교", "검토보고서"];
let fail = 0;
const expect = (cond, msg) => { if (!cond) { console.log("  FAIL " + msg); fail++; } };

for (let b = 0; b < D.buildings.length; b++) {
  const bd = D.buildings[b];
  const sids = Object.keys(bd.strategies);
  for (let t = 0; t < 4; t++) {
    ctx.__go(t, b, null, 0);
    const v = store.view, h = store.headline;
    expect(v.length > 200, `${bd.name} 탭 ${TABS[t]} 내용 비어 있음`);
    expect(!v.includes("undefined"), `${bd.name} 탭 ${TABS[t]} 에 undefined`);
    expect(!v.includes("[object Object]"), `${bd.name} 탭 ${TABS[t]} 에 [object Object]`);
    expect(!v.includes("NaN"), `${bd.name} 탭 ${TABS[t]} 에 NaN`);
    expect(h.includes("공급 가능 세대수") && h.includes("병목 축") && h.includes("위험 / 판정"),
      `${bd.name} 탭 ${TABS[t]} 헤드라인 3종 누락`);
  }
  // 전략 전환
  for (const s of sids) {
    ctx.__go(1, b, s, 0);
    expect(store.view.includes("<svg"), `${bd.name}/${s} 도면 없음`);
  }
  // 층 전환
  const nf = bd.floors_analyzed.length;
  for (let f = 0; f < nf; f++) {
    ctx.__go(1, b, null, f);
    expect(store.view.includes("<svg"), `${bd.name} ${f}번째 층 도면 없음`);
  }
  console.log(`  OK ${bd.name} — 탭4 × 전략${sids.length} × 층${nf}`);
}

// 검토보고서의 단가 계산
ctx.__go(3, 0, null, 0);
expect(store.view.includes("단가는 사용자 입력"), "단가 사용자 입력 문구 없음");
expect(store.view.includes("전문가의 현장조사"), "면책 문구 없음");
expect(store.view.includes("미확보"), "미확보 축 표시 없음");

// 헤드라인 수치가 caps.supply 와 일치하는지
ctx.__go(0, 0, null, 0);
const b0 = D.buildings[0], s0 = b0.strategies[b0.recommended];
expect(store.headline.includes(String(s0.caps.supply)), "헤드라인 공급 세대수 불일치");
expect(store.headline.includes(s0.caps.bottleneck_label), "헤드라인 병목 불일치");

// 해시 라우팅
ctx.__go(2, 1, null, 3);
expect(ctx.location.hash === "#t2/b1/f3", `해시 불일치: ${ctx.location.hash}`);
ctx.location.hash = "#t3/b0/f0";
vm.runInContext("readHash(); render();", ctx);
expect(store.view.includes("최종 판정"), "해시로 검토보고서 복원 실패");

console.log(fail === 0 ? "\n전부 통과" : `\n실패 ${fail}건`);
process.exit(fail === 0 ? 0 : 1);
