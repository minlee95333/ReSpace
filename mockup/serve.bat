@echo off
REM 배치 도구를 로컬 서버로 연다 (start.bat 의 단순판).
REM index.html 은 file:// 로 열면 site.js 사본으로 뜨지만, 정상 경로는
REM site.json 을 fetch 하는 쪽이다.
REM
REM start.bat 과 달리 여기서는 중복 확인을 하지 않는다. 이미 8000 에 서버가
REM 떠 있으면 python 이 SO_REUSEADDR 로 조용히 겹쳐 바인딩하므로, 두 번
REM 실행하지 말 것. 평소에는 start.bat 을 쓴다.
cd /d "%~dp0"
echo http://localhost:8000/ 을 브라우저에서 열 것. 종료는 Ctrl+C.
python -m http.server 8000 --bind 127.0.0.1
