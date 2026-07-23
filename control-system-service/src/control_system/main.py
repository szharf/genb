from fastapi import FastAPI

from .bootstrap import create_local_app


def create_application() -> FastAPI:
    return create_local_app()
