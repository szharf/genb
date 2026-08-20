from __future__ import annotations

import os
import threading

from .factory import build_gateway


def main() -> None:
    import uvicorn

    app = build_gateway(os.environ)
    stopping = threading.Event()

    def flush_audits() -> None:
        while not stopping.wait(1.0):
            app.audit_buffer.flush(batch_size=100)

    worker = threading.Thread(target=flush_audits, name="genb-audit-flush", daemon=True)
    worker.start()
    try:
        uvicorn.run(
            app, host=os.environ.get("GENB_GATEWAY_HOST", "0.0.0.0"),
            port=int(os.environ.get("GENB_GATEWAY_PORT", "9080")),
            workers=1, proxy_headers=False, server_header=False,
        )
    finally:
        stopping.set()
        worker.join(timeout=2)
        app.audit_buffer.flush(batch_size=100)


if __name__ == "__main__":
    main()
