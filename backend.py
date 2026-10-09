import uvicorn

from kara.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("kara.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
