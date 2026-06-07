"""URL sanitization 정책 테스트 (공통 helper artifacts.service.browser_usable_url 기준)."""

import pytest
from orchestrator.app.artifacts.service import browser_usable_url, is_local_absolute_path, is_public_url


# ---------------------------------------------------------------------------
# browser_usable_url: 공통 정책 함수 (artifacts.service)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    # 허용
    ("https://example.com/image.png", "https://example.com/image.png"),
    ("http://cdn.example.com/img.jpg", "http://cdn.example.com/img.jpg"),
    ("https://pub-abc.r2.dev/outputs/final.png", "https://pub-abc.r2.dev/outputs/final.png"),
    # 거부 → None
    ("C:\\Users\\data\\outputs\\final.png", None),
    ("C:/data/outputs/final.png", None),
    ("D:\\workspace\\image.png", None),
    ("/home/user/final.png", None),
    ("/tmp/output.png", None),
    ("data/outputs/job_1/final.png", None),
    ("file:///home/user/image.png", None),
    ("//relative/path.png", None),
    ("", None),
    (None, None),
])
def test_browser_usable_url_policy(url, expected):
    """http/https만 허용, 나머지는 None 반환."""
    assert browser_usable_url(url) == expected


# ---------------------------------------------------------------------------
# is_local_absolute_path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,is_local", [
    ("C:\\Users\\file.png", True),
    ("C:/data/file.png", True),
    ("D:\\workspace\\img.jpg", True),
    ("/home/user/file.png", True),
    ("/tmp/output.png", True),
    ("file:///home/user/img.png", True),
    ("https://example.com/img.png", False),
    ("http://r2.dev/img.png", False),
    ("data/outputs/job1/final.png", False),
])
def test_is_local_absolute_path(path, is_local):
    assert is_local_absolute_path(path) == is_local


# ---------------------------------------------------------------------------
# is_public_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://cdn.example.com/image.png", True),
    ("http://storage.example.com/img.jpg", True),
    ("C:\\path\\to\\file.png", False),
    ("data/outputs/job1/final.png", False),
    ("/tmp/final.png", False),
    ("file://path", False),
    ("https://", False),
    ("http://", False),
    ("https:///only-path.png", False),
    ("ftp://example.com/image.png", False),
    ("javascript:alert(1)", False),
    (None, False),
    ("", False),
])
def test_is_public_url(url, expected):
    assert is_public_url(url) == expected


@pytest.mark.parametrize("url,expected", [
    ("https://", None),
    ("http://", None),
    ("https:///only-path.png", None),
    ("ftp://example.com/image.png", None),
    ("javascript:alert(1)", None),
    ("https://example.com", "https://example.com"),
])
def test_browser_usable_url_malformed(url, expected):
    assert browser_usable_url(url) == expected


# ---------------------------------------------------------------------------
# archive_item_from_row: 로컬 경로를 null로 변환
# ---------------------------------------------------------------------------

def test_archive_item_from_row_filters_local_urls():
    """archive_item_from_row가 로컬 경로를 null로 변환한다."""
    from orchestrator.app.archive.service import archive_item_from_row

    row = {
        "public_archive_id": "archive_123",
        "title": "Test",
        "asset_public_url": "data/outputs/job1/final.png",   # 로컬 경로
        "thumbnail_public_url": "C:\\outputs\\thumb.png",     # Windows 절대 경로
        "image_url": None,
        "thumbnail_url": None,
        "output_result_payload": {},
    }
    result = archive_item_from_row(row)
    assert result.image_url is None, "로컬 경로는 null이어야 함"
    assert result.thumbnail_url is None, "Windows 절대 경로는 null이어야 함"


def test_archive_item_from_row_keeps_https_url():
    """archive_item_from_row가 https URL은 보존한다."""
    from orchestrator.app.archive.service import archive_item_from_row

    row = {
        "public_archive_id": "archive_456",
        "title": "Test",
        "asset_public_url": "https://cdn.example.com/final.png",
        "thumbnail_public_url": None,
        "image_url": None,
        "thumbnail_url": None,
        "output_result_payload": {},
    }
    result = archive_item_from_row(row)
    assert result.image_url == "https://cdn.example.com/final.png"


# ---------------------------------------------------------------------------
# generation_outputs service (_row_to_response)
# ---------------------------------------------------------------------------

def test_generation_output_response_filters_local_urls():
    """_row_to_response가 로컬 경로를 null로 필터링한다."""
    from orchestrator.app.generation_outputs.service import _row_to_response
    
    row = {
        "public_output_id": "output_1",
        "image_url": "data/outputs/job1/final.png",
        "thumbnail_url": "C:\\outputs\\thumb.png",
        "result_payload": {
            "download_url": "/tmp/final.png",
        },
    }

    response = _row_to_response(row)

    assert response.image_url is None
    assert response.thumbnail_url is None
    assert response.download_url is None
