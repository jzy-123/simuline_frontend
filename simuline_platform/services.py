from __future__ import annotations

import base64
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = PROJECT_ROOT / "Out" / "Result"
STATIC_ROOT = Path(__file__).resolve().parent / "static"
PLATFORM_JOB_ROOT = PROJECT_ROOT / "workspace" / "platform_jobs"


METRIC_LABELS = {
    "Metric-Inter-User-Like-Mean": "用户点赞均值",
    "Metric-Inter-User-Like-Gini": "用户点赞集中度",
    "Metric-Inter-Creator-Exposure-Gini": "创作者曝光集中度",
    "Metric-Inter-Creator-Click-Gini": "创作者点击集中度",
    "Metric-Inter-Creator-Like-Mean": "创作者点赞均值",
    "Metric-Inter-Creator-Like-Gini": "创作者点赞集中度",
    "Metric-Inter-Article-Exposure-Gini": "内容曝光集中度",
    "Metric-Inter-Article-Click-Gini": "内容点击集中度",
    "Metric-Inter-Article-Like-Mean": "内容点赞均值",
    "Metric-Inter-Article-Like-Gini": "内容点赞集中度",
    "Metric-Quality-Create-Weighted": "内容平均质量",
    "Metric-Quality-Exposure-Weighted": "曝光加权质量",
    "Metric-Quality-Click-Weighted": "点击加权质量",
    "Metric-Quality-Like-Weighted": "点赞加权质量",
    "Metric-Homogenization-User-Exposure": "曝光同质化",
    "Metric-Homogenization-User-Click": "点击同质化",
    "Metric-Homogenization-User-Like": "点赞同质化",
    "Metric-RecSys-MRR@5": "推荐 MRR@5",
    "Latent-User_Article_Similarity-Exposure": "曝光匹配度",
    "Latent-User_Article_Similarity-Click": "点击匹配度",
    "Latent-User_Article_Similarity-Like": "点赞匹配度",
    "Latent-User_Interest_Shifting": "用户兴趣漂移",
}

METRIC_GROUPS = {
    "overview": [
        "Metric-Inter-User-Like-Mean",
        "Metric-Inter-Creator-Exposure-Gini",
        "Metric-Quality-Exposure-Weighted",
        "Metric-RecSys-MRR@5",
        "Latent-User_Interest_Shifting",
    ],
    "user": [
        "Metric-Inter-User-Like-Mean",
        "Metric-Inter-User-Like-Gini",
        "Metric-Homogenization-User-Exposure",
        "Metric-Homogenization-User-Click",
        "Metric-Homogenization-User-Like",
        "Latent-User_Interest_Shifting",
    ],
    "creator": [
        "Metric-Inter-Creator-Exposure-Gini",
        "Metric-Inter-Creator-Click-Gini",
        "Metric-Inter-Creator-Like-Mean",
        "Metric-Inter-Creator-Like-Gini",
    ],
    "content": [
        "Metric-Inter-Article-Exposure-Gini",
        "Metric-Inter-Article-Click-Gini",
        "Metric-Inter-Article-Like-Mean",
        "Metric-Inter-Article-Like-Gini",
        "Metric-Quality-Create-Weighted",
        "Metric-Quality-Exposure-Weighted",
        "Metric-Quality-Click-Weighted",
        "Metric-Quality-Like-Weighted",
    ],
    "recsys": [
        "Metric-RecSys-MRR@5",
        "Metric-RecSys-User-Registed",
        "Metric-RecSys-Article-Registed",
        "Latent-User_Article_Similarity-Exposure",
        "Latent-User_Article_Similarity-Click",
        "Latent-User_Article_Similarity-Like",
    ],
}

