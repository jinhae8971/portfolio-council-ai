"""구조화 로깅 설정"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """JSON 구조화 로깅 설정."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
