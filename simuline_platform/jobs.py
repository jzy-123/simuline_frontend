from __future__ import annotations

import json
import math
import os
import signal
import shutil
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SimuLine.Simulation.Config.config import BASE_CONFIG

from .services import (
    EXPERIMENT_TEMPLATES,
    PROJECT_ROOT,
    encode_experiment_id,
    read_output_csv,
)


WORKSPACE_ROOT = PROJECT_ROOT / "workspace" / "platform_jobs"
ACTIVE_JOB_STATUSES = {"starting", "running"}

DEMO_DEFAULTS = {
    "experiment": "Platform",
    "description": "platform-demo",
    "model": "BPR",
    "num_round": 2,
    "num_user": 500,
    "num_creator": 100,
    "epochs": 1,
    "eval_step": 1,
    "stopping_step": 1,
    "train_batch_size": 256,
    "eval_batch_size": 512,
    "positive_inter_type": "click",
    "recommendation_list_length": 100,
    "num_click": 10,
    "n_round": 2,
}

ALLOWED_OVERRIDE_KEYS = {
    "model",
    "num_round",
    "num_user",
    "num_creator",
    "num_create",
    "n_round",
    "epochs",
    "learning_rate",
    "train_batch_size",
    "eval_batch_size",
    "eval_step",
    "stopping_step",
    "recommendation_list_length",
    "num_from_match",
    "num_from_cold_start",
    "num_from_hot",
    "num_from_promote",
    "cold_start_inter_type",
    "hot_inter_type",
    "promote_type",
    "promote_round",
    "num_click",
    "uam_delta",
    "cam_delta",
    "creator_target_inter_type",
}

INT_KEYS = {
    "num_round",
    "num_user",
    "num_creator",
    "num_create",
    "n_round",
    "epochs",
    "train_batch_size",
    "eval_batch_size",
    "eval_step",
    "stopping_step",
    "recommendation_list_length",
    "num_from_match",
    "num_from_cold_start",
    "num_from_hot",
    "num_from_promote",
    "promote_round",
    "num_click",
}

FLOAT_KEYS = {
    "learning_rate",
    "uam_delta",
    "cam_delta",
}


class JobDeleteError(RuntimeError):
    """Raised when a job cannot be deleted safely."""


