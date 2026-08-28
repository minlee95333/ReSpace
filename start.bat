@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AI CCTV 배치 적정성 평가

REM =====================================================================
REM  이것 하나만 누르면 된다.
REM
REM    1) 평가를 다시 계산한다 - 입력이 바뀌었을 수 있으므로 늘 최신화한다
REM    2) mockup 의 start.bat 에 넘긴다 - 로컬 서버를 띄우고 브라우저를 연다
REM
REM  계산에 실패하면 화면을 열지 않는다. 옛 수치를 최신인 양 보여주는 것이
REM  가장 나쁘다. 계산 없이 열려면  start.bat /noeval  로 실행한다.
REM
REM  경로에 역슬래시를 쓰지 않는다. 배치를 생성할 때 백슬래시+r 이 CR 로
REM  바뀌어 src 다음이 잘려나간 적이 있다. 슬래시는 파이썬도 cmd 도 받는다.
REM
REM  외부 요청은 0 건이다. 인터넷도 설치도 필요 없다.
REM =====================================================================

if not exist "mockup/index.html" goto :nomockup
if /i "%~1"=="/noeval" goto :launch

REM --- 파이썬 찾기 -----------------------------------------------------
REM  where 로 찾지 않는다. 어떤 환경에서는 where python 이 실패하는데 python
REM  은 실행된다. 실제로 돌려보고 판단하는 것이 유일하게 믿을 수 있다.
set "PYCMD="
python -V >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto :havepy

py -3 -V >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto :havepy

goto :nopython

:havepy
REM --- 입력이 바뀌었을 때만 다시 계산한다 ------------------------------
REM  종전에는 열 때마다 무조건 돌렸다. 현장이 단지 전체로 넓어지면서 그
REM  계산이 55분이 됐고, 버튼을 누른 사람 눈에는 멈춘 것으로 보였다.
REM  "옛 수치를 최신인 양 보여주지 않는다" 는 원칙은 그대로 지킨다 -
REM  입력이 산출물보다 새로우면 계산하고, 아니면 그냥 연다.
%PYCMD% src/needs_eval.py
if errorlevel 1 goto :fresh

echo.
echo   입력이 바뀌었습니다. 평가를 다시 계산합니다.
%PYCMD% src/needs_eval.py --why
%PYCMD% -c "import sys;sys.path.insert(0,'src');import config as c;print('  복셀 %d x %d x %d m 격자 - 카메라 후보를 세는 중입니다.'%(c.SITE_WIDTH_M,c.SITE_DEPTH_M,c.VOXEL_M))" 2>nul
echo.
echo   현장 크기에 따라 수십 분이 걸릴 수 있습니다. 창을 닫지 마세요.
echo   (계산 없이 지금 결과를 보려면 이 창을 닫고  start.bat /noeval  로 실행)
echo.
%PYCMD% src/report.py
if errorlevel 1 goto :failed

echo.
echo   계산 완료. 화면을 엽니다.
goto :launch

:fresh
echo.
echo   산출물이 입력보다 새롭습니다. 다시 계산하지 않고 바로 엽니다.
goto :launch

REM --- 계산 실패: 화면을 열지 않는다 -----------------------------------
:failed
echo.
echo   [실패] 계산이 끝나지 않았습니다. 위 메시지가 원인입니다.
echo.
echo          옛 수치를 최신인 양 보여줄 수 없으므로 화면을 열지 않습니다.
echo          그래도 옛 결과를 보려면  start.bat /noeval  로 실행하세요.
echo.
pause
exit /b 1

REM --- 파이썬 없음 -----------------------------------------------------
:nopython
echo.
echo   [오류] 파이썬을 찾지 못했습니다. python 또는 py 가 PATH 에 있어야 합니다.
echo.
echo          계산 없이 옛 결과를 보려면  start.bat /noeval  로 실행하세요.
echo.
pause
exit /b 1

:launch
if defined AICCTV_NO_LAUNCH goto :dryrun
call "mockup/start.bat"
exit /b 0

:dryrun
echo   [시험] AICCTV_NO_LAUNCH 가 설정되어 브라우저를 열지 않습니다.
exit /b 0

:nomockup
echo [오류] mockup/index.html 이 없습니다.
echo        start.bat 은 프로젝트 최상단에서 실행해야 합니다.
echo        현재 위치: %CD%
pause
exit /b 1
