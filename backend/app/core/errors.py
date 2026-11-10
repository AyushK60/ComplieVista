"""Shared API error type and the raw-stream request-size cap."""
from __future__ import annotations

from fastapi import Request


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status



def _capped_receive_call(request: Request, cap: int):
    """F05: returns an async receive() bounded by `cap` total body bytes.
    Handles missing/misleading Content-Length and chunked uploads: the cap is
    enforced on the raw ASGI stream BEFORE any parsing, for every body type."""
    total = {"n": 0}
    original_receive = request._receive  # capture BEFORE any reassignment

    async def receive():
        msg = await original_receive()
        if msg.get("type") == "http.request":
            total["n"] += len(msg.get("body", b""))
            if total["n"] > cap:
                raise AppError("PAYLOAD_TOO_LARGE",
                               f"request exceeds {cap} bytes", 413)
        return msg

    return receive
