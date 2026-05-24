import logging
import os
import sys


def configure() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    # Quiet noisy libs.
    for noisy in ("httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)
