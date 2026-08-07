@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
  echo Re:Space 입력 검사
  echo.
  echo   run.bat ^<building_dir^>        예: run.bat data\buildings\esquisse-gasan
  echo   run.bat test                   테스트 전체 실행
  echo.
  exit /b 1
)

if /i "%~1"=="test" (
  python -m unittest discover -s tests -t .
  exit /b %errorlevel%
)

python -m engine.inspect %*
exit /b %errorlevel%
