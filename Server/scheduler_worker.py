"""Dedicated FundInv scheduler process.

Run exactly one instance with:
    venv/bin/python scheduler_worker.py
"""

import logging
import signal
import threading

from jobs.scheduler import start_scheduler, stop_scheduler


logging.basicConfig(level=logging.INFO)
shutdown = threading.Event()


def _stop(*_args) -> None:
    shutdown.set()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    start_scheduler()
    try:
        shutdown.wait()
    finally:
        stop_scheduler()
