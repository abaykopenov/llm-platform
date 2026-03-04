"""
Auth Middleware
Optional API key authentication via Authorization: Bearer <key> header.
"""

from typing import List, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_keys: List[str]):
        super().__init__(app)
        self.api_keys = set(api_keys)

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip auth for health endpoints and docs
        skip_paths = {"/health", "/status", "/docs", "/openapi.json", "/"}
        if request.url.path in skip_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token in self.api_keys:
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Invalid or missing API key. Use Authorization: Bearer <key>",
                    "type": "authentication_error",
                }
            },
        )
