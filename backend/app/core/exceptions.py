"""统一异常与响应封装：所有接口都返回 {code, message, data, request_id}。"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("mathrag")

HTTP_BY_CODE = {
    1001: 400,
    1002: 401,
    1003: 403,
    1004: 404,
    1005: 409,
    2001: 413,
    2002: 415,
    2003: 422,
    3001: 429,
    4001: 502,
    4002: 504,
    5000: 500,
}


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class AppError(Exception):
    def __init__(self, code: int, message: str, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status or HTTP_BY_CODE.get(code, 400)


def ok(data=None) -> dict:
    return {"code": 0, "message": "ok", "data": data, "request_id": new_request_id()}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
                "request_id": new_request_id(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "body"
        return JSONResponse(
            status_code=400,
            content={
                "code": 1001,
                "message": f"参数校验失败：{field} {first.get('msg', '')}".strip(),
                "data": None,
                "request_id": new_request_id(),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "code": 5000,
                "message": "服务内部错误，请稍后重试",
                "data": None,
                "request_id": new_request_id(),
            },
        )
