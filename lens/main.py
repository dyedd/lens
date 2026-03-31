import uvicorn

from .core.config import settings
from .gateway.service import app


def run() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
