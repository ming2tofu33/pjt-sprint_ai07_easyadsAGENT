# HTML PPT

이 폴더는 GitHub Pages에서 바로 열 수 있는 HTML 발표 자료입니다.

## 열기

- 로컬 파일로 확인: `docs/PPT/index.html`
- 로컬 서버로 확인: `python -m http.server 8000 --directory docs`
- 서버 실행 후 URL: `http://localhost:8000/PPT/`
- GitHub Pages URL 형식: `https://<github-id>.github.io/<repo-name>/PPT/`

## 발표 조작

- 다음 슬라이드: `Right`, `Space`, `PageDown`
- 이전 슬라이드: `Left`, `PageUp`
- 첫 슬라이드: `Home`
- 마지막 슬라이드: `End`
- 전체 화면: `F` 또는 하단 `Full` 버튼
- 특정 슬라이드 공유: `/PPT/#15`처럼 해시 번호를 붙입니다.

## 수정 위치

- 전체 뷰어와 슬라이드 목록: `index.html`
- 개별 슬라이드: `slide01.html`부터 `slide18.html`
- 공용 아이콘 CSS: `../assets/icons.css`
- PPT 이미지 자산: `../assets/`

슬라이드를 추가할 때는 새 `slideNN.html` 파일을 만든 뒤 `index.html`의 `slideCount`, `slideTitles`, 입력 필드 `max` 값을 함께 수정합니다.
