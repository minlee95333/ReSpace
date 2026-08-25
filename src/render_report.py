# -*- coding: utf-8 -*-
"""스마트 안전보고서 HTML 렌더러.

단일 파일. 외부 의존성 0, 스크립트 0 — 인쇄와 첨부에 그대로 쓴다.
데이터는 safety_report.build() 가 만든 것을 받기만 한다.
"""
from pathlib import Path
import html


def _pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def _bar(v, target):
    w = max(0.0, min(1.0, v or 0.0)) * 100
    color = "#1e7a46" if (v or 0) >= target else "#a62a2a"
    return (f'<div class="bar"><div class="fill" style="width:{w:.1f}%;'
            f'background:{color}"></div>'
            f'<div class="tick" style="left:{target * 100:.1f}%"></div></div>')


def write(rep: dict, path: Path) -> Path:
    m = rep["standard"]["metric"]
    tgt = rep["standard"]["target"]
    cov = rep["coverage"]
    ok = rep["verdict"]["passes"]
    pres = rep["prescription"]
    E = html.escape

    lv_rows = "".join(
        "<tr><td>{}</td><td class=n>{:.1f}m</td><td class=n>{}</td>"
        "<td class=n>{}</td><td class=n>{}</td></tr>".format(
            "지상층" if k == "0" else f"{k}층", v["floor_z_m"], v["voxels"],
            _pct(v["spatial_coverage"]), _pct(v["risk_coverage"]))
        for k, v in rep["coverage"]["by_level"].items())

    zn_rows = "".join(
        "<tr><td>{}</td><td class=n>{}</td><td class=n>{}</td>"
        "<td class=n>{}</td><td>{}</td></tr>".format(
            E(k), v["weight"], v["voxels"], _pct(v["coverage"]),
            _bar(v["coverage"], tgt))
        for k, v in sorted(rep["coverage"]["by_zone"].items(),
                           key=lambda kv: -kv[1]["weight"]))

    curve_rows = "".join(
        "<tr class='{}'><td class=n>{}</td><td class=n>{}</td>"
        "<td class=n>{}</td></tr>".format(
            "hit" if r[m] >= tgt else "", r["n_cameras"], _pct(r[m]),
            r["fail_voxels"])
        for r in rep["options"]["add_curve"])

    blind_rows = "".join(
        "<tr><td>{}</td><td class=n>{:.0f}, {:.0f}</td><td class=n>{}</td>"
        "<td>{}</td><td class=n>{}</td><td class=n>{:.3f}</td><td>{}</td></tr>".format(
            E(b["voxel_id"]), b["x"], b["y"],
            "지상" if b["level"] == 0 else f"{b['level']}층",
            E(", ".join(b["zones"]) or "—"), b["w"], b["P_total"], E(b["reason"]))
        for b in rep["blind_spots"][:40])

    lim = "".join(f"<li>{E(x)}</li>" for x in rep["basis"]["limits"])

    # 시간대별 위험구역 진단
    tp = rep.get("time_phased")
    if tp:
        win_rows = "".join(
            "<tr class='{}'><td>{}</td><td>{}</td><td class=n>{}–{}</td>"
            "<td>{}</td><td class=n>{}</td><td class=n>−{:.3f}</td>"
            "<td class=n><b>{}</b></td><td>{}</td></tr>".format(
                "bad" if not r["passes"] else "",
                E(r["window"]["id"]), E(r["window"]["label"]),
                E(r["window"]["from"]), E(r["window"]["to"]),
                E(", ".join(r["active_zones"])), _pct(r["base_score"]),
                r["penalty_total"], _pct(r["scored"]), E(r["verdict"]))
            for r in tp["windows"])
        worst = next(r for r in tp["windows"]
                     if r["window"]["id"] == tp["worst_window"])
        zone_rows = "".join(
            "<tr class='{}'><td>{}</td><td class=n>{}</td><td class=n>{}</td>"
            "<td class=n>{}</td><td class=n>{}</td><td class=n>−{:.3f}</td>"
            "<td>{}</td></tr>".format(
                "bad" if z["critical_fail"] else "",
                E(z["zone"]), z["weight"], z["voxels"], _pct(z["coverage"]),
                _pct(z["required"]), z["penalty"],
                "치명 미달" if z["critical_fail"] else
                ("미달" if not z["meets"] else "충족"))
            for z in worst["zones"])
        pr = tp["penalty_rule"]
        req = " · ".join(f"가중치 {k}→{v:.0%}" for k, v in
                         sorted(pr["required_by_weight"].items(), reverse=True))
        time_html = f"""
<h2>7. 시간대별 위험구역 진단</h2>
<p class="note">위험구역은 하루 내내 같지 않다. 시간대마다 열려 있는 구역이 다르므로,
 고정된 카메라 배치가 <b>그때그때 위험한 곳을 보고 있는지</b>를 따로 판정한다.
 <b>종합은 최악의 시간대로 대표한다</b> — 평균을 쓰면 위험 시간대의 실패가
 한가한 시간대에 가려진다.</p>
<div class="warn"><b>감점 규칙.</b> 구역마다 요구 커버리지가 다르다 ({E(req)}).
 못 미치면 <b>감점 = {pr['penalty_k']} × 가중치 × 미달폭</b> 이다. 같은 미달폭이라도
 가중치가 높은 구역이 더 아프다. 그리고 <b>가중치 {pr['critical_weight']} 구역이
 요건에 미달하면 점수와 무관하게 전체를 미달로 확정한다</b> — 안전기준은 평균으로
 면제되지 않는다.</div>
<table>
 <thead><tr><th>구간</th><th>작업</th><th class=n>시각</th><th>열린 위험구역</th>
  <th class=n>기본</th><th class=n>감점</th><th class=n>최종</th><th>판정</th></tr></thead>
 <tbody>{win_rows}</tbody>
</table>
<p class="note"><b>최악 시간대 {E(worst['window']['id'])}
 ({E(worst['window']['label'])})</b> 의 구역별 내역</p>
<table>
 <thead><tr><th>위험구역</th><th class=n>가중치</th><th class=n>복셀</th>
  <th class=n>커버리지</th><th class=n>요구</th><th class=n>감점</th>
  <th>판정</th></tr></thead>
 <tbody>{zone_rows}</tbody>
</table>
<p class="note">근거: {E(tp['basis'][:300])}</p>
"""
    else:
        time_html = ""

    gap_txt = "" if ok else f"&nbsp;(부족 {rep['verdict']['gap'] * 100:.1f}%p)"
    v_bg = "#eff7f2" if ok else "#fbf0f0"
    v_bd = "#1e7a46" if ok else "#a62a2a"
    spec = rep["basis"]["camera_spec"]
    rho = rep["basis"]["rho_measured_px"]

    doc = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>스마트 안전보고서 — AI CCTV 커버리지 진단</title>
