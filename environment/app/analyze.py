#!/usr/bin/env python3
"""Legacy raw-proportion survival report."""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path


def ratio(value: Fraction) -> dict[str, str]:
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        return 2
    try:
        payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        observations = payload["observations"]
        query_times = payload["query_times"]
    except (OSError, ValueError, KeyError, TypeError):
        return 2

    counts: dict[int, list[int]] = {}
    for row in observations:
        bucket = counts.setdefault(int(row["time"]), [0, 0])
        bucket[1] += 1
        bucket[0] += int(row["event"])

    blocks = []
    cdf_by_time = {}
    previous = Fraction(0, 1)
    for time in sorted(counts):
        events, exposed = counts[time]
        cdf = Fraction(events, exposed)
        mass = cdf - previous
        previous = cdf
        cdf_by_time[time] = cdf
        blocks.append(
            {
                "start_time": time,
                "end_time": time,
                "events": events,
                "exposed": exposed,
                "cdf": ratio(cdf),
                "mass": ratio(mass),
            }
        )

    blocks_for_median = [
        block for block in blocks if Fraction(
            int(block["cdf"]["numerator"]), int(block["cdf"]["denominator"])
        ) >= Fraction(1, 2)
    ]
    median = blocks_for_median[0]
    report = {
        "schema_version": 1,
        "study_id": payload.get("study_id", ""),
        "time_unit": "month",
        "blocks": blocks,
        "queries": [
            {
                "time": time,
                "cdf": ratio(cdf_by_time[time]),
                "survival": ratio(1 - cdf_by_time[time]),
            }
            for time in query_times
        ],
        "median_interval": {
            "start_time": median["start_time"],
            "end_time": median["end_time"],
            "cdf": median["cdf"],
        },
        "log_likelihood": 0.0,
    }
    try:
        Path(argv[2]).write_text(
            json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
