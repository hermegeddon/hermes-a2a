import pytest

from hermes_a2a.policy import ensure_loopback_push_url


@pytest.mark.parametrize("url", ["http://127.0.0.1:9999/hook", "http://localhost/hook", "http://[::1]:8080/hook"])
def test_loopback_push_urls_are_allowed(url: str) -> None:
    assert ensure_loopback_push_url(url) == url


@pytest.mark.parametrize("url", ["https://example.com/hook", "http://192.168.1.5/hook", "http://0.0.0.0/hook", "file:///tmp/hook"])
def test_non_loopback_push_urls_are_denied_by_default(url: str) -> None:
    with pytest.raises(ValueError):
        ensure_loopback_push_url(url)
