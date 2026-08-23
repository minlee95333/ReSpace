# -*- coding: utf-8 -*-
"""안전보고서 HTML 을 지면 그림용으로 캡처한다.

**왜 손으로 찍지 않는가.** 보고서 수치가 바뀔 때마다 다시 찍어야 하는데
손으로 하면 잊는다. 실제로 그림 7·8·9 가 옛 화면인 채로 한동안 남아 있었다.

**세 가지를 하고 찍는다.**

  1) 긴 표를 앞부분만 남긴다. 증설 곡선 98행·사각지대 40행을 다 넣으면
     세로로 3배가 되어 지면에서 글씨가 안 읽힌다
  2) 색을 전부 무채색으로 바꾼다. 계산된 색을 명도로 환산해 덮으므로
     인라인·클래스·상속 어디서 왔든 걸린다. **원본 HTML 은 건드리지 않는다**
  3) 전체 쪽을 한 장으로 찍는다. 두 단으로 쪼개는 것은 make_figures_extra.py

    python tools/capture_report.py
    python tools/make_figures_extra.py     # → fig_report.png
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "safety_report.html"
OUT = ROOT / "outputs" / "figures" / "_report_full.png"

TRIM = [(1, 10), (4, 8)]      # (표 순번, 남길 행 수)

PREP = """
() => {
  const trim = (idx, keep) => {
    const t = document.querySelectorAll('table')[idx];
    if (!t) return;
    const body = t.tBodies[0] || t;
    const rows = [...body.rows];
    if (rows.length <= keep) return;
    rows.slice(keep).forEach(r => r.remove());
    const td = document.createElement('td');
    td.colSpan = rows[0].cells.length;
    td.textContent = '\\u2026 이하 ' + (rows.length - keep) +
                     '행 생략 (원본 보고서에는 전부 있다)';
    td.style.cssText =
      'text-align:center;color:#6E6E6E;padding:8px 0;font-size:12px';
    const tr = document.createElement('tr');
    tr.appendChild(td);
    body.appendChild(tr);
  };
  __TRIM__

  // 색조를 명도로 환산해 덮는다. 붉은 막대는 짙게, 초록 막대는 옅게 남는다.
  const gray = (m) => {
    const [r, g, b] = [+m[1], +m[2], +m[3]];
    if (Math.max(r, g, b) - Math.min(r, g, b) <= 4) return null;
    const L = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
    return 'rgb(' + L + ',' + L + ',' + L + ')';
  };
  const RE = /rgba?\\((\\d+), (\\d+), (\\d+)/;
  const PROPS = ['background-color', 'border-left-color', 'border-top-color',
                 'border-right-color', 'border-bottom-color', 'color'];
  let n = 0;
  document.querySelectorAll('*').forEach(e => {
    const cs = getComputedStyle(e);
    PROPS.forEach(p => {
      const m = cs.getPropertyValue(p).match(RE);
      if (!m) return;
      const v = gray(m);
      if (v) { e.style.setProperty(p, v, 'important'); n++; }
    });
  });
  document.body.style.background = '#FFFFFF';
  return {props: n, height: document.body.scrollHeight};
}
"""


def main():
    if not SRC.exists():
        sys.exit(f"{SRC} 가 없다. 먼저 python src/safety_report.py 를 돌릴 것.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright 가 없다.  pip install playwright && playwright install chromium")

    js = PREP.replace("__TRIM__",
                      " ".join(f"trim({i}, {k});" for i, k in TRIM))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 980, "height": 1200},
                          device_scale_factor=2)
        page.goto(SRC.resolve().as_uri())
        info = page.evaluate(js)
        page.screenshot(path=str(OUT), full_page=True)
        b.close()
    print(f"→ {OUT}  ({OUT.stat().st_size:,} bytes)")
    print(f"   무채색화 {info['props']}개 속성 · 쪽 높이 {info['height']}px")


if __name__ == "__main__":
    main()
