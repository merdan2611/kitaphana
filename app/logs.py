"""Log lines that journald can sort by severity.

journald files everything a service writes to stderr at "info" priority, so `journalctl -u
kitaphana -p err` would find nothing, tracebacks included. It does honour a syslog prefix such
as "<3>" (error) at the start of each line, and it splits a record on newlines, so every line
of a traceback carries the prefix. deploy/logging.yaml installs this formatter for uvicorn's
loggers and the app's alike.

The prefix is added only when systemd connected stderr to the journal (it then sets
JOURNAL_STREAM), so a terminal running bare uvicorn sees plain lines.
"""
from __future__ import annotations

import logging
import os

_PRIORITY = {
    logging.CRITICAL: 2,
    logging.ERROR: 3,
    logging.WARNING: 4,
    logging.INFO: 6,
    logging.DEBUG: 7,
}


class JournalFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not os.environ.get("JOURNAL_STREAM"):
            return text
        prefix = f"<{_PRIORITY.get(record.levelno, 6)}>"
        return "\n".join(prefix + line for line in text.splitlines())
