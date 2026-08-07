import logging

import uvicorn

from .app import create_app


class _SuccessfulHealthCheckFilter(logging.Filter):
    """Hide successful health probes while preserving failed requests."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        path = str(args[2]).split("?", 1)[0]
        try:
            status_code = int(args[4])
        except (TypeError, ValueError):
            return True
        return path != "/health" or status_code >= 400


logging.getLogger("uvicorn.access").addFilter(_SuccessfulHealthCheckFilter())

app = create_app()


def run() -> None:
    uvicorn.run("modelark_proxy.main:app", host="0.0.0.0", port=8080)
