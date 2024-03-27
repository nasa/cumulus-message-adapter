import sys


def write_error(error: str) -> None:
    """stderr.write wrapper that forces flush on each write"""
    sys.stderr.write(error + '\n')
    sys.stderr.flush()
