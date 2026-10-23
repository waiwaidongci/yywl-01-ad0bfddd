from __future__ import annotations

from typing import Any


HELP_TEXT = (
    "nonparametric-current-status-mle\n"
    "usage: python3 /app/analyze.py INPUT.json REPORT.json\n"
    "help: python3 /app/analyze.py --help\n"
    "time_unit=month\n"
    "method=weighted-isotonic-cdf\n"
    "exit=0 success-or-help;3 refusal\n"
)


def make_payload(
    event_counts: list[int],
    exposed_counts: list[int] | None = None,
    query_times: list[int] | None = None,
    study_id: str = "CS-7A31",
    start_time: int = 1,
) -> dict[str, Any]:
    if exposed_counts is None:
        exposed_counts = [2] * len(event_counts)
    observations = []
    record_number = 1
    for time, (events, exposed) in enumerate(
        zip(event_counts, exposed_counts, strict=True),
        start=start_time,
    ):
        for index in range(exposed):
            observations.append(
                {
                    "record_id": f"CS-{study_id[3:]}-{record_number:03X}",
                    "time": time,
                    "event": 1 if index < events else 0,
                }
            )
            record_number += 1
    if query_times is None:
        query_times = [start_time, start_time + len(event_counts) - 1]
    return {
        "schema_version": 1,
        "study_id": study_id,
        "time_unit": "month",
        "observations": observations,
        "query_times": query_times,
    }


