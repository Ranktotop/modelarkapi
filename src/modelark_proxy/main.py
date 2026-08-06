import uvicorn

from .app import create_app

app = create_app()


def run() -> None:
    uvicorn.run("modelark_proxy.main:app", host="0.0.0.0", port=8080)
