import httpx
import pytest
import respx

from conftest import make_client
from twila_credicarro import CredicarroApiError, CredicarroResilienceOptions, CredicarroTimeoutError
from twila_credicarro._internal.http.api_response import ApiResponse
from twila_credicarro._internal.resilience.resilience_pipeline import ResiliencePipeline

PROPOSAL_ID = "bea8d060-f93d-48eb-b6c4-45f64483cdd9"

FAST_OPTIONS = CredicarroResilienceOptions(
    total_timeout_ms=5_000,
    attempt_timeout_ms=1_000,
    max_retry_attempts=3,
    retry_base_delay_ms=1,
)


def _response(status_code: int) -> ApiResponse:
    return ApiResponse(status_code=status_code, body={}, headers={})


def test_defaults_follow_the_documentation() -> None:
    options = CredicarroResilienceOptions()

    assert options.total_timeout_ms == 30_000
    assert options.attempt_timeout_ms == 10_000
    assert options.document_upload_attempt_timeout_ms == 60_000
    assert options.max_retry_attempts == 3
    assert options.retry_base_delay_ms == 500
    assert options.retry_on_500 is True
    assert options.disable_automatic_idempotency_key is False
    assert options.circuit_breaker_failure_ratio == 0.5
    assert options.circuit_breaker_sampling_duration_ms == 30_000
    assert options.circuit_breaker_minimum_throughput == 10
    assert options.circuit_breaker_break_duration_ms == 15_000


def test_successful_response_does_not_retry() -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        return _response(200)

    assert pipeline.execute(True, attempt).status_code == 200
    assert calls["count"] == 1


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_statuses_are_retried_when_retry_safe(status: int) -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        return _response(status) if calls["count"] < 3 else _response(200)

    assert pipeline.execute(True, attempt).status_code == 200
    assert calls["count"] == 3


def test_500_is_not_retried_when_retry_on_500_is_disabled() -> None:
    pipeline = ResiliencePipeline(CredicarroResilienceOptions(retry_base_delay_ms=1, retry_on_500=False))
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        return _response(500)

    assert pipeline.execute(True, attempt).status_code == 500
    assert calls["count"] == 1


def test_transient_response_does_not_retry_when_not_retry_safe() -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        return _response(503)

    assert pipeline.execute(False, attempt).status_code == 503
    assert calls["count"] == 1


def test_network_error_retries_and_eventually_raises() -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(CredicarroTimeoutError, match="ConnectError"):
        pipeline.execute(True, attempt)

    assert calls["count"] == FAST_OPTIONS.max_retry_attempts


def test_network_error_is_not_retried_when_not_retry_safe() -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(CredicarroTimeoutError, match="ConnectError"):
        pipeline.execute(False, attempt)

    assert calls["count"] == 1


def test_attempt_timeout_becomes_credicarro_timeout_error() -> None:
    pipeline = ResiliencePipeline(FAST_OPTIONS)

    def attempt() -> ApiResponse:
        raise httpx.ReadTimeout("lento")

    with pytest.raises(CredicarroTimeoutError) as error:
        pipeline.execute(True, attempt)

    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_total_timeout_raises_timeout_error() -> None:
    options = CredicarroResilienceOptions(
        total_timeout_ms=50,
        attempt_timeout_ms=50,
        max_retry_attempts=5,
        retry_base_delay_ms=200,
    )
    pipeline = ResiliencePipeline(options)
    calls = {"count": 0}

    def attempt() -> ApiResponse:
        calls["count"] += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(CredicarroTimeoutError):
        pipeline.execute(True, attempt)

    assert calls["count"] >= 1


def test_circuit_breaker_opens_after_failure_threshold_and_blocks_next_call() -> None:
    options = CredicarroResilienceOptions(
        total_timeout_ms=5_000,
        attempt_timeout_ms=1_000,
        max_retry_attempts=1,
        circuit_breaker_minimum_throughput=2,
        circuit_breaker_failure_ratio=0.5,
        circuit_breaker_break_duration_ms=60_000,
    )
    pipeline = ResiliencePipeline(options)

    for _ in range(2):
        pipeline.execute(False, lambda: _response(503))

    with pytest.raises(CredicarroTimeoutError):
        pipeline.execute(False, lambda: _response(200))


def test_get_is_retried_through_the_client(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    responses = iter([httpx.Response(503), httpx.Response(200, json={"id_proposta": PROPOSAL_ID})])
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=lambda request: next(responses))
    client = make_client()

    assert client.proposals.get(PROPOSAL_ID).id == PROPOSAL_ID
    client.close()

    assert route.call_count == 2


def test_retry_after_header_is_respected(mock_router: respx.MockRouter, token_route: respx.Route) -> None:
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200, json={"id_proposta": PROPOSAL_ID})]
    )
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=lambda request: next(responses))
    client = make_client()

    client.proposals.get(PROPOSAL_ID)
    client.close()

    assert route.call_count == 2


def test_exhausted_retries_return_the_last_response_as_api_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    route = mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(return_value=httpx.Response(503))
    client = make_client()

    with pytest.raises(CredicarroApiError) as error:
        client.proposals.get(PROPOSAL_ID)
    client.close()

    assert error.value.status_code == 503
    assert route.call_count == 3


def test_request_timeout_from_transport_raises_timeout_error(
    mock_router: respx.MockRouter, token_route: respx.Route
) -> None:
    mock_router.get(f"v2/proposal/{PROPOSAL_ID}").mock(side_effect=httpx.ReadTimeout("lento"))
    client = make_client(max_retry_attempts=2)

    with pytest.raises(CredicarroTimeoutError):
        client.proposals.get(PROPOSAL_ID)
    client.close()
