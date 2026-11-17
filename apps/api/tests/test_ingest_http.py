import httpx
import pytest

from fcsl_api.ingest.http import PoliteClient, SourceBlocked


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, tmp_path=None, ft=None, **kw):
    ft = ft or FakeTime()
    client = PoliteClient(
        "https://example.test",
        min_interval_s=kw.pop("min_interval_s", 1.0),
        cache_dir=tmp_path,
        user_agent="test-agent",
        transport=httpx.MockTransport(handler),
        clock=ft.clock,
        sleep=ft.sleep,
        wall_clock=ft.clock,
        **kw,
    )
    return client, ft


def test_rate_limit_spaces_requests():
    client, ft = make_client(lambda r: httpx.Response(200, json={"ok": True}), min_interval_s=2.0)
    for _ in range(3):
        client.get_json("/x")
    assert sum(ft.sleeps) >= 2 * 2.0


@pytest.mark.parametrize("status", [403, 429])
def test_blocked_raises_without_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    client, _ = make_client(handler)
    with pytest.raises(SourceBlocked):
        client.get_json("/x")
    assert len(calls) == 1


def test_retries_5xx_then_succeeds():
    responses = iter([httpx.Response(503), httpx.Response(500), httpx.Response(200, json=[1])])
    calls = []

    def handler(request):
        calls.append(request)
        return next(responses)

    client, _ = make_client(handler)
    assert client.get_json("/x") == [1]
    assert len(calls) == 3


def test_gives_up_after_retries_on_5xx():
    client, _ = make_client(lambda r: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("/x")


def test_cache_hit_avoids_request(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"n": len(calls)})

    client, _ = make_client(handler, tmp_path)
    assert client.get_json("/x", {"b": 1, "a": 2}, cache_ttl_s=60) == {"n": 1}
    assert client.get_json("/x", {"a": 2, "b": 1}, cache_ttl_s=60) == {"n": 1}
    assert len(calls) == 1


def test_cache_expired_refetches(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"n": len(calls)})

    client, ft = make_client(handler, tmp_path)
    assert client.get_json("/x", cache_ttl_s=60) == {"n": 1}
    ft.now += 61
    assert client.get_json("/x", cache_ttl_s=60) == {"n": 2}
