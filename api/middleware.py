"""API logging middleware for detailed request/response tracking.

This module provides middleware to automatically log all API requests and responses,
with special handling for memory-related endpoints to capture fact splits and search results.
"""

import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from utils.logger import get_debug_logger


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses."""

    def __init__(self, app: ASGIApp):
        """Initialize the middleware.

        Args:
            app: The ASGI application
        """
        super().__init__(app)
        self.debug_logger = get_debug_logger()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process each request/response pair.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response from the route handler
        """
        start_time = time.time()
        endpoint = str(request.url.path)
        method = request.method

        # Extract uid from query params or request body for relevant endpoints
        uid = request.query_params.get("uid")
        request_data = None

        # For POST requests, try to read the body for logging
        if method == "POST":
            try:
                body = await request.body()
                if body:
                    request_data = json.loads(body.decode())
                    uid = request_data.get("uid", uid)
            except Exception:
                pass  # Body not available or not JSON

        # Log the request
        self.debug_logger.log_api_request(
            endpoint=endpoint,
            method=method,
            uid=uid,
            request_data=request_data
        )

        # Process the request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log successful response
            self.debug_logger.log_api_response(
                endpoint=endpoint,
                status="success",
                duration_ms=duration_ms
            )

            # Add custom header with duration
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log error response
            self.debug_logger.log_api_response(
                endpoint=endpoint,
                status="error",
                duration_ms=duration_ms,
                error=str(e)
            )
            raise