EXPERIMENT_TEMPLATES = [
    {
        "id": "baseline",
        "name": "基础个性化推荐",
        "description": "以个性化匹配为主，保留少量新内容扶持，用作策略对照组。",
        "business_goal": "观察不做额外干预时，生态指标自然演化趋势。",
        "config_patch": {
            "num_from_match": 80,
            "num_from_cold_start": 20,
            "num_from_hot": 0,
            "num_from_promote": 0,
            "promote_type": "author",
        },
    },
    {
        "id": "cold-start-boost",
        "name": "新内容扶持",
        "description": "提高冷启动内容比例，评估新品/新内容扶持对生态的影响。",
        "business_goal": "判断新内容扶持是否提升内容多样性，同时控制点击和质量损失。",
        "config_patch": {
            "num_from_match": 60,
            "num_from_cold_start": 40,
            "num_from_hot": 0,
            "num_from_promote": 0,
            "promote_type": "author",
        },
    },
    {
        "id": "hot-content",
        "name": "热门内容倾斜",
        "description": "增加热门内容推荐比例，评估短期互动提升与生态集中风险。",
        "business_goal": "观察热门倾斜是否带来更高点击，以及是否加剧流量集中。",
        "config_patch": {
            "num_from_match": 70,
            "num_from_cold_start": 20,
            "num_from_hot": 10,
            "num_from_promote": 0,
            "promote_type": "author",
        },
    },
    {
        "id": "author-promotion",
        "name": "作者/供给方推广",
        "description": "保留一定推广位给指定供给方，评估推广对生态公平和长期反馈的影响。",
        "business_goal": "判断推广策略是否挤压自然流量，并观察创作者收益分布变化。",
        "config_patch": {
            "num_from_match": 70,
            "num_from_cold_start": 20,
            "num_from_hot": 0,
            "num_from_promote": 10,
            "promote_type": "author",
        },
    },
]


class ExperimentNotFoundError(FileNotFoundError):
    """Raised when an encoded experiment id cannot be resolved."""


class ExperimentDeleteError(RuntimeError):
    """Raised when an experiment result cannot be deleted safely."""


def encode_experiment_id(experiment: str, variant: str, run: str) -> str:
    payload = json.dumps([experiment, variant, run], ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_experiment_id(experiment_id: str) -> tuple[str, str, str]:
    padding = "=" * (-len(experiment_id) % 4)
    try:
        payload = base64.urlsafe_b64decode(experiment_id + padding)
        decoded = json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ExperimentNotFoundError("Experiment not found") from exc
    if not isinstance(decoded, list) or len(decoded) != 3:
        raise ExperimentNotFoundError("Experiment not found")
    return str(decoded[0]), str(decoded[1]), str(decoded[2])


def experiment_output_path(experiment_id: str) -> Path:
    experiment, variant, run = decode_experiment_id(experiment_id)
    output_path = RESULT_ROOT / experiment / variant / f"{run}_output.csv"
    if not output_path.exists():
        raise ExperimentNotFoundError("Experiment output not found")
    return output_path


def job_metadata_by_experiment_id() -> dict[str, dict[str, Any]]:
    if not PLATFORM_JOB_ROOT.exists():
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for path in PLATFORM_JOB_ROOT.glob("*/metadata.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        output_experiment_id = item.get("output_experiment_id")
        if output_experiment_id:
            metadata[str(output_experiment_id)] = item
    return metadata


def result_metadata_for_experiment(experiment_id: str) -> dict[str, Any] | None:
    try:
        experiment, variant, run = decode_experiment_id(experiment_id)
    except ExperimentNotFoundError:
        return None
    metadata_path = RESULT_ROOT / experiment / variant / f"{run}_platform_metadata.json"
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def display_name_for_experiment(experiment_id: str, fallback: str) -> str:
    result_metadata = result_metadata_for_experiment(experiment_id)
    if result_metadata and result_metadata.get("name"):
        return str(result_metadata["name"])
    metadata = job_metadata_by_experiment_id().get(experiment_id)
    if metadata and metadata.get("name"):
        return str(metadata["name"])
    return fallback


def safe_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def parse_round(value: str, fallback: int) -> int:
    try:
        return int(float(value))
    except ValueError:
        return fallback


def read_output_csv(output_path: Path) -> dict[str, Any]:
    with output_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))
    if not rows:
        return {"rounds": [], "metrics": {}}

    rounds = [parse_round(value, index) for index, value in enumerate(rows[0][1:])]
    metrics: dict[str, list[float | None]] = {}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        metric_name = row[0]
        values = [safe_float(value) for value in row[1:]]
        if len(values) < len(rounds):
            values.extend([None] * (len(rounds) - len(values)))
        metrics[metric_name] = values[: len(rounds)]

    return {"rounds": rounds, "metrics": metrics}


