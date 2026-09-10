"""Run the dependency-free local API: ``python -m knotwise.api.server``."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from knotwise.api.live import parse_live_scenario, solve_live_scenario


class KnotWiseHandler(BaseHTTPRequestHandler):
    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/recommendations":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            scenario = parse_live_scenario(payload)
            result = solve_live_scenario(scenario)
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "INVALID_REQUEST", "message": str(error)})
            return
        self._json(HTTPStatus.UNPROCESSABLE_ENTITY if result["status"] == "INFEASIBLE" else HTTPStatus.OK, result)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), KnotWiseHandler)
    print("KnotWise live API listening on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
