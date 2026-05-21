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

ENTITY_TYPE_LABELS = {
    "user": "用户",
    "creator": "创作者",
    "article": "内容",
}

ENTITY_STATUS_LABELS = {
    "active": "当前活跃",
    "expired": "已退出活跃窗口",
    "pending": "尚未生成",
}

ENTITY_METRIC_LABELS = {
    "user": {
        "like": "累计点赞",
        "interest_shift": "兴趣漂移",
    },
    "creator": {
        "exposure": "累计曝光",
        "click": "累计点击",
        "like": "累计点赞",
        "latent_shift": "兴趣漂移",
    },
    "article": {
        "exposure": "累计曝光",
        "click": "累计点击",
        "like": "累计点赞",
        "quality": "内容质量",
        "click_through_rate": "点击率",
        "like_through_rate": "点赞率",
    },
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


class EntityNotFoundError(FileNotFoundError):
    """Raised when an entity cannot be resolved for an experiment."""


class EntityTypeError(ValueError):
    """Raised when an unsupported entity type is requested."""


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


def numeric_value(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def value_at(values: list[float], index: int) -> float | None:
    if index < 0 or index >= len(values):
        return None
    return values[index]


def last_non_none_index(values: list[float | None]) -> int | None:
    for index in range(len(values) - 1, -1, -1):
        if values[index] is not None:
            return index
    return None


def rank_of_index(values: list[float], index: int) -> int | None:
    current = value_at(values, index)
    if current is None:
        return None
    return 1 + sum(1 for value in values if value > current)


def share_of_total(value: float | None, values: list[float]) -> float | None:
    if value is None:
        return None
    total = sum(values)
    if total <= 0:
        return None
    return value / total


def tensor_row(matrix: Any, row_index: int) -> list[float]:
    if row_index < 0:
        return []
    if hasattr(matrix, "detach"):
        matrix = matrix.detach().cpu()
    if hasattr(matrix, "shape"):
        shape = tuple(matrix.shape)
        if len(shape) >= 2 and row_index < shape[0]:
            return numeric_list(matrix[row_index])
    if isinstance(matrix, list) and row_index < len(matrix):
        return numeric_list(matrix[row_index])
    return []


def static_value(record: dict[str, Any] | None, key: str, index: int) -> float | None:
    if not record:
        return None
    return value_at(numeric_list(record.get(key)), index)


def latent_shift_series(record: dict[str, Any] | None, row_index: int) -> list[float | None]:
    if not record:
        return []
    latents = record.get("latent")
    if not isinstance(latents, list):
        return []
    shifts: list[float | None] = []
    previous_row: list[float] | None = None
    for matrix in latents:
        current_row = tensor_row(matrix, row_index)
        if not current_row:
            shifts.append(None)
            previous_row = None
            continue
        if previous_row is None or len(previous_row) != len(current_row):
            shifts.append(0.0)
        else:
            shifts.append(
                math.sqrt(sum((current - previous) ** 2 for current, previous in zip(current_row, previous_row)))
            )
        previous_row = current_row
    return shifts


def infer_article_layout(article_record: dict[str, Any] | None) -> dict[str, int]:
    if not article_record:
        return {
            "batch_size": 0,
            "active_window_rounds": 0,
            "current_max_id": 0,
            "total_possible_id": 0,
        }
    lengths = [len(numeric_list(item)) for item in article_record.get("exposure", [])]
    positive_lengths = [length for length in lengths if length > 0]
    batch_size = positive_lengths[0] if positive_lengths else 0
    max_active_count = max(positive_lengths, default=0)
    active_window_rounds = int(max_active_count / batch_size) if batch_size else 0
    latest_index = max((index for index, length in enumerate(lengths) if length > 0), default=-1)
    current_max_id = 0
    if latest_index >= 0 and batch_size and active_window_rounds:
        current_max_id = (
            max(0, latest_index - (active_window_rounds - 1)) * batch_size + lengths[latest_index]
        )

    total_possible_id = 0
    latent = article_record.get("latent")
    if hasattr(latent, "shape") and len(tuple(latent.shape)) >= 1:
        total_possible_id = int(tuple(latent.shape)[0])
    elif isinstance(latent, list):
        total_possible_id = len(latent)

    return {
        "batch_size": batch_size,
        "active_window_rounds": active_window_rounds,
        "current_max_id": current_max_id,
        "total_possible_id": total_possible_id,
    }


def article_offset(round_index: int, layout: dict[str, int]) -> int:
    batch_size = layout["batch_size"]
    active_window_rounds = layout["active_window_rounds"]
    if batch_size <= 0 or active_window_rounds <= 0:
        return 0
    return max(0, round_index - (active_window_rounds - 1)) * batch_size


def article_series(record: dict[str, Any] | None, key: str, entity_id: int, rounds: list[int]) -> list[float | None]:
    if not record:
        return [None] * len(rounds)
    layout = infer_article_layout(record)
    series: list[float | None] = []
    for round_index, _round in enumerate(rounds):
        values = round_record(record, key, round_index)
        local_index = entity_id - 1 - article_offset(round_index, layout)
        series.append(value_at(values, local_index))
    return series


def top_ranked_items(
    values: list[float],
    *,
    label_prefix: str,
    extra_columns: dict[str, list[float]] | None = None,
    top_n: int = 5,
    id_offset: int = 0,
) -> list[dict[str, Any]]:
    if not values:
        return []
    indices = sorted(range(len(values)), key=lambda index: values[index], reverse=True)[:top_n]
    rows: list[dict[str, Any]] = []
    for rank, index in enumerate(indices, start=1):
        entity_id = id_offset + index + 1
        row: dict[str, Any] = {
            "rank": rank,
            "id": entity_id,
            "label": f"{label_prefix} {entity_id}",
            "value": values[index],
        }
        for column, column_values in (extra_columns or {}).items():
            row[column] = column_values[index] if index < len(column_values) else None
        rows.append(row)
    return rows


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


def latest_nonempty_round_index(record: dict[str, Any] | None, key: str, round_count: int) -> int | None:
    for index in range(round_count - 1, -1, -1):
        if round_record(record, key, index):
            return index
    return None


def build_micro_snapshots(output_path: Path, rounds: list[int]) -> dict[str, Any]:
    run = output_path.stem.removesuffix("_output")
    output_dir = output_path.parent
    user_record = load_torch_payload(output_dir / f"{run}_user_record.pth")
    creator_record = load_torch_payload(output_dir / f"{run}_creator_record.pth")
    article_record = load_torch_payload(output_dir / f"{run}_article_record.pth")
    article_layout = infer_article_layout(article_record)

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
                    "top_users": top_ranked_items(
                        user_like,
                        label_prefix="用户",
                    ),
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
                        id_offset=article_offset(index, article_layout),
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


def ensure_entity_type(entity_type: str) -> str:
    normalized = str(entity_type).strip().lower()
    if normalized not in ENTITY_TYPE_LABELS:
        raise EntityTypeError(f"Unsupported entity type: {entity_type}")
    return normalized


def output_record_bundle(output_path: Path) -> dict[str, Any]:
    run = output_path.stem.removesuffix("_output")
    output_dir = output_path.parent
    return {
        "static": load_torch_payload(output_dir / f"{run}_static_record.pth"),
        "user": load_torch_payload(output_dir / f"{run}_user_record.pth"),
        "creator": load_torch_payload(output_dir / f"{run}_creator_record.pth"),
        "article": load_torch_payload(output_dir / f"{run}_article_record.pth"),
        "recsys": load_torch_payload(output_dir / f"{run}_recsys_record.pth"),
    }


def entity_catalog_payload(experiment_id: str) -> dict[str, Any]:
    output_path = experiment_output_path(experiment_id)
    experiment, variant, run = decode_experiment_id(experiment_id)
    parsed = read_output_csv(output_path)
    records = output_record_bundle(output_path)
    article_layout = infer_article_layout(records["article"])
    fallback_name = f"{experiment} / {variant} / {run}"
    display_name = display_name_for_experiment(experiment_id, fallback_name)

    latest_user_index = latest_nonempty_round_index(records["user"], "like", len(parsed["rounds"]))
    latest_creator_index = latest_nonempty_round_index(records["creator"], "exposure", len(parsed["rounds"]))
    latest_article_index = latest_nonempty_round_index(records["article"], "exposure", len(parsed["rounds"]))

    latest_user_like = round_record(records["user"], "like", latest_user_index) if latest_user_index is not None else []
    latest_creator_exposure = round_record(records["creator"], "exposure", latest_creator_index) if latest_creator_index is not None else []
    latest_creator_click = round_record(records["creator"], "click", latest_creator_index) if latest_creator_index is not None else []
    latest_creator_like = round_record(records["creator"], "like", latest_creator_index) if latest_creator_index is not None else []
    latest_article_exposure = round_record(records["article"], "exposure", latest_article_index) if latest_article_index is not None else []
    latest_article_click = round_record(records["article"], "click", latest_article_index) if latest_article_index is not None else []
    latest_article_like = round_record(records["article"], "like", latest_article_index) if latest_article_index is not None else []
    latest_article_quality = round_record(records["article"], "quality", latest_article_index) if latest_article_index is not None else []

    latest_round = parsed["rounds"][-1] if parsed["rounds"] else None

    return {
        "experiment_id": experiment_id,
        "experiment_name": display_name,
        "latest_round": latest_round,
        "entities": {
            "user": {
                "label": ENTITY_TYPE_LABELS["user"],
                "current_max_id": len(latest_user_like) or len(numeric_list(records["static"].get("user_threshold") if records["static"] else None)),
                "total_possible_id": len(latest_user_like) or len(numeric_list(records["static"].get("user_threshold") if records["static"] else None)),
                "top_entities": top_ranked_items(
                    latest_user_like,
                    label_prefix="用户",
                ),
            },
            "creator": {
                "label": ENTITY_TYPE_LABELS["creator"],
                "current_max_id": len(latest_creator_exposure) or len(numeric_list(records["static"].get("creator_concentration") if records["static"] else None)),
                "total_possible_id": len(latest_creator_exposure) or len(numeric_list(records["static"].get("creator_concentration") if records["static"] else None)),
                "top_entities": top_ranked_items(
                    latest_creator_exposure,
                    label_prefix="创作者",
                    extra_columns={
                        "click": latest_creator_click,
                        "like": latest_creator_like,
                    },
                ),
            },
            "article": {
                "label": ENTITY_TYPE_LABELS["article"],
                "current_max_id": article_layout["current_max_id"],
                "total_possible_id": article_layout["total_possible_id"],
                "top_entities": top_ranked_items(
                    latest_article_exposure,
                    label_prefix="内容",
                    id_offset=article_offset(latest_article_index or 0, article_layout),
                    extra_columns={
                        "click": latest_article_click,
                        "like": latest_article_like,
                        "quality": latest_article_quality,
                    },
                ),
            },
        },
    }


def entity_history_rows(rounds: list[int], metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, round_value in enumerate(rounds):
        metric_values = {
            key: values["values"][index] if index < len(values["values"]) else None
            for key, values in metrics.items()
        }
        rows.append(
            {
                "round": round_value,
                "metrics": metric_values,
                "active": any(value is not None for value in metric_values.values()),
            }
        )
    return rows


def user_entity_detail(
    *,
    experiment_id: str,
    experiment_name: str,
    records: dict[str, Any],
    rounds: list[int],
    entity_id: int,
) -> dict[str, Any]:
    user_count = len(numeric_list(records["static"].get("user_threshold") if records["static"] else None))
    if user_count <= 0:
        latest_index = latest_nonempty_round_index(records["user"], "like", len(rounds))
        user_count = len(round_record(records["user"], "like", latest_index)) if latest_index is not None else 0
    if entity_id < 1 or entity_id > user_count:
        raise EntityNotFoundError("User not found")

    entity_index = entity_id - 1
    like_series = [value_at(round_record(records["user"], "like", index), entity_index) for index in range(len(rounds))]
    interest_shift_series = latent_shift_series(records["user"], entity_index)
    latest_index = last_non_none_index(like_series)
    latest_round = rounds[latest_index] if latest_index is not None else None
    latest_round_values = round_record(records["user"], "like", latest_index) if latest_index is not None else []
    current_like = like_series[latest_index] if latest_index is not None else None

    metrics = {
        "like": {"label": ENTITY_METRIC_LABELS["user"]["like"], "values": like_series},
        "interest_shift": {
            "label": ENTITY_METRIC_LABELS["user"]["interest_shift"],
            "values": (interest_shift_series[: len(rounds)] + [None] * len(rounds))[: len(rounds)],
        },
    }

    return {
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "entity_type": "user",
        "entity_type_label": ENTITY_TYPE_LABELS["user"],
        "entity_id": entity_id,
        "label": f"用户 {entity_id}",
        "status": "active",
        "status_label": ENTITY_STATUS_LABELS["active"],
        "latest_round": latest_round,
        "latest_available_round": latest_round,
        "current_max_id": user_count,
        "total_possible_id": user_count,
        "profile": [
            {"label": "兴趣阈值", "value": static_value(records["static"], "user_threshold", entity_index)},
            {"label": "质量偏好权重", "value": static_value(records["static"], "user_like_quality_weight", entity_index)},
            {"label": "匹配偏好权重", "value": static_value(records["static"], "user_like_match_weight", entity_index)},
            {"label": "用户集中度参数", "value": static_value(records["static"], "user_concentration", entity_index)},
        ],
        "current_metrics": [
            {
                "key": "like",
                "label": ENTITY_METRIC_LABELS["user"]["like"],
                "value": current_like,
                "rank": rank_of_index(latest_round_values, entity_index) if latest_index is not None else None,
                "share": share_of_total(current_like, latest_round_values) if latest_index is not None else None,
            },
            {
                "key": "interest_shift",
                "label": ENTITY_METRIC_LABELS["user"]["interest_shift"],
                "value": metrics["interest_shift"]["values"][latest_index] if latest_index is not None else None,
                "rank": None,
                "share": None,
            },
        ],
        "timeline": {
            "rounds": rounds,
            "metrics": metrics,
            "default_metric": "like",
        },
        "history_rows": entity_history_rows(rounds, metrics),
        "notes": [
            "用户点赞来自当前活跃窗口内的累计正反馈。",
            "兴趣阈值和偏好权重来自初始化静态画像，兴趣漂移反映相邻轮次潜在向量变化。",
        ],
    }


def creator_entity_detail(
    *,
    experiment_id: str,
    experiment_name: str,
    records: dict[str, Any],
    rounds: list[int],
    entity_id: int,
) -> dict[str, Any]:
    creator_count = len(numeric_list(records["static"].get("creator_concentration") if records["static"] else None))
    if creator_count <= 0:
        latest_index = latest_nonempty_round_index(records["creator"], "exposure", len(rounds))
        creator_count = len(round_record(records["creator"], "exposure", latest_index)) if latest_index is not None else 0
    if entity_id < 1 or entity_id > creator_count:
        raise EntityNotFoundError("Creator not found")

    entity_index = entity_id - 1
    exposure_series = [value_at(round_record(records["creator"], "exposure", index), entity_index) for index in range(len(rounds))]
    click_series = [value_at(round_record(records["creator"], "click", index), entity_index) for index in range(len(rounds))]
    like_series = [value_at(round_record(records["creator"], "like", index), entity_index) for index in range(len(rounds))]
    creator_latent_shift_series = latent_shift_series(records["creator"], entity_index)
    latest_index = last_non_none_index(exposure_series)
    latest_round = rounds[latest_index] if latest_index is not None else None
    latest_exposure_values = round_record(records["creator"], "exposure", latest_index) if latest_index is not None else []
    latest_click_values = round_record(records["creator"], "click", latest_index) if latest_index is not None else []
    latest_like_values = round_record(records["creator"], "like", latest_index) if latest_index is not None else []

    metrics = {
        "exposure": {"label": ENTITY_METRIC_LABELS["creator"]["exposure"], "values": exposure_series},
        "click": {"label": ENTITY_METRIC_LABELS["creator"]["click"], "values": click_series},
        "like": {"label": ENTITY_METRIC_LABELS["creator"]["like"], "values": like_series},
        "latent_shift": {
            "label": ENTITY_METRIC_LABELS["creator"]["latent_shift"],
            "values": (creator_latent_shift_series[: len(rounds)] + [None] * len(rounds))[: len(rounds)],
        },
    }

    return {
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "entity_type": "creator",
        "entity_type_label": ENTITY_TYPE_LABELS["creator"],
        "entity_id": entity_id,
        "label": f"创作者 {entity_id}",
        "status": "active",
        "status_label": ENTITY_STATUS_LABELS["active"],
        "latest_round": latest_round,
        "latest_available_round": latest_round,
        "current_max_id": creator_count,
        "total_possible_id": creator_count,
        "profile": [
            {"label": "创作集中度参数", "value": static_value(records["static"], "creator_concentration", entity_index)},
        ],
        "current_metrics": [
            {
                "key": "exposure",
                "label": ENTITY_METRIC_LABELS["creator"]["exposure"],
                "value": exposure_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_exposure_values, entity_index) if latest_index is not None else None,
                "share": share_of_total(exposure_series[latest_index], latest_exposure_values) if latest_index is not None else None,
            },
            {
                "key": "click",
                "label": ENTITY_METRIC_LABELS["creator"]["click"],
                "value": click_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_click_values, entity_index) if latest_index is not None else None,
                "share": share_of_total(click_series[latest_index], latest_click_values) if latest_index is not None else None,
            },
            {
                "key": "like",
                "label": ENTITY_METRIC_LABELS["creator"]["like"],
                "value": like_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_like_values, entity_index) if latest_index is not None else None,
                "share": share_of_total(like_series[latest_index], latest_like_values) if latest_index is not None else None,
            },
            {
                "key": "latent_shift",
                "label": ENTITY_METRIC_LABELS["creator"]["latent_shift"],
                "value": metrics["latent_shift"]["values"][latest_index] if latest_index is not None else None,
                "rank": None,
                "share": None,
            },
        ],
        "timeline": {
            "rounds": rounds,
            "metrics": metrics,
            "default_metric": "exposure",
        },
        "history_rows": entity_history_rows(rounds, metrics),
        "notes": [
            "创作者指标是将当前活跃内容窗口内的曝光、点击和点赞聚合到创作者上得到。",
            "兴趣漂移反映创作者潜在向量在相邻轮次的变化。",
        ],
    }


