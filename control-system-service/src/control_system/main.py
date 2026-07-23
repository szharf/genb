import os

from fastapi import FastAPI

from .bootstrap import create_genb_connected_app, create_local_app


def create_application() -> FastAPI:
    identity_adapter = os.getenv("CONTROL_SYSTEM_IDENTITY_ADAPTER", "local")
    if identity_adapter == "local":
        return create_local_app()
    if identity_adapter == "genb":
        return create_genb_connected_app()
    raise RuntimeError("CONTROL_SYSTEM_IDENTITY_ADAPTER must be local or genb")
