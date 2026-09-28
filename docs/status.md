# 현재 상태 (이어받기용)

마지막 갱신: 2026-09-28

## 기준선
- 원본: `Jissen! Mahjong Shinan (Japan).sfc` SHA-1 `0b7785d0…b396`
- 제품 빌드: `python3 tools/build.py` → `build/Jissen_Mahjong_Shinan_KR.sfc`, `.ips`, `charmap_ko.tsv`
- 에뮬레이터: `tools/emu/setup.sh` (snes9x `1bcc369e` + 추적 패치)

## 완료 (런타임 확인됨)
- PrintString 1,118문자열, TilePrint(TPG 99, TPC 17, `$01:D37D` 반장 계속 확인창).
- 그림 글자: 타이틀, 메인 메뉴, 이름 입력(탭·한글 격자), 상대 선택(이름·단위·결정), 단위 상태 명패, 플레이 데이터, 캐릭터 데이터,
  환경 설정, 종료 확인창, 룰 설정, 지남 소개 간판, 월례 대회(배너·대진표·우승자), 단위 심사(배너·헤더·순위표),
  대국 화면(버튼·배지·바람 표시·국 배지·점수표 계·남은패·역).
- 작업 사양: `tools/gfxjobs.py`(원문 전사 `text/jp/GFX.tsv`, 번역 `text/ko/GFX.tsv`), 코드가 만드는 타일맵은 `data/*map.bin`에 캡처해 제자리 되쓰기.
- 테스트: `python3 -m pytest -q tests`.

## 남은 일
1. 단위 심사 판정 화면: 본문은 런타임 확인(불합격 경로). 제목 "심사 판정"(#136)은 에셋 합성 미리보기로만 확인했고, 합격 경로와 #141 결과 조각은 미확인.
2. 엔딩/스태프롤 여부 미확인.
3. 번역 검수: 모든 번역은 `draft`. 사람 검수 후 `reviewed`로 바꿔야 릴리스 후보.
4. 실기(실제 SNES/다른 에뮬레이터) 확인은 아직 안 함.

## 확인된 주의점
- 일본어판에서 만든 세이브 스테이트에는 VRAM이 들어 있어, 한글판에서 불러오면 이미 그려진 화면이 일본어로 남는다. 한글판에서 새로 부팅해 만든 스테이트(`work/kr/*.state`)를 쓴다.

## 로컬 파생 데이터 (커밋하지 않음)
- `text/jp/*.tsv`(GFX.tsv 제외): `python3 tools/extract.py && python3 tools/tiletext_extract.py`로 원본 ROM에서 재생성.
- `data/*map.bin`: 코드가 조립하는 타일맵을 에뮬레이터 VRAM에서 캡처한 값. 없으면 빌드가 실패한다. 기대 해시:
  - `data/exam_banner_bg1map.bin` sha256 `c83a5e11b1eec889967637e22a04e6218240532a1e75d5526b5d24cb8fe7679a`
  - `data/exam_header_bg3map.bin` sha256 `39d7802eac1c892f89e2a2d26cbbdf731a9f09e300202e81083fe1e6d6b31d71`
  - `data/exam_rank_bg1map.bin` sha256 `3238b35a24a465424b0f21e2b92e68ee8da862658e5ad9fec902497e264496a4`
