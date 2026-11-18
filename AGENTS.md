# AGENTS.md

2D 게임 프로그래밍 텀프로젝트 **Over the Wall** (Python, pico2d).
와이어로 날아 거인을 베고 적 요새를 함락하는 2D 횡스크롤 와이어 액션 게임.

## 실행
```bash
pip install pico2d
python main.py
```
- 리소스 재생성: `pip install pillow` 후 `python tools/make_sprites.py`
  → `resource/*.png`, `resource/*_meta.json`
- 모든 이미지는 외부 리소스 없이 `tools/make_sprites.py`가 코드로 그린다. 그림을 바꿀 때는 png를 직접 고치지 말고 이 스크립트를 고친 뒤 다시 실행한다.
- Windows 환경. 폰트 경로는 `C:/Windows/Fonts/` (config.py).

## 구조
- `main.py`: 진입점. 작업 폴더를 맞추고 `title_mode`로 시작
- `game_framework.py`: 모드 전환 (`change_mode` / `push_mode` / `pop_mode`)
- 모드: `title_mode` → `play_mode` → `upgrade_mode`(카드 선택) → `result_mode`
- `game_world.py`: 레이어별 오브젝트 관리, 충돌 판정
- `config.py`: 화면 크기, 길 5줄 좌표, 레이어 상수, 구간(ZONES) 데이터
- `state_machine.py`: 플레이어 상태 전이 (와이어, 착지, 낙하 등)
- 오브젝트: `player`, `giant`, `ally`, `cannon`, `projectile`, `wall`, `fortress`, `effect`
- 화면: `background`, `camera`, `render`, `ui`
- `upgrade.py`: 강화 카드, `map_data.py`: 맵 데이터
- 기획 문서: `PRD.md` (최종 목표). 지금 코드는 프로토타입이며 PRD를 하나씩 적용해 나가는 중

## 코드 규칙
- 주석과 UI 문자열은 한글
- 수치·데이터는 가능하면 `config.py`에 모은다

## 커밋 규칙
- 기능 하나를 끝낼 때마다 커밋, 한 커밋에 기능 하나
- 한글 한 줄 메시지
- **`[프로토타입]` 머리말은 더 이상 붙이지 않는다** (README에 남아 있는 규칙보다 이쪽이 우선)
  - 예: `동료 구분: 리바이는 작게, 미카사는 빨간 목도리`
- 사용자가 요청할 때만 커밋한다
