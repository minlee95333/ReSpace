# 선행연구 원문 — 목록과 용도

수집 2026-08-25. 원본은 `~/Downloads/` 에 그대로 두었고 여기에는 사본을 한글 제목으로
정리했다. **PDF 는 출판사 저작물이므로 git 에 올리지 않는다** (`.gitignore` 처리).

우리 곡선을 대체하는 것이 아니라 **대조**하는 것이 목적이다(방침 C).
본 연구의 실측 곡선을 기본값으로 두고, 곡선을 교체 가능한 입력으로 분리하며,
선행연구가 보고한 관계와 형태가 일치하는지를 확인한다.

---

## 1. Kim et al. (2019) — 우리 WDR 의 직접 조상 ★

**체계적 카메라 배치 프레임워크 — 건설현장 작업 수준 시각 모니터링을 위한**

> Kim, J., Ham, Y., Chung, Y., & Chi, S. (2019). Systematic Camera Placement Framework
> for Operation-Level Visual Monitoring on Construction Jobsites.
> *Journal of Construction Engineering and Management*, 145(4), 04019019.
> DOI: 10.1061/(ASCE)CO.1943-7862.0001636

- 파일: `2019_Kim_체계적 카메라 배치 프레임워크.pdf` (14쪽)
- 원본: `kim-et-al-2019-systematic-camera-placement-framework-...pdf`
- 라이선스: **CC BY 4.0** (본문 명시). 인용·재배포 자유
- 소속: 서울대 · Texas A&M
- 방법: 시각 모니터링 결정요인 식별 → 수학적 모델링 → 하이브리드 시뮬레이션-최적화(GA)

**확인할 것**
- Weighted Visible Coverage 의 정의식 — 우리 WDR 과 무엇이 같고 무엇이 다른가
- 가중치를 어떻게 부여했는가(우리 w(v) 와 비교)
- 가시성 판정을 이진으로 했는지, 픽셀밀도 등 조건을 넣었는지

**제안서에서의 쓰임**: 3.1 인용 + 6.7.3 에서 WDR 의 계보를 대는 자리.
"기존 지표는 관측 가능한 공간의 가중치 합이고, 본 연구는 그 자리에 검출확률을 둔다"
는 문장의 근거가 여기서 나온다.

---

## 2. Ahn et al. (2026) — 가림률 대조 ★

**가림 환경에서의 굴착기 추적을 위한 신뢰도 기반 다중 카메라 자동 전략
(인스턴스 분할 딥러닝 이용)**

> Ahn, S., Seo, S., Shin, Y., & Koo, C. (2026). Automated reliability-based multi-camera
> strategy for excavator tracking under dynamic occlusion using deep learning with
> instance segmentation. *Automation in Construction*, 181, 106589.
> DOI: 10.1016/j.autcon.2025.106589

- 파일: `2026_Ahn_가림 환경 굴착기 추적 신뢰도 다중카메라.pdf` (17쪽)
- 원본: `1-s2.0-S0926580525006296-main.pdf`
- 소속: **인천대학교 건축·도시설계학부** (구중완 교수 연구실)
- 3단계 구성: (i) 실촬영·합성영상 성능 검증 (ii) 가림률·시점 기반 신뢰도 모델링
  (iii) 실제 시나리오 전략 검증

**이미 확인된 수치** (보도자료 기준, 본문 재확인 필요)
- 굴착기 **암(arm) 가림률 0.7 초과**, **본체(body) 0.5 초과** 에서 성능 악화
- 신뢰 추적 구역 분류 SVC weighted F1 **0.904**
- 실환경 MOTA **84.41 %**

**확인할 것**
- 신뢰도 모델의 입출력이 연속값인지 이진 분류인지
- 가림률 정의(면적 기준? 부위별?) — 우리 `occ_pct_box` 와 정의가 같은가
- 시점(viewpoint)을 어떤 변수로 표현했는가

**제안서에서의 쓰임**: 6.8 대조표의 가림 축.
우리 실측은 가림률 0.15 에서 이미 재현율 0.9578 → 0.6737 로 30 % 를 잃는다.
Ahn 의 0.5 와 큰 차이가 나며, **대상 크기 차이(굴착기 본체 vs 사람 머리)** 로 설명된다.
"중장비 감시 기준으로 설계된 배치는 안전모 검출에 불충분하다" 는 논거의 출처.

---

## 3. Shin et al. (2025) — 거리·높이·각도 대조 ★

**원거리 건설현장 감시영상에서 굴착기 활동 인식 향상을 위한 딥러닝 기반 자동화 방법**

> Shin, Y., Seo, S., & Koo, C. (2025). Deep learning-based automated method for enhancing
> excavator activity recognition in far-field construction site surveillance videos.
> *Automation in Construction*, 173, 106099.
> DOI: 10.1016/j.autcon.2025.106099

- 파일: `2025_Shin_원거리 영상 굴착기 활동 인식.pdf` (19쪽)
- 원본: `1-s2.0-S0926580525001396-main.pdf`
- 소속: **인천대학교 건축·도시설계학부** (구중완 교수 연구실)
- 방법: 3D ResNet + 전이학습, 딥러닝 기반 영상 전처리, **SHAP** 으로 배치조건 기여도 분석
- 실환경 원거리 영상 weighted F1 **0.818**, **거리가 가장 중요한 요인**

