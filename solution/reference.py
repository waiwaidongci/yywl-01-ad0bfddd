#!/usr/bin/env python3
"""Nonparametric current-status survival estimate with weighted PAVA."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


TOP_KEYS = ("schema_version", "study_id", "time_unit", "observations", "query_times")
OBSERVATION_KEYS = ("record_id", "time", "event")
STUDY_RE = re.compile(r"^CS-[0-9A-F]{4}$")
RECORD_RE = re.compile(r"^CS-[0-9A-F]{4}-[0-9A-F]{3}$")
HELP_TEXT = (
    "nonparametric-current-status-mle\n"
    "usage: python3 /app/analyze.py INPUT.json REPORT.json\n"
    "help: python3 /app/analyze.py --help\n"
    "time_unit=month\n"
    "method=weighted-isotonic-cdf\n"
    "exit=0 success-or-help;3 refusal\n"
)


class Refusal(Exception):
    """A stable command-line refusal."""


@dataclass
class Block:
    start_time: int
    end_time: int
    events: int
    exposed: int

    @property
    def cdf(self) -> Fraction:
        return Fraction(self.events, self.exposed)


def exact_keys(value: Any, expected: Iterable[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Refusal(f"{name} must be an object")
    if set(value) != set(expected):
        raise Refusal(f"{name} has missing or extra keys")
    return value


def duplicate_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("duplicate key")
        result[key] = value
    return result


def invalid_constant(_text: str) -> None:
    raise Refusal("non-finite JSON number")


def require_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Refusal(f"{name} must be an integer")
    if value < low or value > high:
        raise Refusal(f"{name} is outside its allowed range")
    return value


def parse_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("input is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=duplicate_hook,
            parse_constant=invalid_constant,
        )
    except Refusal:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise Refusal("input is invalid JSON") from exc


def validate_payload(payload: Any) -> tuple[str, dict[int, list[int]], list[int]]:
    envelope = exact_keys(payload, TOP_KEYS, "top level")
    require_int(envelope["schema_version"], "schema_version", 1, 1)
    study_id = envelope["study_id"]
    if not isinstance(study_id, str) or STUDY_RE.fullmatch(study_id) is None:
        raise Refusal("study_id is invalid")
    if envelope["time_unit"] != "month":
        raise Refusal("time_unit must be month")

    raw_observations = envelope["observations"]
    if not isinstance(raw_observations, list) or not 36 <= len(raw_observations) <= 60:
        raise Refusal("observation count is outside its allowed range")
    counts: dict[int, list[int]] = {}
    seen_records: set[str] = set()
    for index, raw_observation in enumerate(raw_observations):
        row = exact_keys(raw_observation, OBSERVATION_KEYS, f"observation {index}")
        record_id = row["record_id"]
        if not isinstance(record_id, str) or RECORD_RE.fullmatch(record_id) is None:
            raise Refusal(f"observation {index} record_id is invalid")
        if record_id in seen_records:
            raise Refusal("record_id values must be unique")
        seen_records.add(record_id)
        time = require_int(row["time"], f"observation {index} time", 1, 60)
        event = require_int(row["event"], f"observation {index} event", 0, 1)
        bucket = counts.setdefault(time, [0, 0])
        bucket[0] += event
        bucket[1] += 1

    if not 12 <= len(counts) <= 30:
        raise Refusal("distinct inspection month count is outside its allowed range")
    raw_queries = envelope["query_times"]
    if not isinstance(raw_queries, list) or not 2 <= len(raw_queries) <= 6:
        raise Refusal("query time count is outside its allowed range")
    queries = [
        require_int(value, f"query_time {index}", 1, 60)
        for index, value in enumerate(raw_queries)
    ]
    if any(queries[index] >= queries[index + 1] for index in range(len(queries) - 1)):
        raise Refusal("query_times must be strictly increasing")
    if any(value not in counts for value in queries):
        raise Refusal("query_times must be observed months")
    return study_id, counts, queries


def pool_adjacent_violators(counts: dict[int, list[int]]) -> list[Block]:
    blocks: list[Block] = []
    for time in sorted(counts):
        events, exposed = counts[time]
        blocks.append(Block(time, time, events, exposed))
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            if left.events * right.exposed < right.events * left.exposed:
                break
            blocks[-2:] = [
                Block(
                    left.start_time,
                    right.end_time,
                    left.events + right.events,
                    left.exposed + right.exposed,
                )
            ]
    return blocks


def fraction_object(value: Fraction) -> dict[str, str]:
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def build_report(
    study_id: str,
    counts: dict[int, list[int]],
    queries: list[int],
) -> dict[str, Any]:
    blocks = pool_adjacent_violators(counts)
    cdf_by_time: dict[int, Fraction] = {}
    report_blocks = []
    previous_cdf = Fraction(0, 1)
    for block in blocks:
        cdf = block.cdf
        mass = cdf - previous_cdf
        report_blocks.append(
            {
                "start_time": block.start_time,
                "end_time": block.end_time,
                "events": block.events,
                "exposed": block.exposed,
                "cdf": fraction_object(cdf),
                "mass": fraction_object(mass),
            }
        )
        for time in counts:
            if block.start_time <= time <= block.end_time:
                cdf_by_time[time] = cdf
        previous_cdf = cdf

    median_block = next((block for block in blocks if block.cdf >= Fraction(1, 2)), None)
    if median_block is None:
        raise Refusal("median is not reached")

    terms = []
    for time, (events, exposed) in counts.items():
        cdf = cdf_by_time[time]
        if events:
            terms.append(events * math.log(float(cdf)))
        if exposed > events:
            terms.append((exposed - events) * math.log(float(1 - cdf)))
    log_likelihood = math.fsum(terms)
    if not math.isfinite(log_likelihood):
        raise Refusal("log likelihood is not finite")

    return {
        "schema_version": 1,
        "study_id": study_id,
        "time_unit": "month",
        "blocks": report_blocks,
        "queries": [
            {
                "time": time,
                "cdf": fraction_object(cdf_by_time[time]),
                "survival": fraction_object(1 - cdf_by_time[time]),
            }
            for time in queries
        ],
        "median_interval": {
            "start_time": median_block.start_time,
            "end_time": median_block.end_time,
            "cdf": fraction_object(median_block.cdf),
        },
        "log_likelihood": log_likelihood,
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if not path.parent.is_dir():
        raise Refusal("report parent directory does not exist")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".survival-", delete=False
        ) as handle:
            temporary_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    except OSError as exc:
        raise Refusal("report cannot be written") from exc
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def run(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--help":
        sys.stdout.write(HELP_TEXT)
        return 0
    if len(argv) != 3:
        raise Refusal("wrong argument count")
    input_path = Path(argv[1])
    output_path = Path(argv[2])
    if not input_path.is_absolute() or not output_path.is_absolute():
        raise Refusal("paths must be absolute")
    try:
        resolved_input = input_path.resolve(strict=True)
    except OSError as exc:
        raise Refusal("input cannot be resolved") from exc
    resolved_output = output_path.resolve(strict=False)
    if resolved_input == resolved_output:
        raise Refusal("input and report paths must differ")
    try:
        raw = resolved_input.read_bytes()
    except OSError as exc:
        raise Refusal("input cannot be read") from exc
    payload = parse_json(raw)
    study_id, counts, queries = validate_payload(payload)
    atomic_write(resolved_output, build_report(study_id, counts, queries))
    return 0


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except Refusal as exc:
        print(f"survival refused: {exc}", file=sys.stderr)
        return 3
    except Exception:
        print("survival refused: internal analysis failure", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