def article_entity_detail(
    *,
    experiment_id: str,
    experiment_name: str,
    records: dict[str, Any],
    rounds: list[int],
    entity_id: int,
) -> dict[str, Any]:
    layout = infer_article_layout(records["article"])
    total_possible_id = layout["total_possible_id"] or layout["current_max_id"]
    if entity_id < 1 or (total_possible_id > 0 and entity_id > total_possible_id):
        raise EntityNotFoundError("Article not found")

    exposure_series = article_series(records["article"], "exposure", entity_id, rounds)
    click_series = article_series(records["article"], "click", entity_id, rounds)
    like_series = article_series(records["article"], "like", entity_id, rounds)
    quality_series = article_series(records["article"], "quality", entity_id, rounds)
    ctr_series = [
        None if exposure is None or exposure <= 0 or click is None else click / exposure
        for exposure, click in zip(exposure_series, click_series)
    ]
    ltr_series = [
        None if click is None or click <= 0 or like is None else like / click
        for click, like in zip(click_series, like_series)
    ]
    available_indices = [index for index, value in enumerate(exposure_series) if value is not None]
    latest_index = available_indices[-1] if available_indices else None
    latest_round = rounds[latest_index] if latest_index is not None else None
    first_round = rounds[available_indices[0]] if available_indices else None

    if latest_index is None:
        status = "pending"
    elif latest_index == len(rounds) - 1:
        status = "active"
    else:
        status = "expired"

    latest_round_values_exposure = round_record(records["article"], "exposure", latest_index) if latest_index is not None else []
    latest_round_values_click = round_record(records["article"], "click", latest_index) if latest_index is not None else []
    latest_round_values_like = round_record(records["article"], "like", latest_index) if latest_index is not None else []
    latest_round_values_quality = round_record(records["article"], "quality", latest_index) if latest_index is not None else []
    latest_local_index = entity_id - 1 - article_offset(latest_index, layout) if latest_index is not None else -1

    metrics = {
        "exposure": {"label": ENTITY_METRIC_LABELS["article"]["exposure"], "values": exposure_series},
        "click": {"label": ENTITY_METRIC_LABELS["article"]["click"], "values": click_series},
        "like": {"label": ENTITY_METRIC_LABELS["article"]["like"], "values": like_series},
        "quality": {"label": ENTITY_METRIC_LABELS["article"]["quality"], "values": quality_series},
        "click_through_rate": {"label": ENTITY_METRIC_LABELS["article"]["click_through_rate"], "values": ctr_series},
        "like_through_rate": {"label": ENTITY_METRIC_LABELS["article"]["like_through_rate"], "values": ltr_series},
    }

    return {
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "entity_type": "article",
        "entity_type_label": ENTITY_TYPE_LABELS["article"],
        "entity_id": entity_id,
        "label": f"内容 {entity_id}",
        "status": status,
        "status_label": ENTITY_STATUS_LABELS[status],
        "latest_round": rounds[-1] if rounds else None,
        "latest_available_round": latest_round,
        "current_max_id": layout["current_max_id"],
        "total_possible_id": total_possible_id,
        "profile": [
            {"label": "首次进入活跃窗口轮次", "value": first_round},
            {"label": "最近一次活跃轮次", "value": latest_round},
            {"label": "质量峰值", "value": max((value for value in quality_series if value is not None), default=None)},
        ],
        "current_metrics": [
            {
                "key": "exposure",
                "label": ENTITY_METRIC_LABELS["article"]["exposure"],
                "value": exposure_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_round_values_exposure, latest_local_index) if latest_index is not None else None,
                "share": share_of_total(exposure_series[latest_index], latest_round_values_exposure) if latest_index is not None else None,
            },
            {
                "key": "click",
                "label": ENTITY_METRIC_LABELS["article"]["click"],
                "value": click_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_round_values_click, latest_local_index) if latest_index is not None else None,
                "share": share_of_total(click_series[latest_index], latest_round_values_click) if latest_index is not None else None,
            },
            {
                "key": "like",
                "label": ENTITY_METRIC_LABELS["article"]["like"],
                "value": like_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_round_values_like, latest_local_index) if latest_index is not None else None,
                "share": share_of_total(like_series[latest_index], latest_round_values_like) if latest_index is not None else None,
            },
            {
                "key": "quality",
                "label": ENTITY_METRIC_LABELS["article"]["quality"],
                "value": quality_series[latest_index] if latest_index is not None else None,
                "rank": rank_of_index(latest_round_values_quality, latest_local_index) if latest_index is not None else None,
                "share": None,
            },
        ],
        "timeline": {
            "rounds": rounds,
            "metrics": metrics,
            "default_metric": "exposure",
        },
        "history_rows": entity_history_rows(rounds, metrics),
        "notes": [
            "内容只在活跃窗口内持续更新，退出窗口后会停止变化。",
            "点击率 = 点击 / 曝光，点赞率 = 点赞 / 点击，可用于观察单篇内容的转化质量。",
        ],
    }


def entity_detail_payload(experiment_id: str, entity_type: str, entity_id: int) -> dict[str, Any]:
    normalized_type = ensure_entity_type(entity_type)
    output_path = experiment_output_path(experiment_id)
    experiment, variant, run = decode_experiment_id(experiment_id)
    parsed = read_output_csv(output_path)
    records = output_record_bundle(output_path)
    fallback_name = f"{experiment} / {variant} / {run}"
    display_name = display_name_for_experiment(experiment_id, fallback_name)

    if normalized_type == "user":
        return user_entity_detail(
            experiment_id=experiment_id,
            experiment_name=display_name,
            records=records,
            rounds=parsed["rounds"],
            entity_id=entity_id,
        )
    if normalized_type == "creator":
        return creator_entity_detail(
            experiment_id=experiment_id,
            experiment_name=display_name,
            records=records,
            rounds=parsed["rounds"],
            entity_id=entity_id,
        )
    return article_entity_detail(
        experiment_id=experiment_id,
        experiment_name=display_name,
        records=records,
        rounds=parsed["rounds"],
        entity_id=entity_id,
    )


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
