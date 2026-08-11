"""외부 자료를 입력 계약으로 옮기는 어댑터.

엔진은 어댑터를 모른다. 어댑터가 `building.json` / `floor_plan_*.json` 을 만들고,
엔진은 그 파일만 읽는다. 대시보드와 같은 방향의 단절이다.

- `bdrg`  건축물대장 API → building.json (수치)
- `dxf`   DXF 도면 → floor_plan_NN.json (형상)
"""
