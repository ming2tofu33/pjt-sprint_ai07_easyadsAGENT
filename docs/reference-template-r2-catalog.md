# 레퍼런스 템플릿 R2 카탈로그

서비스에서 영구적으로 사용할 레퍼런스 이미지는 코드에 이미지 파일을 직접 커밋하지 않고, 메타데이터와 R2 object key만 커밋합니다.

## 파일 위치

- 메타데이터 카탈로그: `orchestrator/app/reference_catalog/permanent_templates.json`
- 로컬 업로드 준비 폴더: `data/reference_templates/inbox/`
- 업로드 헬퍼: `scripts/upload_reference_templates_to_r2.py`

`data/` 폴더는 git에 포함하지 않는 원본 준비 공간입니다. 실제 서비스 이미지는 Cloudflare R2에 올라가고, 카탈로그에는 템플릿 ID와 R2 object key만 남깁니다.

## R2 경로 규칙

각 이미지의 object key는 아래 형식을 사용합니다.

```text
reference-templates/v1/<template_id>/source.png
```

예시:

```text
template_id: ref_cafe_1_0_007
source file: data/reference_templates/inbox/1_0.png
object key: reference-templates/v1/ref_cafe_1_0_007/source.png
```

## 업로드 전 확인

```bash
uv run python scripts/upload_reference_templates_to_r2.py
```

기본 실행은 dry-run입니다. 로컬 이미지 파일과 카탈로그의 R2 object key가 모두 매칭되는지만 확인합니다.

특정 템플릿만 확인할 수도 있습니다.

```bash
uv run python scripts/upload_reference_templates_to_r2.py --template-id ref_cafe_1_0_007
```

## 실제 업로드

아래 환경 변수가 설정되어 있어야 합니다.

```bash
EASYADS_ENABLE_R2_UPLOAD=true
EASYADS_R2_BUCKET=<bucket-name>
EASYADS_R2_ENDPOINT_URL=<cloudflare-r2-endpoint>
EASYADS_R2_ACCESS_KEY_ID=<access-key>
EASYADS_R2_SECRET_ACCESS_KEY=<secret-key>
EASYADS_R2_URL_MODE=public
EASYADS_R2_PUBLIC_BASE_URL=<public-r2-or-cdn-base-url>
```

실제 업로드:

```bash
uv run python scripts/upload_reference_templates_to_r2.py --upload
```

## 프론트에서 이미지가 보이는 조건

`EASYADS_R2_PUBLIC_BASE_URL`이 설정되어 있으면 `/api/v1/references` 응답의 `thumbnail_url`, `preview_url`에 브라우저에서 접근 가능한 URL이 내려갑니다.

이 값이 없으면 카탈로그 검색은 되지만 이미지 URL은 비어 있을 수 있습니다. 이 경우 프론트는 빈 상태 또는 이미지 없는 카드로 표시해야 합니다.

## 메타데이터 수정 방법

새 레퍼런스를 추가하거나 분류를 바꿀 때는 `permanent_templates.json`에서 아래 값을 수정합니다.

- `title`: UI에 표시되는 이름
- `category`: 대표 카테고리
- `tags`: 검색 태그
- `business_types`: 업종 필터
- `ad_formats`, `platforms`, `aspect_ratio`: 광고 형식 필터
- `style_keywords`, `color_palette`, `layout_hint`: 생성 요청에 넘길 스타일 힌트
- `metadata.source_file`: 로컬 준비 폴더의 원본 파일명
- `metadata.r2_object_key`: 실제 R2 업로드 경로

로컬 파일명을 바꾸면 `metadata.source_file`과 업로드 dry-run 결과를 반드시 다시 확인합니다.
