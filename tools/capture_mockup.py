# -*- coding: utf-8 -*-
"""심사자 화면(목업)을 지면 그림용으로 캡처한다.

**왜 스크립트인가.** 손으로 찍으면 수치가 바뀔 때 다시 찍는 것을 잊는다.
실제로 그림 7·8·9 가 옛 화면인 채로 한동안 남아 있었다.

**색.** 기본은 원본 컬러다(`GRAYSCALE = False`). 검출확률 히트맵은 색이
정보를 지므로 이 그림만은 예외로 둔다.

무채색이 필요하면 `GRAYSCALE = True` 로 바꾼다. 그때는 tokens.css 의
`--scale-*` 다섯 정지점을 **응답째 가로채** 회색 램프로 바꾼다 — `<style>` 을
끼워 넣는 방법은 heat() 가 첫 호출에 값을 캐시해 타이밍이 안 맞았다. 원본이
붉은색↔푸른색 발산이라 그대로 회색조로 낮추면 양끝 명도가 비슷해져 구별이
사라지므로, 명도를 단조로 다시 깐다.

**시점.** `PITCH` 가 클수록 위에서 내려다본다(2D 가 90°). 목업 기본값 25° 는
거의 옆에서 보는 각이라 지면 그림으로는 층 구조가 안 읽힌다. 여기서는 올려
잡는다. PRESETS 를 페이지 위에서 바꾼 뒤 3D 버튼을 누르면 적용된다 —
setMode 가 그때 PRESETS 를 복사하기 때문이다.

    python tools/capture_mockup.py
    python tools/make_figures_extra.py     # → fig_3d.png
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
MOCKUP = ROOT / "mockup"
OUT = ROOT / "outputs" / "figures" / "_mockup_3d.png"
PORT = 8793

GRAYSCALE = False       # 이 그림만 컬러를 허용한다
PITCH = 58              # 클수록 위에서 본다. 목업 기본은 25

# 어두울수록 못 보는 곳. 명도를 단조로 깐다. GRAYSCALE 일 때만 쓴다.
GRAY_STOPS = {
    "--scale-0": "#2E2E2E",     # P 0.00  미달극
    "--scale-25": "#5A5A5A",
    "--scale-mid": "#8C8C8C",   # P 0.50  임계
    "--scale-75": "#BEBEBE",
    "--scale-1": "#E6E6E6",     # P 1.00  통과극
}


def graytokens(css: str) -> str:
    """`--scale-*: <무엇이든>;` 을 회색 hex 로 바꾼다.

    정규식을 쓰지 않는다 — 역참조가 도구를 거치며 사라지는 일이 있었다.
    이름을 찾아 다음 세미콜론까지를 통째로 갈아 끼운다.
    """
    for name, hexv in GRAY_STOPS.items():
        i = 0
        while True:
            i = css.find(name + ":", i)
            if i < 0:
                i = css.find(name + " :", i)
            if i < 0:
                break
            end = css.find(";", i)
            if end < 0:
                break
            css = css[:i] + f"{name}: {hexv}" + css[end:]
            i += len(name) + len(hexv) + 2
    return css


def serve():
    handler = partial(SimpleHTTPRequestHandler, directory=str(MOCKUP))
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def trim(path: Path, pad: int = 18):
    """회색조로 굳히고 바깥 여백을 자른다.

    캔버스가 864×788 인데 그림은 가운데 절반뿐이라, 그대로 두면 지면에서
    실제 내용이 절반 크기로 들어간다.
    """
    from PIL import Image
    im = Image.open(path)
    im = im.convert("L") if GRAYSCALE else im.convert("RGB")
    # 모서리 색과 비교하는 방법은 못 쓴다 ― 캔버스가 둥근 카드 위에 있어
    # 카드 전체가 '내용'으로 잡힌다. 명도로 자른다.
    # 캔버스 가장자리에 둥근 카드 테두리가 옅게 그려져 있어 그대로 재면
    # 언제나 전체가 나온다. 바깥 2% 를 떼고 잰 뒤 좌표를 되돌린다.
    ins = int(min(im.size) * 0.02)
    inner = im.crop((ins, ins, im.width - ins, im.height - ins))
    box = inner.convert("L").point(lambda v: 255 if v < 238 else 0).getbbox()
    if box:
        box = (box[0] + ins, box[1] + ins, box[2] + ins, box[3] + ins)
    im = im.convert("RGB")
    if box:
        box = (max(0, box[0] - pad), max(0, box[1] - pad),
               min(im.width, box[2] + pad), min(im.height, box[3] + pad))
        im = im.crop(box)
    im.save(path)
    return im.size


def main():
    if not (MOCKUP / "index.html").exists():
        sys.exit(f"{MOCKUP/'index.html'} 가 없다.")
    if not (MOCKUP / "data.json").exists():
        sys.exit("mockup/data.json 이 없다. 먼저 python src/report.py 를 돌릴 것.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright 가 없다.  "
                 "pip install playwright && playwright install chromium")

    srv = serve()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": 1500, "height": 1000},
                              device_scale_factor=2)

            def route_tokens(route):
                r = route.fetch()
                route.fulfill(response=r, body=graytokens(r.text()))

            if GRAYSCALE:
                page.route("**/tokens.css", route_tokens)
            page.goto(f"http://127.0.0.1:{PORT}/index.html")
            page.wait_for_selector("canvas", timeout=30000)
            # 3D 버튼을 누르기 전에 기준각을 바꾼다. setMode 가 이때 복사한다.
            page.evaluate("(p) => { window.CoverageViewer.PRESETS['3d'].pitch = p; }",
                          PITCH)
            page.click('button[data-m="3d"]')
            page.wait_for_timeout(1500)     # 캔버스가 한 프레임 더 돌 시간
            page.locator("canvas").first.screenshot(path=str(OUT))
            b.close()
    finally:
        srv.shutdown()

    size = trim(OUT)
    print(f"→ {OUT}  ({OUT.stat().st_size:,} bytes)  잘라낸 크기 {size}")


if __name__ == "__main__":
    main()
