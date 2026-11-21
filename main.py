"""网页/API 统一入口：uvicorn main:app --host 127.0.0.1 --port 8000。"""
from app.api import app

__all__ = ["app"]