class JobTerminateError(RuntimeError):
    """Raised when a job cannot be terminated safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_job_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def job_dir(job_id: str) -> Path:
    return WORKSPACE_ROOT / job_id


def config_path(job_id: str) -> Path:
    return job_dir(job_id) / "config.json"


def metadata_path(job_id: str) -> Path:
    return job_dir(job_id) / "metadata.json"


def status_path(job_id: str) -> Path:
    return job_dir(job_id) / "status.json"


def log_path(job_id: str) -> Path:
    return job_dir(job_id) / "run.log"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_job_config(job_id: str) -> dict[str, Any]:
    return read_json(config_path(job_id))


def read_job_metadata(job_id: str) -> dict[str, Any]:
    return read_json(metadata_path(job_id))


def read_job_status(job_id: str) -> dict[str, Any]:
    path = status_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"Job {job_id} not found")
    return enrich_job_status(read_json(path))


def enrich_job_status(status: dict[str, Any]) -> dict[str, Any]:
    job_id = status.get("job_id")
    if not job_id:
        return status
    try:
        metadata = read_job_metadata(str(job_id))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    if metadata:
        status.setdefault("name", metadata.get("name"))
        status.setdefault("display_name", metadata.get("name"))
        status.setdefault("template_id", metadata.get("template_id"))
        status.setdefault("output_experiment_id", metadata.get("output_experiment_id"))
    if not status.get("display_name"):
        status["display_name"] = status.get("name") or str(job_id)
    return status


def update_job_status(job_id: str, **updates: Any) -> dict[str, Any]:
    try:
        status = read_job_status(job_id)
    except FileNotFoundError:
        status = {"job_id": job_id, "created_at": utc_now()}
    status.update(updates)
    status["updated_at"] = utc_now()
    write_json(status_path(job_id), status)
    return status


def list_job_statuses() -> list[dict[str, Any]]:
    if not WORKSPACE_ROOT.exists():
        return []
    statuses = []
    for path in WORKSPACE_ROOT.glob("*/status.json"):
        try:
            statuses.append(enrich_job_status(read_json(path)))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(statuses, key=lambda item: item.get("created_at", ""), reverse=True)


def template_by_id(template_id: str) -> dict[str, Any]:
    for template in EXPERIMENT_TEMPLATES:
        if template["id"] == template_id:
            return template
    raise ValueError(f"Unknown template_id: {template_id}")


def coerce_override(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        return int(value)
    if key in FLOAT_KEYS:
        return float(value)
    return value


def apply_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if key not in ALLOWED_OVERRIDE_KEYS:
            raise ValueError(f"Unsupported override key: {key}")
        if value is None or value == "":
            continue
        config[key] = coerce_override(key, value)


def validate_config(config: dict[str, Any]) -> None:
    recommendation_total = (
        config["num_from_match"]
        + config["num_from_cold_start"]
        + config["num_from_hot"]
        + config["num_from_promote"]
    )
    if recommendation_total != config["recommendation_list_length"]:
        raise ValueError("Recommendation source counts must equal recommendation_list_length")
    if config["num_click"] > config["recommendation_list_length"]:
        raise ValueError("num_click cannot exceed recommendation_list_length")
    initial_articles = config["num_creator"] * config["num_create"]
    if config["recommendation_list_length"] > initial_articles:
        raise ValueError("recommendation_list_length cannot exceed initial article count")
    if config["num_from_cold_start"] > initial_articles:
        raise ValueError("num_from_cold_start cannot exceed articles created in one round")
    if not 1 <= config["num_user"] <= 10000:
        raise ValueError("num_user must be between 1 and 10000")
    if not 1 <= config["num_creator"] <= 1000:
        raise ValueError("num_creator must be between 1 and 1000")


def build_platform_config(
    *,
    job_id: str,
    template_id: str,
    name: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = template_by_id(template_id)
    config = deepcopy(BASE_CONFIG)
    config.update(DEMO_DEFAULTS)
    config.update(template["config_patch"])
    apply_overrides(config, overrides or {})

    config["experiment"] = "Platform"
    config["var"] = template_id
    config["run"] = f"job-{job_id}"
    config["description"] = f"platform:{name}"
    config["best_stable_quality"] = math.log(config["num_create"] * config["num_user"] + 1)
    validate_config(config)
    return config


def experiment_id_from_config(config: dict[str, Any]) -> str:
    return encode_experiment_id(config["experiment"], config["var"], config["run"])


def output_csv_path(config: dict[str, Any]) -> Path:
    return (
        PROJECT_ROOT
        / "Out"
        / "Result"
        / config["experiment"]
        / config["var"]
        / f"{config['run']}_output.csv"
    )


def result_metadata_path(config: dict[str, Any]) -> Path:
    return output_csv_path(config).parent / f"{config['run']}_platform_metadata.json"


def progress_from_output(config: dict[str, Any]) -> dict[str, Any]:
    output_path = output_csv_path(config)
    current_round = 0
    if output_path.exists():
        try:
            parsed = read_output_csv(output_path)
            current_round = max(0, len(parsed["rounds"]) - 1)
        except (OSError, IndexError, ValueError):
            current_round = 0
    num_round = int(config["num_round"])
    current_round = min(current_round, num_round)
    return {
        "current_round": current_round,
        "num_round": num_round,
        "progress": 1.0 if num_round == 0 else current_round / num_round,
    }


def create_experiment_job(
    *,
    template_id: str,
    name: str,
    overrides: dict[str, Any] | None = None,
    auto_start: bool = True,
) -> dict[str, Any]:
    job_id = new_job_id()
    job_dir(job_id).mkdir(parents=True, exist_ok=False)
    config = build_platform_config(
        job_id=job_id,
        template_id=template_id,
        name=name,
        overrides=overrides,
    )
    metadata = {
        "job_id": job_id,
        "name": name,
        "template_id": template_id,
        "created_at": utc_now(),
        "output_experiment_id": experiment_id_from_config(config),
    }
    write_json(config_path(job_id), config)
    write_json(metadata_path(job_id), metadata)
    write_json(result_metadata_path(config), metadata)
    status = update_job_status(
        job_id,
        status="pending",
        pid=None,
        error=None,
        name=metadata["name"],
        display_name=metadata["name"],
        template_id=template_id,
        log_path=str(log_path(job_id)),
        output_experiment_id=metadata["output_experiment_id"],
        **progress_from_output(config),
    )
    if auto_start:
        status = start_job(job_id)
    return status


def start_job(job_id: str) -> dict[str, Any]:
    read_job_config(job_id)
    current_status = read_job_status(job_id)
    if current_status.get("status") in {"starting", "running"}:
        return current_status

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(PROJECT_ROOT)
        if not existing_pythonpath
        else str(PROJECT_ROOT) + os.pathsep + existing_pythonpath
    )
    log_path(job_id).parent.mkdir(parents=True, exist_ok=True)
    with log_path(job_id).open("ab") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "simuline_platform.worker", "--job-id", job_id],
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
    return update_job_status(job_id, status="starting", pid=process.pid, error=None)


def tail_job_log(job_id: str, max_bytes: int = 20000) -> str:
    path = log_path(job_id)
    if not path.exists():
        return ""
    with path.open("rb") as file:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(max(0, size - max_bytes), os.SEEK_SET)
        return file.read().decode("utf-8", errors="replace")


def terminate_job(job_id: str) -> dict[str, Any]:
    status = read_job_status(job_id)
    if status.get("status") not in ACTIVE_JOB_STATUSES:
        return status

    pid = status.get("pid")
    if pid:
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    message = result.stderr.strip() or result.stdout.strip()
                    check = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if str(pid) in check.stdout:
                        raise JobTerminateError(message or f"Failed to terminate process {pid}")
            else:
                os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired as exc:
            raise JobTerminateError(f"Timed out while terminating process {pid}") from exc
        except OSError as exc:
            raise JobTerminateError(str(exc)) from exc

    try:
        progress = progress_from_output(read_job_config(job_id))
    except Exception:
        progress = {}
    return update_job_status(
        job_id,
        status="terminated",
        pid=None,
        error="Terminated by user",
        **progress,
    )


def delete_job(job_id: str) -> dict[str, Any]:
    status = read_job_status(job_id)
    if status.get("status") in ACTIVE_JOB_STATUSES:
        raise JobDeleteError("Cannot delete a job while it is starting or running")
    root = WORKSPACE_ROOT.resolve()
    target = job_dir(job_id).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Job {job_id} not found")
    if root not in target.parents:
        raise JobDeleteError(f"Refusing to delete unsafe path: {target}")
    shutil.rmtree(target)
    return {"job_id": job_id, "deleted": True}


def delete_jobs(job_ids: list[str]) -> dict[str, Any]:
    deleted = []
    errors = []
    for job_id in job_ids:
        try:
            deleted.append(delete_job(job_id))
        except Exception as exc:
            errors.append({"job_id": job_id, "error": str(exc)})
    return {"deleted": deleted, "errors": errors}
