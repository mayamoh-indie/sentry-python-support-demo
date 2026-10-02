import os

import sentry_sdk


def parse_trace_sample_rate(value: str) -> float:
    message = "SENTRY_TRACES_SAMPLE_RATE must be a finite number between 0 and 1."
    try:
        rate = float(value)
    except ValueError:
        raise ValueError(message) from None
    if not 0 <= rate <= 1:
        raise ValueError(message)
    return rate


def read_nonblank_setting(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be blank.")
    return value


def configure_sentry() -> None:
    environment = read_nonblank_setting("SENTRY_ENVIRONMENT", "candidate-demo")
    release = read_nonblank_setting("SENTRY_RELEASE", "sentry-support-demo@1.0.0")
    sample_rate = parse_trace_sample_rate(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    try:
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN", "").strip(),
            environment=environment,
            release=release,
            traces_sample_rate=sample_rate,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
        )
    except ValueError:
        # SDK parsing errors can include parts of the supplied DSN.
        raise ValueError("Invalid Sentry configuration; check SENTRY_DSN.") from None
