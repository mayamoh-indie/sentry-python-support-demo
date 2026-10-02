import traceback

import pytest
import sentry_sdk

from app.config import configure_sentry, parse_trace_sample_rate


@pytest.mark.parametrize(
    ("value", "expected"), [("0", 0.0), ("0.1", 0.1), ("1", 1.0), (" 0.5 ", 0.5)]
)
def test_sample_rate(value, expected):
    assert parse_trace_sample_rate(value) == expected


@pytest.mark.parametrize(
    "value", ["", " ", "bad", "null", "NaN", "inf", "-inf", "-0.1", "1.1"]
)
def test_invalid_sample_rate(value):
    with pytest.raises(ValueError, match="SENTRY_TRACES_SAMPLE_RATE must be a finite number"):
        parse_trace_sample_rate(value)


@pytest.fixture
def clean_settings(monkeypatch):
    for name in (
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_TRACES_SAMPLE_RATE",
        "SENTRY_SPOTLIGHT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_configuration(clean_settings, monkeypatch):
    options = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: options.update(kwargs))
    configure_sentry()
    assert options["dsn"] == ""
    assert options["environment"] == "candidate-demo"
    assert options["release"] == "sentry-support-demo@1.0.0"
    assert options["traces_sample_rate"] == 0.1


def test_configuration_overrides(clean_settings, monkeypatch):
    monkeypatch.setenv("SENTRY_ENVIRONMENT", " local-test ")
    monkeypatch.setenv("SENTRY_RELEASE", "demo@2.0.0")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0")
    options = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: options.update(kwargs))
    configure_sentry()
    assert options["environment"] == "local-test"
    assert options["release"] == "demo@2.0.0"
    assert options["traces_sample_rate"] == 0.0


@pytest.mark.parametrize("name", ["SENTRY_ENVIRONMENT", "SENTRY_RELEASE"])
@pytest.mark.parametrize("value", ["", " "])
def test_blank_metadata_fails_before_sdk_init(clean_settings, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: pytest.fail("SDK initialized"))
    with pytest.raises(ValueError, match=f"{name} must not be blank"):
        configure_sentry()


@pytest.mark.parametrize(
    "value",
    [
        "not-a-dsn",
        "https://key@example.invalid/private-marker",
        "https://key@example.invalid:bad-port/1",
    ],
)
def test_invalid_dsn_error_omits_value(clean_settings, monkeypatch, value):
    monkeypatch.setenv("SENTRY_DSN", value)
    with pytest.raises(
        ValueError, match="Invalid Sentry configuration; check SENTRY_DSN"
    ) as error:
        configure_sentry()
    rendered = "".join(traceback.format_exception(error.value))
    assert value not in rendered
    assert "private-marker" not in rendered
    assert "bad-port" not in rendered
