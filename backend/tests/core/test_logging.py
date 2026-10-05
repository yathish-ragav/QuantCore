import json
import logging

from quantcore.core.logging import JsonFormatter


def test_json_formatter_emits_stable_operational_fields(monkeypatch):
    monkeypatch.setattr("quantcore.core.logging.settings.ENVIRONMENT", "test")
    record = logging.LogRecord(
        "quantcore.test",
        logging.INFO,
        __file__,
        10,
        "request completed",
        (),
        None,
    )
    record.event = "http.request.completed"
    record.request_id = "req-123"
    record.status_code = 200
    record.duration_ms = 12.5

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "quantcore.test"
    assert payload["message"] == "request completed"
    assert payload["environment"] == "test"
    assert payload["event"] == "http.request.completed"
    assert payload["request_id"] == "req-123"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5
