from __future__ import annotations

import argparse
import sys
import threading
import time
import traceback

from .jobs import (
    experiment_id_from_config,
    progress_from_output,
    read_job_config,
    update_job_status,
)


def monitor_progress(job_id: str, config: dict, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        update_job_status(job_id, status="running", **progress_from_output(config))
        stop_event.wait(5)


def run_job(job_id: str) -> int:
    config = read_job_config(job_id)
    stop_event = threading.Event()
    monitor = threading.Thread(target=monitor_progress, args=(job_id, config, stop_event), daemon=True)
    try:
        update_job_status(job_id, status="running", error=None, **progress_from_output(config))
        monitor.start()
        from main import run_simulation

        run_simulation(config)
        stop_event.set()
        monitor.join(timeout=2)
        update_job_status(
            job_id,
            status="completed",
            output_experiment_id=experiment_id_from_config(config),
            **progress_from_output(config),
        )
        return 0
    except Exception:
        stop_event.set()
        monitor.join(timeout=2)
        error = traceback.format_exc()
        print(error, file=sys.stderr)
        update_job_status(job_id, status="failed", error=error, **progress_from_output(config))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    return run_job(args.job_id)


if __name__ == "__main__":
    raise SystemExit(main())
