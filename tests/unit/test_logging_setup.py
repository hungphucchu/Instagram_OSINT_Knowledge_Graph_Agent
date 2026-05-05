"""Unit tests for ``src/myproject/logging_setup.py``."""

from __future__ import annotations

import json
import logging

from myproject.logging_setup import (
    configure_logging,
    get_request_id,
    log_event,
    new_request_id,
    reset_request_id,
    set_request_id,
)


def test_logging_setup_module_imports() -> None:
    import myproject.logging_setup  # noqa: F401


def test_new_request_id_format() -> None:
    rid = new_request_id()
    assert rid.startswith("req_")
    assert len(rid) >= len("req_") + 6


def test_request_id_context_roundtrip() -> None:
    token = set_request_id("req_test")
    try:
        assert get_request_id() == "req_test"
    finally:
        reset_request_id(token)
    assert get_request_id() != "req_test"


def test_json_formatter_emits_required_fields() -> None:
    """The JSON formatter renders timestamp/level/module/request_id/message/extra."""
    # Format a synthetic record directly to avoid pytest's caplog plugin owning
    # the root logger and intercepting records before our handler sees them.
    from myproject.logging_setup import _JsonFormatter, _RequestIdFilter

    formatter = _JsonFormatter()
    request_filter = _RequestIdFilter()
    record = logging.LogRecord(
        name="myproject.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=None,
        exc_info=None,
    )
    record.extra_fields = {"k": 1, "name": "alice"}
    token = set_request_id("req_unit")
    try:
        request_filter.filter(record)
        line = formatter.format(record)
    finally:
        reset_request_id(token)

    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req_unit"
    assert payload["module"] == "myproject.test"
    assert payload["level"] == "INFO"
    assert payload["extra"] == {"k": 1, "name": "alice"}
    assert "timestamp" in payload


def test_log_event_calls_logger_with_extra_fields(monkeypatch) -> None:  # noqa: ANN001
    """``log_event`` forwards arbitrary kwargs through ``extra={'extra_fields': ...}``."""
    captured: list[dict[str, object]] = []

    class _StubLogger:
        def log(self, level: int, message: str, *, extra: dict[str, object] | None = None) -> None:
            captured.append({"level": level, "message": message, "extra": extra})

    log_event(_StubLogger(), "ping", k=1)  # type: ignore[arg-type]
    assert captured == [
        {"level": logging.INFO, "message": "ping", "extra": {"extra_fields": {"k": 1}}}
    ]


def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging twice does not double-install handlers."""
    configure_logging("INFO")
    before = len(logging.getLogger().handlers)
    configure_logging("INFO")
    after = len(logging.getLogger().handlers)
    assert before == after
