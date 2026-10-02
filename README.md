# Sentry Python Support Demo

A small FastAPI service for exploring Sentry error capture and SDK troubleshooting.
Order `999` simulates a malformed inventory response; other integer IDs return a
synthetic order. There is no database or external inventory service.

The demo uses automatic FastAPI instrumentation, an unhandled exception with
application frames, environment and release metadata, request-scoped order context,
and sampled HTTP traces.

```text
GET /api/orders/999
  -> get_order()
  -> process_order()
  -> validate_inventory()
  -> OrderProcessingError
  -> Sentry SDK -> Sentry issue
```

## Run locally

Requires Python 3.12 or newer. From the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS/Linux, activate with `source .venv/bin/activate` and copy the config with
`cp .env.example .env`. If PowerShell blocks activation, use
`.\.venv\Scripts\python.exe` in place of `python`; activation is optional.

1. Sign in to [Sentry](https://sentry.io/signup/) and create a Python/FastAPI project.
2. In project settings, open **Client Keys (DSN)** and copy its DSN.
3. Edit the ignored `.env` file locally and put the value after `SENTRY_DSN=`.
   An API auth token is not needed. Leave the other example values in place.
4. Start the server:

```powershell
python -m uvicorn app.main:app --reload
```

The app loads `.env` from the repository root; existing shell variables take
precedence. Restart after changing configuration. A blank DSN keeps the app usable
locally but sends nothing to Sentry.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SENTRY_DSN` | empty | Destination project; supplied locally |
| `SENTRY_ENVIRONMENT` | `candidate-demo` | Separate demo events from other environments |
| `SENTRY_RELEASE` | `sentry-support-demo@1.0.0` | Identify the application version |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Sample approximately 10% of new HTTP traces |

Invalid configuration fails at startup. The sample rate must be a finite number
from `0` to `1`; blank values, `NaN`, and infinity are rejected. Environment and
release use defaults only when unset; explicitly blank values are rejected.
Surrounding whitespace is stripped from metadata and the DSN. A malformed DSN
produces an error naming the setting without repeating its value.

Trace sampling is independent of error sampling: errors keep the SDK's default
100% sample rate. A single request may have an error event without a stored trace.
Temporarily set `SENTRY_TRACES_SAMPLE_RATE=1.0` and restart to inspect every local
demo request; return to `0.1` afterward. This is one service, so the demo makes no
claim to show distributed tracing.

## Reproduce and inspect

In another terminal, use a browser or:

```powershell
curl.exe -i http://127.0.0.1:8000/
curl.exe -i http://127.0.0.1:8000/health
curl.exe -i http://127.0.0.1:8000/api/orders/123
curl.exe -i http://127.0.0.1:8000/api/orders/999
```

On macOS/Linux, use `curl`. The first three requests return **200**. Order `999`
returns **500 Internal Server Error** and logs a traceback in the server terminal.
That failure is intentional and does not stop the server. `/health` checks only
that the application responds; it does not prove Sentry delivery.

IDs are synthetic integer labels, including zero and negative numbers. Non-integer
IDs such as `abc` or `1.5` return **422**, without an application error event.
An omitted path segment does not match this route and returns **404**. There is no
request body to parse or batch to partially process.

In Sentry, select the destination project and recent time range, then open the new
issue. Repeating the same failure should add events to the same issue rather than
create a new issue per request. Verify:

| Field | Expected value |
| --- | --- |
| Exception | `OrderProcessingError` (unhandled) |
| Message | `Unable to process order because the inventory service returned an invalid state.` |
| Application frames | `get_order` -> `process_order` -> `validate_inventory` |
| Request | `GET`, URL ending in `/api/orders/999` |
| Environment | `candidate-demo` |
| Release | `sentry-support-demo@1.0.0` |
| Tag | `component=order-api` |
| Order context | `id=999`, `synthetic=true` |
| Sampled transaction | `/api/orders/{order_id}`; actual IDs stay out of the transaction name |

To diagnose this example, start at `validate_inventory`: the simulated response
state is `unknown`. Compare order `123`, which uses `available`. In a real support
case, verify the upstream response contract before deciding whether an unfamiliar
state is valid. Catching everything and returning 200 would hide the failure.

## If the event is missing

1. Confirm order `999` returns 500 and the terminal shows `OrderProcessingError`.
   A 200 suggests the wrong route/process; a 422 means the ID was not an integer.
2. Check that `.env` contains a nonempty DSN for the selected project. An existing
   shell `SENTRY_DSN` overrides the file, even if it is empty. Do not print the DSN.
3. Restart the server and trigger the error again. Leave it running while the SDK
   sends from its background queue.
4. Clear environment/search filters and check the recent time range in Sentry.
   Look for another event on the existing issue as well as new issues.
5. Check outbound connectivity/proxy settings and project quotas or inbound
   filters. For local diagnosis, `SENTRY_DEBUG=true` enables SDK diagnostics;
   restart, inspect them privately, then disable it before sharing logs.

Changing trace sampling will not fix a missing error event. The app relies on the
framework integration; it neither catches this exception nor calls
`capture_exception` manually, which avoids reporting the same failure twice.

## Tests

```powershell
python -m pytest -q
```

Tests replace the SDK transport with an in-memory collector, override Sentry
environment variables, and disable `.env` loading. No Sentry account or network
delivery is required. They check the HTTP responses, unhandled failure, captured
stack and metadata, route-based tracing, invalid input and configuration, and
isolation of order context from the next health request. Local capture does not
prove ingestion into a live project; use the manual steps above to verify that
separately.

## Data and scope

All order data is synthetic. DSNs and credentials are supplied through environment
variables (optionally loaded from the ignored `.env`) and are not committed.
Default PII collection is off, stack-frame local variables are disabled, and
request bodies are not collected. Request URLs and other debugging metadata can
still be included: use only synthetic requests and do not put secrets in URLs.

The SDK [automatically enables FastAPI integration](https://docs.sentry.io/platforms/python/integrations/fastapi/).
See [SDK options](https://docs.sentry.io/platforms/python/configuration/options/)
for the sampling and data collection settings used here.

MIT licensed. Run locally; the intentional failure endpoint is a diagnostic demo.
