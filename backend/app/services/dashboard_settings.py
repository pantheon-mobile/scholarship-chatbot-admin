"""Display selection only; metric names/order and aggregation remain application-owned."""
import json
import os

METRIC_IDS = ('access_count', 'access_user_count', 'chat_count', 'chat_user_count', 'average_chats_per_day', 'average_chats_per_user', 'response_count', 'average_responses_per_chat', 'average_responses_per_user', 'response_time_average', 'response_time_range', 'valid_answer_count', 'no_answer_count', 'answer_rate', 'good_count', 'bad_count', 'unrated_count', 'satisfaction_rate', 'comment_count', 'good_comment_count', 'bad_comment_count')


def visible_basic_metrics() -> list[str]:
    raw = os.getenv("DASHBOARD_BASIC_METRICS", "")
    if not raw.strip():
        return list(METRIC_IDS)
    try:
        settings = json.loads(raw)
    except ValueError as exc:
        raise ValueError("DASHBOARD_BASIC_METRICS must be valid JSON") from exc
    if not isinstance(settings, dict):
        raise ValueError("DASHBOARD_BASIC_METRICS must be an object")
    for key, entry in settings.items():
        if key not in METRIC_IDS:
            raise ValueError(f"Unknown dashboard metric: {key}")
        if (not isinstance(entry, dict) or set(entry) != {"name", "visible"}
                or not isinstance(entry["name"], str) or not entry["name"].strip()
                or type(entry["visible"]) is not int or entry["visible"] not in (0, 1)):
            raise ValueError(f"{key}: name must be a nonempty string and visible must be 0 or 1")
    # Missing entries retain the existing visible behavior, including future metrics.
    return [key for key in METRIC_IDS if settings.get(key, {}).get("visible", 1) == 1]
