@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
  echo Re:Space
  echo.
  echo   run.bat check ^<building_dir^>    도면 입력 검사 ^(격자 그림^)
  echo   run.bat report ^<building_dir^>   분석 실행 ^(result.json + SVG + dashboard.html^)
  echo   run.bat test                    테스트 전체 실행
  echo.
  echo   예: run.bat check data\buildings\esquisse-gasan
  echo       run.bat report data\buildings\esquisse-gasan
  echo.
  echo   결과는 out\ 에 생기며, out\dashboard.html 을 더블클릭하면 열린다.
  echo.
  exit /b 1
)

set VERB=%~1
shift /1

if /i "%VERB%"=="test" (
  python -m unittest discover -s tests -t .
  exit /b %errorlevel%
)

if /i "%VERB%"=="check" (
  python -m engine.inspect %1 %2 %3 %4 %5 %6
  exit /b %errorlevel%
)

if /i "%VERB%"=="report" (
  python -m engine.report %1 %2 %3 %4 %5 %6
  exit /b %errorlevel%
)

echo 알 수 없는 명령: %VERB%
exit /b 1
