import sys

def write_error(error):
    """stderr.write wrapper that forces flush on each write"""
    sys.stderr.write(error + '\n')
    sys.stderr.flush()
    