**확인할 것 — 가장 중요**
- 조건별 성능이 **표로 제시되는가, 그림뿐인가**
- 실험 조건의 실제 범위: 거리 몇 m ~ 몇 m, 높이 몇 m, 각도 몇 °
- 합성영상 생성 방식(우리 합성 변형과 비교 가능한가)
- SHAP 기여도의 축 순위 — 우리 실측에서는 가림 > 부감각 > 픽셀밀도 순인데
  Shin 은 거리를 1위로 든다. **범위가 다르면 순위가 달라지므로 조건 범위 확인이 필수**

**제안서에서의 쓰임**: 6.7.2 표 5(변수 대응) 근거, 6.8 대조표의 거리 축.

---

## 4. Tian et al. (2024) — 변수 분류 체계

**건설 분야 스마트 카메라 센서 배치에 관한 리뷰**

> Tian, W., Li, H., Zhu, H., Wang, Y., Liu, X., Yang, R., Xie, Y., Zhang, M., Zhu, J.,
> & Wang, X. (2024). A Review of Smart Camera Sensor Placement in Construction.
> *Buildings*, 14(12), 3930. DOI: 10.3390/buildings14123930

- 파일: `2024_Tian_건설 스마트 카메라 센서 배치 리뷰.pdf` (29쪽)
- 원본: `buildings-14-03930.pdf`
- 라이선스: **CC BY (MDPI 오픈액세스)**

**확인할 것**: 카메라 배치가 영향을 주는 요소의 분류 체계. 우리 3축이 그 분류의
어느 항목을 덮고 어느 항목을 제외했는지 대조.

---

## 5. Tran et al. (2022) — 4D 배치계획 (전략적 제외 대상의 근거)

**4D BIM 환경에서의 건설안전 감시카메라 설치 생성적 계획**

> Tran, S. V. T., Nguyen, T. L., Chi, H. L., Lee, D., & Park, C. (2022). Generative
> planning for construction safety surveillance camera installation in 4D BIM environment.
> *Automation in Construction*, 134, 104103. DOI: 10.1016/j.autcon.2021.104103

- 파일: `2022_Tran_4D BIM 감시카메라 설치 생성적 계획.pdf` (14쪽)
- 원본: `1-s2.0-S0926580521005549-main.pdf`
- 소속: 중앙대 · 홍콩폴리텍

**쓰임**: 3.1 인용. `CLAUDE.md` §6 이 4D 를 **전략적 제외**로 둔 근거가 이 계열이다.
"이미 수행된 영역이므로 중복하지 않는다" 는 서술의 출처.

---

## 6. Farkhondeh & Maghrebi (2025) — 최신 동적 배치 최적화

**동적 건설현장의 감시카메라 배치 정밀 최적화**

> Farkhondeh, M., & Maghrebi, M. (2025). Exact optimization of surveillance camera
> placement in dynamic construction sites. *Automation in Construction*, 180, 106569.

- 파일: `2025_Farkhondeh_동적 현장 카메라 배치 정밀 최적화.pdf` (20쪽)
- 원본: `1-s2.0-S0926580525006090-main.pdf`
- 소속: Ferdowsi University of Mashhad, Iran
- 방법: MILP. 공정 변화·재배치 비용·카메라 사양·**위험도 기반 우선순위** 반영
- 실제 4개 공정단계 사례에서 **비용 17.64 % 절감**

**쓰임**: 3.1 인용. 위험도 우선순위를 다단계로 넣은 최신 사례이므로,
"기존 연구도 위험도를 넣는다. 다만 가시성 기준이다" 라는 3.3 의 한계 서술을 뒷받침한다.
**우리가 위험도를 처음 넣었다고 주장하면 안 되는 근거이기도 하다.**

---

## 7. Zhang et al. (2024) — 참고 (직접 대조 대상 아님)

**실시간 정보와 결합한 지식그래프 기반 건설현장 동적 위험 분석**

> Zhang, J., Ruan, X., Si, H., & Wang, X. (2024). Dynamic hazard analysis on construction
> sites using knowledge graphs integrated with real-time information.
> *Automation in Construction*. (PII S0926580524006745)

- 파일: `2024_Zhang_지식그래프 기반 동적 위험 분석.pdf` (15쪽)
- 원본: `1-s2.0-S0926580524006745-main.pdf` (2026-08-16 수집)
- 주제가 위험 분석이라 6.3(위험도 지도) 쪽 참고자료. CCTV 배치와는 직접 관련 없음

---

## 대조 설계 요약

대상(굴착기 vs 안전모)도 지표(weighted F1 / MOTA vs 재현율)도 다르므로
**수치 직접 비교는 성립하지 않는다.** 비교 가능한 것은 관계의 형태와 순위다.

| 축 | 선행연구 | 본 연구 실측 | 상태 |
|---|---|---|---|
| 가림률 | 굴착기 본체 0.5 초과에서 악화 (Ahn 2026) | 0.15 에서 0.9578 → 0.6737 | 대상 크기 차이로 설명 |
| 부감각 | 극단적 부감이 저해 요인 (KISA 2025, 정성) | 붕괴점 61.4° (모델 2종 61.36 / 61.74) | 정성 서술의 수치화 |
| 거리 | 가장 중요한 요인 (Shin 2025, SHAP) | 조건 범위 확인 후 비교 | **원문 확인 필요** |
| 지표 정의 | Weighted Visible Coverage (Kim 2019) | WDR = Σw·P_total / Σw | **원문 확인 필요** |
