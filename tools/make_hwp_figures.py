# -*- coding: utf-8 -*-
"""제안서용 그림을 한글(.hwp) 파일로 뽑는다.

**왜 필요한가.** 제출물이 .hwp 원본이라 그림을 한글 안에서 다뤄야 한다.
PNG 를 하나씩 끌어다 놓고 크기를 맞추고 캡션을 다는 일을 반복하면 수치가
바뀔 때마다 처음부터 다시 해야 한다. 여기서 한 번에 만든다.

**어떻게 되는가.** 한컴오피스가 설치된 PC 에서 COM 자동화로 진짜 .hwp 를
만든다. LibreOffice 는 .hwp 를 읽기만 하고 쓰지는 못하며, pyhwp 계열도
읽기 전용이라 이 경로가 유일하다.

  - 그림은 A4 본문 폭(160mm)에 맞춰 넣는다. 비율은 원본 그대로 유지한다
  - 캡션은 그림 아래 한 줄. 수치가 들어 있어 그대로 쓸 수 있다
  - 그림마다 쪽을 나눈다. 제안서에 복사해 갈 때 섞이지 않게

**쓰는 법.** 만들어진 파일을 열어 필요한 그림을 골라 제안서로 복사한다.
이 파일 자체를 제안서로 쓰라는 뜻이 아니다.

    python tools/make_figures.py
    python tools/make_figures_extra.py
    python tools/make_hwp_figures.py

한컴오피스가 없으면 그렇게 말하고 멈춘다. 그 경우 outputs/figures/ 의 PNG 를
직접 끌어다 쓰면 된다.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
SHOT = ROOT / "docs" / "screenshots"
OUT = ROOT / "outputs" / "BIGB_그림_0823.hwp"

A4_BODY_MM = 160.0        # A4 폭 210 - 좌우 여백 25씩
MAX_H_MM = 170.0          # 세로가 이보다 크면 폭을 줄여 한 쪽에 담는다


def load():
    O = ROOT / "outputs"
    sr = json.loads((O / "safety_report.json").read_text(encoding="utf-8"))
    cm = json.loads((O / "comparison.json").read_text(encoding="utf-8"))
    cp = json.loads((O / "curve_params.json").read_text(encoding="utf-8"))
    mf = json.loads((ROOT / "data" / "filtered" / "manifest.json")
                    .read_text(encoding="utf-8"))
    return sr, cm, cp, mf


def figures():
    sr, cm, cp, mf = load()
    pl = cm["placements"]
    sd = sr["coverage"]["overall"]["score_detail"]
    pres = sr["prescription"]
    prim = cp["per_target"][cp["primary"]]
    cut = (1 - pl["empirical"]["fail_voxel_count"]
           / pl["geometric"]["fail_voxel_count"]) * 100
    tp = sr.get("time_phased") or {}

    return [
        (FIG / "fig_samples.png", "§2",
         "그림 1. 설치 조건에 따른 화면 속 작업자. 오른쪽은 현장에서 흔한 "
         "조건이며 이 조건의 미착용 검출률은 사실상 0이다."),
        (FIG / "fig_curves.png", "§3",
         f"그림 2. 실측 검출확률 곡선. {cp['n_conditions']}조건 × "
         f"{mf['n_selected']}장 추론, 주 지표 R² = {cp['r2_primary']:.4f}. "
         f"부감각은 {prim['g_theta']['params']['x0']:.0f}도 부근에서 무너진다."),
        (FIG / "fig_three.png", "§3",
         f"그림 3. 동일 예산 8대에서 설계 기준별 비교. 미달 복셀 "
         f"{pl['geometric']['fail_voxel_count']:,} → "
         f"{pl['empirical']['fail_voxel_count']:,}개({cut:.0f}% 감소)."),
        (FIG / "fig_pipeline.png", "§3·§5",
         "그림 4. 처리 흐름. 입력은 네 개의 계약 파일이며 실제 도면·계획서를 "
         "그 형식으로 넣으면 그대로 돈다."),
        (FIG / "fig_score.png", "§3",
         f"그림 5. 예시 계획서 채점. 총점 {sd['total']:.1f}/100, 등급 "
         f"{sd['grade']}. 치명 구역 {len(sd['critical_failures'])}곳 미달로 "
         f"등급 상한이 걸렸다."),
        (FIG / "fig_prescribe.png", "§3·§6",
         f"그림 6. 처방. 같은 8대 재배치로는 치명 구역이 남고, "
         f"{pres['add_cameras']}대를 증설하면 {pres['resulting']*100:.1f}점에 "
         f"도달한다."),
        (SHOT / "m-3d.png", "§5",
         "그림 7. 심사자 화면. 복셀별 검출확률을 색으로, 카메라 화각을 "
         "부채꼴로 표시한다."),
        (FIG / "fig_report.png", "§5·§6",
         "그림 8. 자동 생성되는 스마트 안전보고서. 건설기술진흥법 시행규칙 "
         "별표 7 의 CCTV 설치·운용계획 칸을 채운다. 긴 표는 앞부분만 남겼다."),
        (SHOT / "time-phased.png", "§3",
         f"그림 9. 시간대별 위험구역 진단. 최악은 "
         f"{tp.get('worst_window', '-')} 시간대이며 종합은 평균이 아니라 "
         f"최악값으로 대표한다."),
    ]


def build():
    try:
        import win32com.client as wc
    except ImportError:
        sys.exit("pywin32 가 없다.  pip install pywin32")
    from PIL import Image

    # 앞선 실행이 남긴 인스턴스가 있으면 COM 이 응답하지 않는다. 먼저 정리한다.
    import subprocess
    subprocess.run(["taskkill", "/F", "/IM", "Hwp.exe"],
                   capture_output=True, check=False)

    try:
        hwp = wc.Dispatch("HWPFrame.HwpObject")
    except Exception as e:
        sys.exit("한컴오피스를 찾을 수 없다. outputs/figures/ 의 PNG 를 직접 "
                 f"끌어다 쓸 것.\n  {type(e).__name__}: {e}")

    # 이 등록을 빼면 파일에 접근할 때마다 보안 대화상자가 떠서 자동화가 멈춘다
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    hwp.XHwpWindows.Item(0).Visible = False
    hwp.HAction.Run("FileNew")

    def text(s):
        hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
        hwp.HParameterSet.HInsertText.Text = s
        hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

    def para():
        hwp.HAction.Run("BreakPara")

    def page():
        hwp.HAction.Run("BreakPage")

    text("BIGB 제안서 그림 모음")
    para()
    text("outputs/figures/ 의 300dpi PNG 를 A4 본문 폭에 맞춰 넣었다. "
         "필요한 그림을 골라 제안서로 복사할 것. 수치가 바뀌면 "
         "tools/make_hwp_figures.py 를 다시 돌리면 캡션까지 갱신된다.")
    para()

    missing = []
    for path, section, caption in figures():
        if not path.exists():
            missing.append(path.name)
            continue
        page()
        text(f"[{section}]  {path.name}")
        para()
        iw, ih = Image.open(path).size
        w_mm = A4_BODY_MM
        h_mm = w_mm * ih / iw
        if h_mm > MAX_H_MM:                      # 세로로 긴 그림은 폭을 줄인다
            w_mm = MAX_H_MM * iw / ih
            h_mm = MAX_H_MM
        hwp.InsertPicture(str(path.resolve()), True, 1, False, False, 0,
                          hwp.MiliToHwpUnit(w_mm), hwp.MiliToHwpUnit(h_mm))
        hwp.HAction.Run("MoveDocEnd")
        para()
        text(caption)
        para()

    hwp.SaveAs(str(OUT), "HWP", "")
    hwp.Quit()
    subprocess.run(["taskkill", "/F", "/IM", "Hwp.exe"],
                   capture_output=True, check=False)
    return OUT, missing


if __name__ == "__main__":
    p, missing = build()
    print(f"→ {p}  ({p.stat().st_size:,} bytes)")
    if missing:
        print("빠진 그림:", ", ".join(missing))
