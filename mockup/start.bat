@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AI CCTV 배치 진단 도구 - 실행

REM ---------------------------------------------------------------------
REM  이 파일 하나로 실행한다. 인터넷도, 설치도 필요 없다.
REM
REM  파이썬이 있으면 로컬 서버로 열고, 없으면 index.html 을 파일로 연다
REM  (site.js 가 site.json 과 같은 내용이라 file:// 에서도 뜬다).
REM
REM  2026-08-27 고침. 두 가지가 문제였다.
REM   (1) 확인하는 파일이 옛 뷰어의 data.js / data.json 이었다. 지금 화면은
REM       site.js / site.json 을 읽는다.
REM   (2) 포트가 열려 있는지만 봤다. python -m http.server 는 SO_REUSEADDR 을
REM       쓰므로 이미 떠 있어도 두 번째가 조용히 바인딩된다. 그러면 요청이
REM       둘 중 아무 쪽으로나 가고, 먼저 뜬 서버가 다른 폴더에서 실행된
REM       것이면 화면이 깨진다. 실제로 서버 두 개가 물려 있었다.
REM       이제 HTTP 로 우리 파일이 오는지 확인하고, 이미 정상이면 새로
REM       띄우지 않고 그것을 쓴다.
REM
REM  주의 두 가지.
REM   - 이 파일은 cp949 로 저장한다. em dash 같은 문자를 넣으면 인코딩이
REM     깨져 배치 파일 자체가 실행되지 않는다.
REM   - PowerShell 호출에 for /f 를 쓰지 않는다. 따옴표가 중첩되면서 조용히
REM     깨진다(실제로 그래서 서버가 아예 안 떴다). 종료코드로만 주고받는다.
REM ---------------------------------------------------------------------

set "PORT=8765"
set "ALTPORT=8766"

if not exist "place.html" (
  echo [오류] place.html 이 없습니다. start.bat 을 mockup 폴더 안에서 실행하세요.
  echo        현재 위치: %CD%
  pause
  exit /b 1
)
if not exist "data.js" if not exist "data.json" (
  echo [오류] 뷰 데이터가 없습니다 ^(data.json / data.js^).
  echo        프로젝트 루트에서 다음을 먼저 실행하세요:
  echo            python src
eport.py
  pause
  exit /b 1
)

set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py"
)
if not defined PY goto :openfile

REM --- 이미 정상 서버가 떠 있으면 그것을 쓴다 --------------------------
call :probe %PORT%
if not errorlevel 1 (
  echo 이미 열려 있는 서버를 씁니다 ... http://localhost:%PORT%/
  goto :openbrowser
)

REM 포트는 물려 있는데 우리 것이 아니면 다른 포트로 간다. 겹쳐 띄우면
REM 요청이 엉뚱한 서버로 가므로 반드시 피한다.
call :portbusy %PORT%
if not errorlevel 1 (
  echo [알림] %PORT% 는 다른 프로그램이 쓰고 있어 %ALTPORT% 로 엽니다.
  set "PORT=%ALTPORT%"
)

echo 로컬 서버를 엽니다 ... http://localhost:%PORT%/
start "AI CCTV 뷰어 서버 (닫으면 종료)" /min "%PY%" -m http.server %PORT% --bind 127.0.0.1

REM 뜰 때까지 기다리되 TCP 가 아니라 HTTP 응답으로 확인한다.
call :waitup %PORT%
if errorlevel 1 (
  echo 서버가 뜨지 않았습니다. 파일로 엽니다.
  goto :openfile
)

:openbrowser
start "" "http://localhost:%PORT%/place.html"
echo.
echo  브라우저를 열었습니다.
echo  종료하려면 최소화된 "AI CCTV 뷰어 서버" 창을 닫으세요.
echo.
powershell -NoProfile -Command "Start-Sleep -Seconds 4" >nul 2>&1
exit /b 0

:openfile
echo 파이썬이 없어 index.html 을 파일로 엽니다 ^(site.js 사용^).
start "" "place.html"
powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul 2>&1
exit /b 0

REM --- 우리 서버가 응답하는가. 0 이면 정상 -----------------------------
:probe
powershell -NoProfile -Command "try { $w=[Net.WebRequest]::Create('http://127.0.0.1:%~1/data.json'); $w.Method='HEAD'; $w.Timeout=1500; $r=$w.GetResponse(); $c=[int]$r.StatusCode; $r.Close(); if ($c -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

REM --- 포트를 누가 쓰고 있는가. 0 이면 사용 중 -------------------------
:portbusy
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $a=$c.BeginConnect('127.0.0.1',%~1,$null,$null); if ($a.AsyncWaitHandle.WaitOne(600)) { $c.EndConnect($a); $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

REM --- 최대 6초 기다린다. 0 이면 떴다 ----------------------------------
:waitup
powershell -NoProfile -Command "for ($i=0; $i -lt 24; $i++) { try { $w=[Net.WebRequest]::Create('http://127.0.0.1:%~1/data.json'); $w.Method='HEAD'; $w.Timeout=1000; $r=$w.GetResponse(); $r.Close(); exit 0 } catch { Start-Sleep -Milliseconds 250 } } exit 1" >nul 2>&1
exit /b %errorlevel%