def load_torch_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        import torch
    except ImportError:
        return None
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")
    except Exception:
        return None


def numeric_list(value: Any) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "reshape"):
        value = value.reshape(-1)
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if not isinstance(value, list):
        return []
    values: list[float] = []
    for item in value:
        try:
            parsed = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            values.append(parsed)
    return values


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "active_count": 0,
            "mean": None,
            "median": None,
            "p90": None,
            "max": None,
        }
    return {
        "count": len(values),
        "active_count": sum(1 for value in values if value > 0),
        "mean": safe_mean(values),
        "median": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
        "max": max(values),
    }


def is_integer_like(value: float) -> bool:
    return abs(value - round(value)) < 1e-9


def format_bucket_edge(value: float, *, integer_like: bool) -> str:
    if integer_like:
        return str(int(round(value)))
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def build_histogram(values: list[float], max_bins: int = 8) -> list[dict[str, Any]]:
    if not values:
        return []
    integer_like = all(is_integer_like(value) for value in values)
    minimum = min(values)
    maximum = max(values)
    if integer_like:
        minimum_int = int(round(minimum))
        maximum_int = int(round(maximum))
        if maximum_int - minimum_int + 1 <= max_bins:
            buckets = []
            for item in range(minimum_int, maximum_int + 1):
                buckets.append(
                    {
                        "label": str(item),
                        "count": sum(1 for value in values if int(round(value)) == item),
                    }
                )
            return buckets
    if minimum == maximum:
        return [{"label": format_bucket_edge(minimum, integer_like=integer_like), "count": len(values)}]

    step = (maximum - minimum) / max_bins
    counts = [0] * max_bins
    for value in values:
        index = min(max_bins - 1, int((value - minimum) / step))
        counts[index] += 1

    buckets = []
    for index, count in enumerate(counts):
        start = minimum + index * step
        end = maximum if index == max_bins - 1 else minimum + (index + 1) * step
        buckets.append(
            {
                "label": f"{format_bucket_edge(start, integer_like=integer_like)} ~ {format_bucket_edge(end, integer_like=integer_like)}",
                "count": count,
            }
        )
    return buckets


def round_record(record: dict[str, Any] | None, key: str, index: int) -> list[float]:
    if not record:
        return []
    values = record.get(key)
    if not isinstance(values, list) or index >= len(values):
        return []
    return numeric_list(values[index])


