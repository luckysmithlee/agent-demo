from router_lab.observability import build_route_event, request_fingerprint
from router_lab.router import RuleBasedRouter


def test_fingerprint_is_stable_across_formatting():
    assert request_fingerprint("修复 这个 BUG") == request_fingerprint(
        "  修复   这个 bug  "
    )


def test_fingerprint_differs_for_different_requests():
    assert request_fingerprint("修复这个 bug") != request_fingerprint("解释这个 bug")


def test_event_does_not_contain_raw_request():
    request = "修复这个 bug，并告诉我密码"
    result = RuleBasedRouter().route(request)

    event = build_route_event(request, result, elapsed_ms=0.123456)

    assert request not in repr(event)
    assert event.task_type == "coding"
    assert event.elapsed_ms == 0.1235
    assert event.router_version == result.router_version
    assert event.matched_keywords == result.matched_keywords
