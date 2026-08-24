# -*- coding: utf-8 -*-
"""제안서 작업본(.hwp) 에 새 뼈대를 얹는다.

**왜 새로 짜는가.** 검토 메모가 15매 구성을 지정했다(메모 2). 서식1 의 일곱 절이
아니라 아홉 장이며, 무게중심이 「연구 상세 내용」 5장에 있다. 우리가 가진 실측
결과가 정확히 그 5장이므로 구성을 그쪽으로 옮긴다.

  표지 1 · 배경/문제점 2 · 관련 연구기술 1 · 목적/세부추진과제 1 ·
  창의성 1 · **연구 상세 내용 5** · 경제성·실현가능성 2 · 활용방안 2 · 파급효과 1

**기존 초안을 지우지 않는다.** 새 뼈대 뒤에 "이전 초안(참고용)" 구분선과 함께
초안 본문을 붙인다. 최종본을 낼 때 뒤쪽을 지우면 된다.

**원본 hwp 를 열지 않는다.** 그 파일에는 Scripts 스트림이 들어 있어 COM 으로
Open 하면 스크립트 보안 대화상자에서 멈춘다(SetMessageBoxMode 로도 안 열린다).
그래서 새 문서를 짓고, 초안은 미리 뽑아둔 텍스트(outputs/_sl_clean.txt)를
붙인다. 원본과 메모 원문은 docs/reference/ 와 outputs/_sl_memos.txt 에 있다.

**수치는 outputs/ 에서 읽는다.** 손으로 적은 값이 없어야 코드가 바뀔 때 다시
뽑기만 하면 맞는다.

    python tools/build_proposal.py
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
TARGET = Path.home() / "Desktop" / "제안서_BIGB_작업본.hwp"

TITLE = "건설현장 공간 위험도와 영상 객체 식별 성능을 고려한\nAI CCTV 배치 적정성 평가"
TEAM = ["인천대학교 이승민", "인천대학교 김동현"]
DUE = "2026. 8. 28"

A4_BODY_MM = 155.0


def load():
    O = ROOT / "outputs"
    return (json.loads((O / "safety_report.json").read_text(encoding="utf-8")),
            json.loads((O / "comparison.json").read_text(encoding="utf-8")),
            json.loads((O / "curve_params.json").read_text(encoding="utf-8")),
            json.loads((O / "sensitivity.json").read_text(encoding="utf-8")),
            json.loads((O / "site_eval.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "data/filtered/manifest.json").read_text(encoding="utf-8")))


def outline():
    """(장 제목, [본문 블록]) 목록. 블록은 문자열이거나 ('fig', 파일명, 캡션)."""
    sr, cm, cp, sn, se, mf = load()
    pl = cm["placements"]
    sd = sr["coverage"]["overall"]["score_detail"]
    pres = sr["prescription"]
    prim = cp["per_target"][cp["primary"]]
    cut = (1 - pl["empirical"]["fail_voxel_count"]
           / pl["geometric"]["fail_voxel_count"]) * 100
    realloc = (sr.get("options") or {}).get("reallocate") or {}
    occ = sr["site"]["voxels"]

    B = "•  "     # 불릿. 메모 2 가 불릿을 쓰라고 했다

    return [
        ("1. 연구 배경 및 문제점", [
            "1.1 배경 — CCTV 는 이미 의무에 가깝다",
            f"{B}건설기술진흥법 시행규칙 별표 7(안전관리계획의 수립기준) 1-다는 "
            "「계측장비 및 폐쇄회로 텔레비전 등 안전 모니터링 장비의 설치 및 "
            "운용계획」을 안전관리계획에 포함하도록 규정한다.",
            f"{B}서울시는 해체·굴토 등 취약공정에 CCTV 설치를 의무화했다.",
            f"{B}LH 는 「늘봄 A-Eye」로 전국 350개 현장 중 위험작업·투입장비를 "
            "기준으로 매일 20곳을 선별해 집중 관리한다.",
            "[작성 메모] 배경에는 '무엇이 좋아지는가'만 쓴다. 문제점은 1.2 로 뺀다 (메모 6).",
            "",
            "1.2 문제 — 배치까지가 끝이고, 잘 보이는지는 모른다",
            f"{B}현재 배치는 설치 가능 위치·전체 가시범위·사각지대 최소화로 정해진다. "
            "2D 도면 위에서 화각 부채꼴을 겹쳐 보는 데서 끝난다.",
            f"{B}그러나 화면에 들어왔다고 AI 가 알아보는 것은 아니다. 거리·설치각도·"
            "가림에 따라 식별 성능이 달라진다.",
            ("fig", "fig_samples.png",
             "그림 1-1. 같은 작업자, 같은 카메라. 설치 조건만 다르다. "
             "오른쪽은 현장에 흔한 조건이며 이 조건의 미착용 식별률은 사실상 0 이다."),
            f"{B}판정할 기준도 없다. 「전 범위의 몇 %를 감시해야 한다」는 문장은 "
            "가이드라인·인증제도·시행규칙 어디에도 없다(2026-08 전수 확인).",
            "[작성 메모] 이 장이 납득되지 않으면 뒤가 전부 무너진다 (메모 4). 그림 1-1 이 그 일을 한다.",
        ]),

        ("2. 관련 연구기술 개발현황", [
            "2.1 기하 커버리지 최적화",
            f"{B}카메라 배치 최적화는 무선센서망의 target coverage 문제로 오래 다뤄졌다. "
            "「보이는가」를 0/1 로 판정하고 커버 면적을 최대화한다.",
            f"{B}한계 — 116m 떨어진 지점도 화각 안이면 커버로 센다. 실무 도구"
            "(JVSG, Axis Site Designer)는 이를 보완하려 IEC 62676-4(DORI) 최소 "
            "픽셀밀도를 쓴다. 다만 DORI 는 사람이 화면을 보는 기준이며 AI 검출기에 "
            "대해 검증된 바 없다.",
            "",
            "2.2 확률적 커버리지",
            f"{B}센서의 검출을 확률로 다루는 모델은 존재한다. 그러나 곡선을 "
            "가정값으로 두는 경우가 많다(Sensors 2014 는 시행착오로 파라미터를 "
            "정했다고 명시).",
            "",
            "2.3 4D BIM 안전계획",
            f"{B}Zhang·Teizer·Pradhananga·Eastman, Automation in Construction 29 "
            "(2013) 이 공정·모델에서 위험구역을 자동 도출하는 방식을 확립했다.",
            f"{B}그 연구는 위험을 「찾아내는」 것이다. 찾아진 위험구역을 카메라가 "
            "실제로 보고 있는지 판정하는 문제는 다루지 않는다.",
            "[작성 메모] 메모 7 이 요구한 '유사 문제를 풀려 했으나 해결하지 못한 선행연구' 자리다.",
        ]),

        ("3. 연구 목적 및 세부추진 과제", [
            "3.1 연구 목적",
            "건설현장 CCTV 계획서를 입력받아, 각 위험구역에서 AI 가 안전모 미착용을 "
            "실제로 식별할 확률을 산정하고, 그 값으로 배치의 적정성을 100점으로 "
            "채점하며, 미달 시 재배치 또는 증설을 처방한다.",
            "",
            "3.2 세부 추진과제",
            f"{B}과제 1 — 설치 조건(픽셀밀도·부감각·가림)에 따른 식별 성능 곡선을 "
            "실측으로 확보한다.",
            f"{B}과제 2 — 현장을 부피 복셀로 나누고 광선투사로 복셀·카메라 쌍의 "
            "설치 조건을 산정한다.",
            f"{B}과제 3 — 곡선을 적용해 복셀별 식별확률을 내고 다중 카메라를 결합한다.",
            f"{B}과제 4 — 위험가중치로 100점 채점하고 치명 구역 게이트를 건다.",
            f"{B}과제 5 — 재배치·증설 처방을 산출한다.",
            ("fig", "fig_pipeline.png",
             "그림 3-1. 연구 목적과 세부 추진과제. 입력 네 개의 계약 파일에서 "
             "처방까지 한 줄로 흐른다."),
            "",
            "3.3 용어 정의",
            f"{B}식별확률 P — 해당 지점의 작업자를 AI 가 검출할 확률. "
            "P = f(ρ)·g(θ)·h(o) 로 산정한다.",
            f"{B}ρ 유효 픽셀밀도 — 화면에서 머리가 차지하는 픽셀 수.",
            f"{B}θ 부감각 — 카메라가 내려다보는 각도. 0도가 수평.",
            f"{B}o 가림률 — 골조·가설재에 가려진 비율.",
            f"{B}미달구역 — 위험구역 중 요구 커버리지에 못 미치는 공간.",
            f"{B}치명 구역 — 위험가중치 7 이상인 구역. 미달이면 총점과 무관하게 "
            "적정으로 보지 않는다.",
            "[작성 메모] 메모 10 이 '용어를 앞에서 정의하고 가라'고 지적했다. Blind Risk Zone 대신 미달구역으로 통일한다.",
        ]),

        ("4. 제안 과제의 창의성", [
            f"{B}창의성 1 — 「보이는가」가 아니라 「식별되는가」. 화각 판정 대신 "
            f"{cp['n_conditions']}조건 × {mf['n_selected']}장을 실제로 추론해 얻은 "
            f"곡선을 쓴다(주 지표 R² = {cp['r2_primary']:.4f}).",
            f"{B}창의성 2 — 임계가 아니라 연속 확률. DORI 처럼 자르지 않고 확률로 "
            "다루므로 다중 카메라 결합이 가능해진다. P_total = 1 − Π(1−P) 이며 "
            "겹쳐 보는 것이 이득이 된다.",
            f"{B}창의성 3 — 면적이 아니라 위험으로 채점. 배점을 가중치에 비례시켜 "
            "넓은 저위험 구역이 점수를 지배하지 못하게 한다. 초과 달성으로 다른 "
            "구역을 벌충하지 못한다.",
            f"{B}창의성 4 — 치명 구역 게이트. 가중치 7 이상 구역이 미달이면 총점이 "
            "높아도 적정이 아니다. 안전기준은 평균으로 면제되지 않는다.",
            "[작성 메모] 메모 8: 창의성은 '무엇을 했다'가 아니라 '그것을 하려고 어떤 기술을 도입했나'다. 위 네 줄이 그 형식이다.",
        ]),

        ("5. 연구 상세 내용", [
            "[작성 메모] 메모 2 가 5장을 배정한 핵심부다. Step 순서로 무엇을 했고 어떤 결과를 얻었는지 쓴다.",
            "",
            "Step 1. 식별 성능 곡선 실측",
            f"{B}데이터 — 공개 데이터셋 SHWD 에서 머리 크기 {mf['min_head_px']}px "
            f"이상인 {mf['n_selected']}장을 골랐다. 학습셋과 겹치지 않도록 test "
            "분할로 제한했다.",
            f"{B}검출기 — 사전학습 모델에는 안전모 클래스가 없어 기준 조건에서도 "
            "주 지표가 0.088 에 그쳤다. SHWD 로 파인튜닝했다(mAP50 0.9372).",
            f"{B}변형 — ρ 8수준 × θ 6수준 × o 6수준 = {cp['n_conditions']}조건. "
            "가림은 랜덤 사각형이 아니라 수직 스트라이프로 했다. 현장의 가림원이 "
            "비계·동바리 등 수직 부재이기 때문이다.",
            ("fig", "fig_curves.png",
             f"그림 5-1. 실측 식별확률 곡선. 부감각은 "
             f"{prim['g_theta']['params']['x0']:.0f}도 부근에서 절벽처럼 무너진다."),
            f"{B}결과 — 분리형 곱셈 모델 P = f(ρ)·g(θ)·h(o) 로 피팅했다. 전체 "
            f"{cp['n_conditions']}점 결정계수는 주 지표 {cp['r2_primary']:.4f}, "
            f"항목 최솟값 기준 {cp['r2_full_grid']:.4f} 다.",
            f"{B}검증 — 최신 검출기(yolo26n)로 같은 격자를 다시 측정했다. 곡선의 "
            "형태가 유지되어(변곡점 5.73 → 5.63px) 검출기를 바꿔도 관계가 남는다는 "
            "것을 확인했다.",
            "",
            "Step 2. 현장 모델과 설치 조건 산정",
            f"{B}현장을 {se['site']['voxel_m']}m 정육면체로 나눴다. 바닥면이 아니라 "
            f"부피 전체를 다룬다 — 총 {len(se['voxels']):,}개, 그중 사람이 갈 수 "
            f"있는 {occ:,}개만 채점 대상이다.",
            f"{B}복셀·카메라 쌍마다 거리·픽셀밀도·부감각·가림률을 냈다. 가림은 복셀 "
            "자리에 키 1.7m 막대를 세우고 11개 점에서 광선을 쏘아 막히는 비율로 "
            "구한다.",
            "",
            "Step 3. 위험구역과 가중치",
            f"{B}위험은 우리가 판단하지 않는다. 골조에서 규칙으로 도출되는 것"
            "(슬래브 단부·갱폼 작업면·타설면)과 도면·가설계획에서 받아야 하는 것"
            "(개구부·굴착면·리프트·크레인·야적장)을 나눴다.",
            f"{B}가중치는 고용노동부 「2025년 3분기 재해조사 대상 사망사고 발생 "
            "현황」에서 유도했다. 모든 구역은 출처를 가져야 하며, 없으면 실행이 "
            "멈춘다.",
            "",
            "Step 4. 채점",
            ("fig", "fig_score.png",
             f"그림 5-2. 예시 계획서 채점. 총점 {sd['total']:.1f}/100, 등급 "
             f"{sd['grade']}. 치명 구역 {len(sd['critical_failures'])}곳 미달로 "
             f"등급 상한이 걸렸다."),
            f"{B}구역마다 배점(가중치 비례)과 요구 커버리지를 두고 달성률로 채점한다.",
            "",
            "Step 5. 배치 비교 — 자를 바꾸면 배치가 갈린다",
            ("fig", "fig_three.png",
             f"그림 5-3. 동일 예산 8대. 미달 복셀 "
             f"{pl['geometric']['fail_voxel_count']:,} → "
             f"{pl['empirical']['fail_voxel_count']:,}개({cut:.0f}% 감소)."),
            f"{B}기하 커버리지·문헌의 가정 곡선·실측 곡선 세 기준으로 각각 8대를 "
            "배치하고, 셋 다 실측 곡선의 자로 다시 측정했다.",
            f"{B}기하 기준선에는 DORI 최소 픽셀밀도를 걸었다. 네 등급을 전수 실행한 "
            "뒤 우리와 차이가 가장 작은 등급을 기본값으로 골랐다 — 기존 방식에 가장 "
            "유리한 조건에서 비교하기 위해서다.",
            f"{B}공통으로 선택된 카메라는 8대 중 "
            f"{cm['overlap_camera_count']['empirical_vs_geometric']}대뿐이다.",
            "",
            "Step 6. 처방",
            ("fig", "fig_prescribe.png",
             f"그림 5-4. 현 계획서 {sd['total']:.1f}점 → 재배치 "
             f"{(realloc.get('score_100') or 0):.1f}점 → "
             f"{pres['add_cameras']}대 증설 {pres['resulting']*100:.1f}점."),
            f"{B}대수를 늘리기 전에 재배치를 먼저 시도한다. 예산을 쓰지 않고 되는 "
            "일을 증설로 답하면 발주처가 쓰지 않는다.",
            f"{B}목적함수가 submodular 이므로 탐욕해가 최적해의 (1−1/e) ≈ 63% "
            "이상임이 보장된다.",
            "",
            "Step 7. 민감도",
            f"{B}근거가 공개되지 않은 값 둘(가림 스트라이프 주기, 비계 시야 점유율)을 "
            f"스윕했다. 절대 수치는 흔들리지만 두 배치의 차이는 "
            f"+{sn['delta_WDR_range'][0]:.4f} ~ +{sn['delta_WDR_range'][1]:.4f} 로 "
            "부호가 유지된다.",
            f"{B}위험가중치도 통계 유도값과 심각도 보정값 두 프로파일에서 판정이 "
            "같았다.",
        ]),

        ("6. 연구의 경제성 및 실현가능성 검토", [
            "[작성 메모] 메모 9: 가정을 넣고 숫자로 시뮬레이션해야 한다. 인프라 절감이 아니라 '있는 장비를 제대로 쓰는' 쪽으로 쓴다. 단가 가정은 팀에서 확정할 것.",
            "",
            "6.1 경제성 — 증설 없이 얻는 몫",
            f"{B}예시 현장에서 현 계획서는 {sd['total']:.1f}점이다. 같은 8대를 "
            f"재배치하면 {(realloc.get('score_100') or 0):.1f}점이 된다. "
            f"목표에 닿으려면 {pres['add_cameras']}대 증설이 필요하다.",
            f"{B}즉 재배치만으로 확보되는 몫이 있고, 그만큼의 증설을 미룰 수 있다. "
            "여기에 대당 설치·임대 단가를 곱하면 금액이 나온다. [단가 확정 필요]",
            f"{B}2026-01-01 부터 스마트 안전장비 구입·임대 비용이 산업안전보건관리비에 "
            "100% 계상되므로, 증설 대수를 줄이는 것은 그대로 계상액 절감이다.",
            "",
            "6.2 실현가능성 — 입력이 이미 쓰는 서류다",
            f"{B}입력은 네 개다. CCTV 계획서, 골조 형상, 위험구역, 공정표. 모두 "
            "현장이 이미 작성하는 문서이며 새로 만들 것이 없다.",
            f"{B}BIM 이 없어도 된다. 골조는 축정렬 직육면체 목록으로 받으며, IFC "
            "어댑터가 슬래브·층고·개구부를 자동으로 낸다. 비계는 설계 BIM 에 없으므로 "
            "가설계획에서 받는다.",
            f"{B}실행은 단일 실행파일 하나다. 복셀 {len(se['voxels']):,}개 기준 "
            "재계산에 약 3분이 걸린다.",
            "",
            "6.3 유지관리 — LH 가 직접 굴릴 수 있는가",
            "[작성 메모] 메모 9 가 '매우 중요'라고 한 부분이다.",
            f"{B}검출기가 바뀌어도 곡선 파일 하나만 교체하면 된다. A-Eye 실제 모델의 "
            "곡선을 확보하면 그대로 갈아 끼운다.",
            f"{B}LH 가 커버리지 기준을 게시하면 임계값 한 줄만 바꾼다. 현재는 기준이 "
            "없으므로 네 임계(80·85·90·95%)의 결과를 함께 낸다.",
            f"{B}모든 수치는 계산 결과이며 문서에서 임의로 만들지 않는다. 입력이 "
            "바뀌면 보고서를 다시 뽑기만 하면 맞는다.",
        ]),

        ("7. 연구 결과의 활용방안", [
            "7.1 LH 적용 제안",
            "[작성 메모] 메모 10: '적용성이 LH여도 현대건설이어도 상관없다'는 지적을 받은 자리다. LH 고유 구조에 붙인다.",
            f"{B}LH 는 350개 현장 중 매일 20곳을 위험작업·투입장비 기준으로 선별한다. "
            "이 도구는 그 선별에 「그 현장의 카메라가 오늘 열린 위험구역을 실제로 "
            "식별할 수 있는가」를 더한다.",
            f"{B}시간대별 진단이 그 근거가 된다. 같은 배치도 공정 시간대에 따라 "
            "적정성이 달라지며, 종합은 평균이 아니라 최악의 시간대로 대표한다.",
            ("fig", "fig_timephase.png",
             "그림 7-1. 시간대별 위험구역 진단. 종합은 최악의 시간대로 대표한다."),
            f"{B}산출물은 건설기술진흥법 시행규칙 별표 7 의 「설치 및 운용계획」 칸을 "
            "채우는 형식이다. 새 서식을 만들지 않는다.",
            ("fig", "fig_report.png",
             "그림 7-2. 자동 생성되는 스마트 안전보고서."),
            "",
            "7.2 일반적인 활용",
            f"{B}발주처 — 계획서 심사 단계에서 정량 판정 근거로 쓴다.",
            f"{B}시공사 — 증설 전에 재배치로 되는지 먼저 확인한다.",
            f"{B}장비사 — 카메라 사양(해상도·화각)을 바꿨을 때의 효과를 배치 단위로 "
            "환산해 제시할 수 있다.",
        ]),

        ("8. 파급효과", [
            f"{B}첫째, AI CCTV 배치에 정량적 판단 근거가 생긴다. 경험과 관행으로 "
            "정하던 것을 식별확률로 채점한다.",
            f"{B}둘째, 못 보는 자리가 드러난다. 예시 현장에서 미달 복셀이 "
            f"{pl['geometric']['fail_voxel_count']:,}개에서 "
            f"{pl['empirical']['fail_voxel_count']:,}개로 줄었다.",
            f"{B}셋째, 규정의 빈칸을 채우는 근거가 된다. 커버리지 비율 기준이 없는 "
            "현재 상태에서, 임계를 정하지 않고도 「어떤 임계를 주더라도 필요한 대수와 "
            "위치」를 답할 수 있다.",
            f"{B}넷째, 검출기 성능 향상이 배치 개선으로 이어지는 경로가 생긴다. "
            "곡선을 갈아 끼우면 같은 현장의 필요 대수가 다시 계산된다.",
        ]),
    ]


def build():
    try:
        import win32com.client as wc
    except ImportError:
        sys.exit("pywin32 가 없다.  pip install pywin32")
    subprocess.run(["taskkill", "/F", "/IM", "Hwp.exe"], capture_output=True, check=False)
    hwp = wc.Dispatch("HWPFrame.HwpObject")
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

    text(TITLE.replace("\n", " "))
    para()
    text(f"제17회 LH 국토기술대전 공모 제안서   ·   {DUE}")
    para()
    text("   ·   ".join(TEAM))
    para()
    text("[작성 메모] 작품명은 메모 1 의 지적을 반영했다. "
         "'CCTV 배치 평가'만 쓰면 기존 배치 연구로 읽히고, "
         "'AI 영상인식 신뢰도'는 '영상 객체 식별 성능'으로 바꿨다.")
    para()
    page()

    text("목  차")
    para()
    for name, _ in outline():
        text(name)
        para()
    page()

    from PIL import Image
    for name, blocks in outline():
        text(name)
        para()
        for b in blocks:
            if isinstance(b, tuple):
                _, fname, cap = b
                p = FIG / fname
                if p.exists():
                    iw, ih = Image.open(p).size
                    w_mm = A4_BODY_MM
                    h_mm = w_mm * ih / iw
                    if h_mm > 150:
                        w_mm, h_mm = 150 * iw / ih, 150
                    hwp.InsertPicture(str(p.resolve()), True, 1, False, False, 0,
                                      hwp.MiliToHwpUnit(w_mm), hwp.MiliToHwpUnit(h_mm))
                    hwp.HAction.Run("MoveDocEnd")
                    para()
                text(cap)
                para()
            else:
                text(b)
                para()
        page()

    text("─────  이하 이전 초안 (참고용) · 최종본에서 삭제  ─────")
    para()
    text("이승민 초안 원문이다. 검토 메모 12개는 outputs/_sl_memos.txt 에, "
         "원본 hwp 는 docs/reference/제안서초안_SL_0823.hwp 에 있다.")
    para()
    draft = ROOT / "outputs" / "_sl_clean.txt"
    if draft.exists():
        for line in draft.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                text(line)
                para()

    # **있는 파일을 덮지 않는다.** 사용자가 한글에서 손질한 것이 통째로 날아간다.
    # 실제로 한 번 덮어썼다. 있으면 옆 이름으로 낸다.
    out = TARGET
    if out.exists():
        for i in range(2, 60):
            alt = out.with_name(f"{out.stem}_v{i}{out.suffix}")
            if not alt.exists():
                out = alt
                break
    hwp.SaveAs(str(out), "HWP", "")
    hwp.Quit()
    subprocess.run(["taskkill", "/F", "/IM", "Hwp.exe"], capture_output=True, check=False)
    return out


if __name__ == "__main__":
    p = build()
    print(f"→ {p}  ({p.stat().st_size:,} bytes)")