def top_ranked_items(
    values: list[float],
    *,
    label_prefix: str,
    extra_columns: dict[str, list[float]] | None = None,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    if not values:
        return []
    indices = sorted(range(len(values)), key=lambda index: values[index], reverse=True)[:top_n]
    rows: list[dict[str, Any]] = []
    for rank, index in enumerate(indices, start=1):
        row: dict[str, Any] = {
            "rank": rank,
            "id": index + 1,
            "label": f"{label_prefix} {index + 1}",
            "value": values[index],
        }
        for column, column_values in (extra_columns or {}).items():
            row[column] = column_values[index] if index < len(column_values) else None
        rows.append(row)
    return rows


def build_micro_snapshots(output_path: Path, rounds: list[int]) -> dict[str, Any]:
    run = output_path.stem.removesuffix("_output")
    output_dir = output_path.parent
    user_record = load_torch_payload(output_dir / f"{run}_user_record.pth")
    creator_record = load_torch_payload(output_dir / f"{run}_creator_record.pth")
    article_record = load_torch_payload(output_dir / f"{run}_article_record.pth")

    snapshots: list[dict[str, Any]] = []
    for index, round_value in enumerate(rounds):
        user_like = round_record(user_record, "like", index)
        user_quality_contribution = round_record(user_record, "liked_quality_contribution", index)
        user_match_contribution = round_record(user_record, "liked_match_contribution", index)

        creator_exposure = round_record(creator_record, "exposure", index)
        creator_click = round_record(creator_record, "click", index)
        creator_like = round_record(creator_record, "like", index)

        article_exposure = round_record(article_record, "exposure", index)
        article_click = round_record(article_record, "click", index)
        article_like = round_record(article_record, "like", index)
        article_quality = round_record(article_record, "quality", index)

        if not any([user_like, creator_exposure, article_exposure, article_quality]):
            continue

        snapshots.append(
            {
                "round": round_value,
                "user": {
                    **summarize_distribution(user_like),
                    "histogram": build_histogram(user_like),
                    "quality_contribution_mean": safe_mean(user_quality_contribution),
                    "match_contribution_mean": safe_mean(user_match_contribution),
                },
                "creator": {
                    **summarize_distribution(creator_exposure),
                    "mean_click": safe_mean(creator_click),
                    "mean_like": safe_mean(creator_like),
                    "histogram": build_histogram(creator_exposure),
                    "top_creators": top_ranked_items(
                        creator_exposure,
                        label_prefix="创作者",
                        extra_columns={"click": creator_click, "like": creator_like},
                    ),
                },
                "article": {
                    **summarize_distribution(article_exposure),
                    "mean_click": safe_mean(article_click),
                    "mean_like": safe_mean(article_like),
                    "mean_quality": safe_mean(article_quality),
                    "quality_p90": percentile(article_quality, 0.9),
                    "histogram": build_histogram(article_exposure),
                    "quality_histogram": build_histogram(article_quality),
                    "top_articles": top_ranked_items(
                        article_exposure,
                        label_prefix="内容",
                        extra_columns={
                            "click": article_click,
                            "like": article_like,
                            "quality": article_quality,
                        },
                    ),
                },
            }
        )

    return {
        "available": bool(snapshots),
        "snapshots": snapshots,
        "latest_round": snapshots[-1]["round"] if snapshots else None,
    }


def latest_value(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def first_value(values: list[float | None]) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def summarize_metrics(metrics: dict[str, list[float | None]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for metric_name, values in metrics.items():
        first = first_value(values)
        latest = latest_value(values)
        delta = None if first is None or latest is None else latest - first
        summary[metric_name] = {
            "label": METRIC_LABELS.get(metric_name, metric_name),
            "first": first,
            "latest": latest,
            "delta": delta,
        }
    return summary


def build_business_findings(summary: dict[str, Any]) -> list[str]:
    findings: list[str] = []

    like_mean = summary.get("Metric-Inter-User-Like-Mean", {})
    if like_mean.get("delta") is not None and like_mean["delta"] > 0:
        findings.append("用户点赞均值上升，说明仿真周期内用户正反馈规模在扩大。")

    creator_gini = summary.get("Metric-Inter-Creator-Exposure-Gini", {})
    if creator_gini.get("delta") is not None:
        if creator_gini["delta"] > 0:
            findings.append("创作者曝光集中度上升，流量更倾向聚集到少数创作者。")
        elif creator_gini["delta"] < 0:
            findings.append("创作者曝光集中度下降，流量分配趋于均衡。")

    quality = summary.get("Metric-Quality-Exposure-Weighted", {})
    if quality.get("delta") is not None and quality["delta"] > 0:
        findings.append("曝光加权质量提升，推荐曝光更偏向高质量内容。")

    homogenization = summary.get("Metric-Homogenization-User-Exposure", {})
    if homogenization.get("delta") is not None and homogenization["delta"] > 0:
        findings.append("曝光同质化增强，需要关注用户看到内容过于相似的风险。")

    if not findings:
        findings.append("当前实验指标变化较平稳，可以进一步与其他策略实验做对比。")
    return findings


def list_experiment_outputs() -> list[Path]:
    if not RESULT_ROOT.exists():
        return []
    return sorted(RESULT_ROOT.glob("*/*/*_output.csv"))


def describe_output(output_path: Path) -> dict[str, Any]:
    variant_dir = output_path.parent
    experiment_dir = variant_dir.parent
    run = output_path.stem.removesuffix("_output")
    stat = output_path.stat()
    parsed = read_output_csv(output_path)
    experiment_id = encode_experiment_id(experiment_dir.name, variant_dir.name, run)
    fallback_name = f"{experiment_dir.name} / {variant_dir.name} / {run}"
    display_name = display_name_for_experiment(experiment_id, fallback_name)
    return {
        "id": experiment_id,
        "name": display_name,
        "display_name": display_name,
        "system_name": fallback_name,
        "experiment": experiment_dir.name,
        "variant": variant_dir.name,
        "run": run,
        "status": "completed",
        "round_count": len(parsed["rounds"]),
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def experiment_detail_payload(experiment_id: str) -> dict[str, Any]:
    output_path = experiment_output_path(experiment_id)
    experiment, variant, run = decode_experiment_id(experiment_id)
    parsed = read_output_csv(output_path)
    summary = summarize_metrics(parsed["metrics"])
    fallback_name = f"{experiment} / {variant} / {run}"
    display_name = display_name_for_experiment(experiment_id, fallback_name)
    return {
        "id": experiment_id,
        "name": display_name,
        "display_name": display_name,
        "system_name": fallback_name,
        "experiment": experiment,
        "variant": variant,
        "run": run,
        "status": "completed",
        "rounds": parsed["rounds"],
        "metrics": parsed["metrics"],
        "summary": summary,
        "findings": build_business_findings(summary),
        "labels": METRIC_LABELS,
        "groups": METRIC_GROUPS,
        "micro": build_micro_snapshots(output_path, parsed["rounds"]),
    }


def experiment_report_payload(experiment_id: str) -> dict[str, Any]:
    output_path = experiment_output_path(experiment_id)
    experiment, variant, run = decode_experiment_id(experiment_id)
    parsed = read_output_csv(output_path)
    summary = summarize_metrics(parsed["metrics"])
    fallback_name = f"{experiment} / {variant} / {run}"
    display_name = display_name_for_experiment(experiment_id, fallback_name)
    overview = {
        metric_name: summary[metric_name]
        for metric_name in METRIC_GROUPS["overview"]
        if metric_name in summary
    }
    return {
        "title": f"{display_name} 策略评估报告",
        "overview": overview,
        "findings": build_business_findings(summary),
    }


def safe_unlink(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except FileNotFoundError:
        return False
    if not resolved_path.is_file() or resolved_root not in resolved_path.parents:
        raise ExperimentDeleteError(f"Refusing to delete unsafe path: {path}")
    resolved_path.unlink()
    return True


def delete_experiment_result(experiment_id: str) -> dict[str, Any]:
    output_path = experiment_output_path(experiment_id)
    experiment, variant, run = decode_experiment_id(experiment_id)
    output_dir = output_path.parent
    deleted: list[str] = []

    candidates = [
        output_dir / f"{run}_output.csv",
        output_dir / f"{run}_static_record.pth",
        output_dir / f"{run}_user_record.pth",
        output_dir / f"{run}_creator_record.pth",
        output_dir / f"{run}_article_record.pth",
        output_dir / f"{run}_recsys_record.pth",
        output_dir / f"{run}_platform_metadata.json",
    ]
    version = f"{experiment}_{variant}_{run}"
    candidates.extend(
        [
            PROJECT_ROOT / "SimuLine" / "Simulation" / "Data" / f"graph_{version}.json",
            PROJECT_ROOT / "SimuLine" / "Simulation" / "Data" / f"info_{version}.json",
        ]
    )

    for candidate in candidates:
        if candidate.exists() and safe_unlink(candidate, PROJECT_ROOT):
            deleted.append(str(candidate))
    return {"id": experiment_id, "deleted": deleted}


def delete_experiment_results(experiment_ids: list[str]) -> dict[str, Any]:
    deleted = []
    errors = []
    for experiment_id in experiment_ids:
        try:
            deleted.append(delete_experiment_result(experiment_id))
        except Exception as exc:
            errors.append({"id": experiment_id, "error": str(exc)})
    return {"deleted": deleted, "errors": errors}
