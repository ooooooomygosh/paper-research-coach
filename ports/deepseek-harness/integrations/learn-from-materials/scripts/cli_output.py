"""Keep CLI diagnostics printable with the caller's existing terminal encoding."""
import sys


def configure_output(streams=None):
    """Escape unsupported characters instead of failing after a successful task.

    Preserve the encoding so redirected output remains compatible with the
    caller. UTF-8 output is unchanged; in-memory streams need no configuration.
    """
    for stream in (sys.stdout, sys.stderr) if streams is None else streams:
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            reconfigure(errors='backslashreplace')