def monotone_payload() -> dict[str, Any]:
    events = [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
    return make_payload(events, query_times=[2, 9, 18])


def violation_payload() -> dict[str, Any]:
    events = [2, 0] * 8 + [2, 2]
    return make_payload(events, query_times=[1, 2, 18])


def tie_payload() -> dict[str, Any]:
    return make_payload([1] * 18, query_times=[1, 9, 18])


def no_median_payload() -> dict[str, Any]:
    return make_payload([0] * 18, query_times=[1, 18])


def minimum_payload() -> dict[str, Any]:
    events = [0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3]
    return make_payload(
        events,
        exposed_counts=[3] * 12,
        query_times=[49, 60],
        study_id="CS-7A32",
        start_time=49,
    )


def maximum_payload() -> dict[str, Any]:
    events = [0] * 5 + [1] * 15 + [2] * 10
    return make_payload(
        events,
        query_times=[1, 5, 6, 20, 21, 30],
        study_id="CS-7A33",
    )


def ratio(numerator: int, denominator: int) -> dict[str, str]:
    return {"numerator": str(numerator), "denominator": str(denominator)}


MONOTONE_EXPECTED = {
    "blocks": [
        {
            "start_time": 1,
            "end_time": 1,
            "events": 0,
            "exposed": 2,
            "cdf": ratio(0, 1),
            "mass": ratio(0, 1),
        },
        {
            "start_time": 2,
            "end_time": 5,
            "events": 4,
            "exposed": 8,
            "cdf": ratio(1, 2),
            "mass": ratio(1, 2),
        },
        {
            "start_time": 6,
            "end_time": 18,
            "events": 26,
            "exposed": 26,
            "cdf": ratio(1, 1),
            "mass": ratio(1, 2),
        },
    ],
    "queries": [
        {"time": 2, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 9, "cdf": ratio(1, 1), "survival": ratio(0, 1)},
        {"time": 18, "cdf": ratio(1, 1), "survival": ratio(0, 1)},
    ],
    "median_interval": {"start_time": 2, "end_time": 5, "cdf": ratio(1, 2)},
    "log_likelihood": -5.545177444479562,
}

VIOLATION_EXPECTED = {
    "blocks": [
        {
            "start_time": 1,
            "end_time": 16,
            "events": 16,
            "exposed": 32,
            "cdf": ratio(1, 2),
            "mass": ratio(1, 2),
        },
        {
            "start_time": 17,
            "end_time": 18,
            "events": 4,
            "exposed": 4,
            "cdf": ratio(1, 1),
            "mass": ratio(1, 2),
        },
    ],
    "queries": [
        {"time": 1, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 2, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 18, "cdf": ratio(1, 1), "survival": ratio(0, 1)},
    ],
    "median_interval": {"start_time": 1, "end_time": 16, "cdf": ratio(1, 2)},
    "log_likelihood": -22.18070977791825,
}

TIE_EXPECTED = {
    "blocks": [
        {
            "start_time": 1,
            "end_time": 18,
            "events": 18,
            "exposed": 36,
            "cdf": ratio(1, 2),
            "mass": ratio(1, 2),
        }
    ],
    "queries": [
        {"time": 1, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 9, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 18, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
    ],
    "median_interval": {"start_time": 1, "end_time": 18, "cdf": ratio(1, 2)},
    "log_likelihood": -24.95329850015803,
}

MAXIMUM_EXPECTED = {
    "blocks": [
        {
            "start_time": 1,
            "end_time": 5,
            "events": 0,
            "exposed": 10,
            "cdf": ratio(0, 1),
            "mass": ratio(0, 1),
        },
        {
            "start_time": 6,
            "end_time": 20,
            "events": 15,
            "exposed": 30,
            "cdf": ratio(1, 2),
            "mass": ratio(1, 2),
        },
        {
            "start_time": 21,
            "end_time": 30,
            "events": 20,
            "exposed": 20,
            "cdf": ratio(1, 1),
            "mass": ratio(1, 2),
        },
    ],
    "queries": [
        {"time": 1, "cdf": ratio(0, 1), "survival": ratio(1, 1)},
        {"time": 5, "cdf": ratio(0, 1), "survival": ratio(1, 1)},
        {"time": 6, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 20, "cdf": ratio(1, 2), "survival": ratio(1, 2)},
        {"time": 21, "cdf": ratio(1, 1), "survival": ratio(0, 1)},
        {"time": 30, "cdf": ratio(1, 1), "survival": ratio(0, 1)},
    ],
    "median_interval": {"start_time": 6, "end_time": 20, "cdf": ratio(1, 2)},
    "log_likelihood": -20.79441541679836,
}

TEST_CASE_IDS = {
    "test_entrypoint_is_executable": ["ENTRY-01"],
    "test_help_contract_is_exact": ["HELP-01", "HELP-NOFILE-02"],
    "test_success_is_silent_and_compact": ["RUN-01", "OUT-COMPACT-01"],
    "test_top_level_schema_and_paths_are_exact": [
        "SCHEMA-01",
        "SCHEMA-KEYS-02",
        "SCHEMA-02",
        "PATH-01",
        "OBS-KEYS-01",
        "OBS-KEYS-02",
        "RECORD-KEYS-01",
        "RECORD-KEYS-02",
    ],
    "test_identifiers_and_unit_are_valid": ["ID-01", "RECORD-ID-01", "UNIT-01"],
    "test_observation_month_boundaries_are_accepted": [
        "OBS-MIN-ACCEPT-01",
        "MONTH-MIN-ACCEPT-01",
        "QUERY-MIN-ACCEPT-01",
    ],
    "test_observation_month_boundaries_are_refused": [
        "OBS-REJECT-01",
        "MONTH-REJECT-01",
        "QUERY-REJECT-01",
    ],
    "test_event_and_time_values_are_validated": [
        "TIME-RANGE-01",
        "EVENT-RANGE-01",
        "EVENT-TYPE-01",
    ],
    "test_duplicate_keys_and_malformed_input_are_refused": [
        "JSON-UTF8-01",
        "JSON-DUP-01",
    ],
    "test_refusal_channel_preserves_existing_report": [
        "REFUSE-CHANNEL-01",
        "REFUSE-PRESERVE-01",
        "WRITE-PARENT-01",
    ],
    "test_refusal_leaves_no_temporary_entries": ["REFUSE-TEMP-01"],
    "test_monotone_input_keeps_observed_order": ["ISO-MONO-01"],
    "test_violations_are_pooled": ["ISO-POOL-01"],
    "test_equal_rates_are_merged": ["ISO-TIE-01"],
    "test_queries_and_median_use_exact_fractions": ["QUERY-EXACT-01", "MEDIAN-01"],
    "test_unreached_median_is_refused": ["MEDIAN-REJECT-01"],
    "test_output_schema_order_is_exact": [
        "OUT-ORDER-01",
        "OUT-ORDER-02",
        "OUT-BLOCK-KEYS-01",
        "OUT-BLOCK-ORDER-02",
        "OUT-QUERY-KEYS-01",
        "OUT-QUERY-ORDER-02",
        "OUT-MEDIAN-KEYS-01",
        "OUT-MEDIAN-KEYS-02",
    ],
    "test_maximum_public_case_finishes_within_limit": ["PERF-20", "PERF-TRUTH-01"],
    "test_repeated_runs_are_byte_identical": ["DETERMINISM-01"],
}
