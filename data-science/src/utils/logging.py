import logging
import sys


def setup_logging(
    name: str = "elyssa",
    level: int = logging.INFO,
    log_file: str = "pipeline.log",
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
