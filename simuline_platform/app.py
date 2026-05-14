from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    COOKIE_NAME,
    COOKIE_SECURE,
    SESSION_SECONDS,
    authenticate_user,
    create_session_token,
    current_user_from_request,
)
from .jobs import (
    JobDeleteError,
    JobTerminateError,
    create_experiment_job,
    delete_job,
    delete_jobs,
    list_job_statuses,
    read_job_status,
    start_job,
    tail_job_log,
    terminate_job,
)
from .services import (
    METRIC_GROUPS,
    METRIC_LABELS,
    EXPERIMENT_TEMPLATES,
    PROJECT_ROOT,
    RESULT_ROOT,
    STATIC_ROOT,
    ExperimentDeleteError,
    ExperimentNotFoundError,
    delete_experiment_result,
    delete_experiment_results,
    describe_output,
    experiment_detail_payload,
    experiment_report_payload,
    list_experiment_outputs,
)


class ExperimentCreateRequest(BaseModel):
    template_id: str = "baseline"
    name: str = Field(..., min_length=1, max_length=80)
    auto_start: bool = True
    num_round: int = Field(default=2, ge=1, le=20)
    num_user: int = Field(default=500, ge=1, le=10000)
    num_creator: int = Field(default=100, ge=1, le=1000)
    epochs: int = Field(default=1, ge=1, le=100)
    overrides: dict[str, Any] = Field(default_factory=dict)


class BatchDeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


app = FastAPI(
    title="SimuLine Simulation Platform",
    description="A lightweight experiment and strategy evaluation wrapper for SimuLine.",
    version="0.1.0",
)


if STATIC_ROOT.exists():
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/health",
}


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if is_public_path(path) or current_user_from_request(request):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return RedirectResponse(url=f"/login?next={quote(path)}", status_code=303)


def not_found(exc: ExperimentNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@app.get("/login")
def login_page() -> FileResponse:
    login_path = STATIC_ROOT / "login.html"
    if not login_path.exists():
        raise HTTPException(status_code=404, detail="Login page not found")
    return FileResponse(login_path)


@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response) -> dict[str, Any]:
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(user["username"]),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return {"user": user}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/me")
def current_user(request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    return {"authenticated": bool(user), "user": user}


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_ROOT / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Static dashboard not found")
    return FileResponse(index_path)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "result_root_exists": RESULT_ROOT.exists(),
    }


@app.get("/api/metric-groups")
def metric_groups() -> dict[str, Any]:
    return {"labels": METRIC_LABELS, "groups": METRIC_GROUPS}


@app.get("/api/templates")
def templates() -> dict[str, Any]:
    return {"items": EXPERIMENT_TEMPLATES}


@app.get("/api/experiments")
def experiments() -> dict[str, Any]:
    return {"items": [describe_output(path) for path in list_experiment_outputs()]}


@app.post("/api/experiments")
def create_experiment(request: ExperimentCreateRequest) -> dict[str, Any]:
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Experiment name is required")
    overrides = dict(request.overrides)
    overrides.update(
        {
            "num_round": request.num_round,
            "num_user": request.num_user,
            "num_creator": request.num_creator,
            "epochs": request.epochs,
        }
    )
    try:
        job = create_experiment_job(
            template_id=request.template_id,
            name=name,
            overrides=overrides,
            auto_start=request.auto_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job}


@app.post("/api/experiments/batch-delete")
def delete_experiments(request: BatchDeleteRequest) -> dict[str, Any]:
    if not request.ids:
        raise HTTPException(status_code=400, detail="No experiments selected")
    return delete_experiment_results(request.ids)


@app.get("/api/experiments/{experiment_id}")
def experiment_detail(experiment_id: str) -> dict[str, Any]:
    try:
        return experiment_detail_payload(experiment_id)
    except ExperimentNotFoundError as exc:
        raise not_found(exc) from exc


@app.get("/api/experiments/{experiment_id}/report")
def experiment_report(experiment_id: str) -> dict[str, Any]:
    try:
        return experiment_report_payload(experiment_id)
    except ExperimentNotFoundError as exc:
        raise not_found(exc) from exc


@app.delete("/api/experiments/{experiment_id}")
def delete_experiment(experiment_id: str) -> dict[str, Any]:
    try:
        return delete_experiment_result(experiment_id)
    except ExperimentNotFoundError as exc:
        raise not_found(exc) from exc
    except ExperimentDeleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/jobs")
def jobs() -> dict[str, Any]:
    return {"items": list_job_statuses()}


@app.post("/api/jobs/batch-delete")
def jobs_batch_delete(request: BatchDeleteRequest) -> dict[str, Any]:
    if not request.ids:
        raise HTTPException(status_code=400, detail="No jobs selected")
    return delete_jobs(request.ids)


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str) -> dict[str, Any]:
    try:
        return {"job": read_job_status(job_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/start")
def job_start(job_id: str) -> dict[str, Any]:
    try:
        return {"job": start_job(job_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/terminate")
def job_terminate(job_id: str) -> dict[str, Any]:
    try:
        return {"job": terminate_job(job_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JobTerminateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/log")
def job_log(job_id: str, max_bytes: int = 20000) -> dict[str, Any]:
    try:
        read_job_status(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"job_id": job_id, "log": tail_job_log(job_id, max_bytes=max_bytes)}


@app.delete("/api/jobs/{job_id}")
def job_delete(job_id: str) -> dict[str, Any]:
    try:
        return delete_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JobDeleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