<!-- 인라인 파비콘. 없으면 브라우저가 /favicon.ico 를 찾다 404 를 남긴다 -->
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%230b4f8a'/%3E%3Ccircle cx='8' cy='8' r='3' fill='%23fff'/%3E%3C/svg%3E">
<style>
 @page {{ size: A4; margin: 16mm; }}
 body{{font:13px/1.6 "Malgun Gothic","맑은 고딕",system-ui,sans-serif;color:#16191d;
   max-width:900px;margin:0 auto;padding:24px}}
 h1{{font-size:20px;margin:0 0 4px}}
 h2{{font-size:15px;margin:26px 0 8px;padding-bottom:5px;border-bottom:1px solid #d8dde3}}
 .sub{{color:#5c6570;font-size:12px;margin-bottom:18px}}
 .verdict{{padding:14px 16px;border-radius:6px;margin:16px 0;
   background:{v_bg};border-left:5px solid {v_bd}}}
 .verdict b{{font-size:22px}}
 table{{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0}}
 th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #e3e7ec}}
 th{{background:#f6f8fa;color:#5c6570;font-weight:600}}
 td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
 tr.hit td{{background:#f2f9f5}}
 tr.bad td{{background:#fdf3f3}}
 .bar{{position:relative;height:9px;background:#eceff3;border-radius:5px;min-width:120px}}
 .fill{{height:100%;border-radius:5px}}
 .tick{{position:absolute;top:-2px;width:2px;height:13px;background:#16191d}}
 .note{{color:#5c6570;font-size:11.5px;margin-top:6px}}
 .warn{{background:#fdf7ed;border-left:4px solid #b8860b;padding:10px 12px;
   border-radius:4px;font-size:12px;margin:10px 0}}
 ul{{margin:6px 0 0 18px;padding:0}}
 li{{margin:3px 0;font-size:11.5px;color:#5c6570}}
 footer{{margin-top:30px;padding-top:12px;border-top:1px solid #d8dde3;
   color:#5c6570;font-size:11px}}
</style></head><body>

<h1>스마트 안전보고서 — AI CCTV 커버리지 진단</h1>
<div class="sub">계획서 {E(rep['plan']['path'])} · 카메라 {rep['plan']['cameras']}대 ·
 현장 {rep['site']['width_m']:.0f}×{rep['site']['depth_m']:.0f}m ·
 복셀 {rep['site']['voxels']}개 / {rep['site']['levels']}개 층</div>

<div class="verdict">
 <b>{_pct(rep['verdict']['value'])}</b> / 목표 {tgt:.0%}
 &nbsp;→&nbsp; <b>{'기준 충족' if ok else '기준 미달'}</b>{gap_txt}
 <div class="note">잣대: {E(m)} — 임계 P_total ≥ {rep['standard']['threshold']} 를
  넘는 복셀의 위험가중 비율</div>
</div>

<div class="warn"><b>기준값 주의.</b> {E(rep['standard']['note'])}</div>

<h2>1. 처방</h2>
<div class="verdict" style="background:#eef3f9;border-left-color:#0b4f8a">
 <b style="font-size:15px">[{E(pres['verdict'])}]</b>
 <div style="margin-top:6px">{E(pres['text'].replace('**', ''))}</div>
</div>
<table>
 <thead><tr><th>대안</th><th class=n>대수</th><th class=n>{E(m)}</th>
  <th class=n>미달복셀</th></tr></thead>
 <tbody>
  <tr><td>현 계획서</td><td class=n>{cov['overall']['n_cameras']}</td>
   <td class=n>{_pct(cov['overall'][m])}</td>
   <td class=n>{cov['overall']['fail_voxels']}</td></tr>
  <tr><td>같은 대수 재배치</td>
   <td class=n>{rep['options']['reallocate']['n_cameras']}</td>
   <td class=n>{_pct(rep['options']['reallocate'][m])}</td>
   <td class=n>{rep['options']['reallocate']['fail_voxels']}</td></tr>
  <tr><td>후보 전량 투입 (상한)</td>
   <td class=n>{rep['options']['ceiling']['n_cameras']}</td>
   <td class=n>{_pct(rep['options']['ceiling'][m])}</td>
   <td class=n>{rep['options']['ceiling']['fail_voxels']}</td></tr>
 </tbody>
</table>

<h2>2. 증설 대수별 도달 커버리지</h2>
<p class="note">현 계획서 카메라를 그대로 두고 한 대씩 더한 결과다.
 음영이 목표 달성 지점.</p>
<table><thead><tr><th class=n>총 대수</th><th class=n>{E(m)}</th>
 <th class=n>미달복셀</th></tr></thead>
<tbody>{curve_rows}</tbody></table>

<h2>3. 층별 커버리지</h2>
<table><thead><tr><th>층</th><th class=n>바닥 높이</th><th class=n>복셀</th>
 <th class=n>공간</th><th class=n>위험가중</th></tr></thead>
<tbody>{lv_rows}</tbody></table>

<h2>4. 위험구역별 커버리지</h2>
<table><thead><tr><th>위험구역</th><th class=n>가중치</th><th class=n>복셀</th>
 <th class=n>커버리지</th><th>목표 {tgt:.0%} 대비</th></tr></thead>
<tbody>{zn_rows}</tbody></table>

<h2>5. 사각지대 — 상위 40개</h2>
<p class="note">전체 {len(rep['blind_spots'])}개 중 위험가중치가 높은 순.
 원인은 세 축(ρ 해상도 / θ 부감각 / 가림) 중 가장 크게 깎은 것이다.</p>
<table><thead><tr><th>복셀</th><th class=n>위치(m)</th><th class=n>층</th>
 <th>위험구역</th><th class=n>가중치</th><th class=n>P_total</th>
 <th>원인</th></tr></thead>
<tbody>{blind_rows}</tbody></table>

<h2>6. 산출 근거</h2>
<table>
 <tr><th>검출기</th><td>{E(str(rep['basis']['detector']))} —
  {E(str(rep['basis']['detector_weights']))}</td></tr>
 <tr><th>검출확률 곡선</th><td>{E(rep['basis']['curve'])} ·
  ρ 실사진 실측 R² {rep['basis'].get('r2_rho_native')} ·
  ρ 실측 범위 {rho[0]:.0f}–{rho[1]:.0f}px ·
  θ·o 는 합성 격자 (R² {rep['basis'].get('r2_full_grid_synthetic_rho', '별도 파일')})</td></tr>
 <tr><th>카메라 사양</th><td>{spec['img_w']}×{spec['img_h']} ·
  수평화각 {spec['hfov_deg']:.0f}°</td></tr>
</table>
<p class="note"><b>한계</b></p><ul>{lim}</ul>
{time_html}

<footer>BIGB — AI CCTV 배치 적정성 평가 모델 · 제17회 LH 국토기술대전<br>
 이 보고서의 수치는 전부 계산 결과이며 문서에서 임의로 만들지 않는다.</footer>
</body></html>"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path
