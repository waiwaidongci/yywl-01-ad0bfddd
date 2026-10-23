from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from case_manifest import (
    HELP_TEXT,
    MAXIMUM_EXPECTED,
    MONOTONE_EXPECTED,
    TIE_EXPECTED,
    VIOLATION_EXPECTED,
    make_payload,
    maximum_payload,
    minimum_payload,
    monotone_payload,
    no_median_payload,
    tie_payload,
    violation_payload,
)


ANALYZE = os.environ.get("YEL003_ANALYZE", "/app/analyze.py")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _run_paths(
    input_path: Path,
    output_path: Path,
    timeout: int = 25,
) -> tuple[subprocess.CompletedProcess[bytes], float]:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, ANALYZE, str(input_path), str(output_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return completed, time.perf_counter() - started


def _run_payload(
    tmp_path: Path,
    payload: Any,
    report_name: str = "report.json",
    timeout: int = 25,
) -> tuple[subprocess.CompletedProcess[bytes], Path, float]:
    input_path = tmp_path / "input.json"
    report_path = tmp_path / report_name
    input_path.write_bytes(_json_bytes(payload))
    completed, elapsed = _run_paths(input_path, report_path, timeout)
    return completed, report_path, elapsed


def _run_raw(
    tmp_path: Path,
    raw: bytes,
    report_name: str = "report.json",
) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    input_path = tmp_path / "input.json"
    report_path = tmp_path / report_name
    input_path.write_bytes(raw)
    completed, _elapsed = _run_paths(input_path, report_path)
    return completed, report_path


def _fraction_differences(
    report: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    differences: list[str] = []
    if report["blocks"] != expected["blocks"]:
        differences.append("blocks")
    if report["queries"] != expected["queries"]:
        differences.append("queries")
    if report["median_interval"] != expected["median_interval"]:
        differences.append("median_interval")
    if abs(report["log_likelihood"] - expected["log_likelihood"]) > 0.01:
        differences.append("log_likelihood")
    return differences


def _fraction(value: dict[str, str]) -> Fraction:
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def test_entrypoint_is_executable():
    """题面：「运行时传入输入表和报告路径」。"""
    # CASE ENTRY-01
    target = Path(ANALYZE)
    assert target.is_file()
    assert os.access(target, os.X_OK)
    completed = subprocess.run(
        [sys.executable, ANALYZE, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.startswith(b"nonparametric-current-status-mle\n")
    assert completed.stderr == b""


def test_help_contract_is_exact(tmp_path):
    """题面：「`python3 /app/analyze.py --help` 只打印版本、方法、时间单位和退出码」。"""
    # CASE HELP-01 HELP-NOFILE-02
    before = sorted(path.name for path in tmp_path.iterdir())
    completed = subprocess.run(
        [sys.executable, ANALYZE, "--help"],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == HELP_TEXT
    assert completed.stderr == ""
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_success_is_silent_and_compact(tmp_path):
    """题面：「成功时写紧凑 UTF-8 JSON，末尾一个换行，标准输出和标准错误为空。」"""
    # CASE RUN-01 OUT-COMPACT-01
    text_input = tmp_path / "text-input.json"
    text_report = tmp_path / "text-report.json"
    text_input.write_bytes(_json_bytes(monotone_payload()))
    text_run = subprocess.run(
        [sys.executable, ANALYZE, str(text_input), str(text_report)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=25,
        check=False,
    )
    completed, report_path, _elapsed = _run_payload(tmp_path, monotone_payload())
    raw = report_path.read_bytes()
    assert text_run.stdout == ""
    assert text_run.stderr == ""
    assert completed.returncode == 0
    assert completed.stdout == b""
    assert completed.stderr == b""
    assert raw.endswith(b"\n")
    assert b" " not in raw


def test_top_level_schema_and_paths_are_exact(tmp_path):
    """题面：「输入对象由版本、研究号、时间单位、巡查记录和查询月份五部分组成，键名以示例为准。」"""
    # CASE SCHEMA-01 SCHEMA-KEYS-02 SCHEMA-02 PATH-01 OBS-KEYS-01 OBS-KEYS-02 RECORD-KEYS-01 RECORD-KEYS-02
    valid = monotone_payload()
    extra = dict(valid)
    extra["note"] = "extra"
    extra_result, extra_report, _elapsed = _run_payload(tmp_path, extra, "case_a.json")
    missing = dict(valid)
    missing.pop("query_times")
    missing_result, missing_report, _elapsed = _run_payload(
        tmp_path, missing, "case_b.json"
    )
    invalid_schema = monotone_payload()
    invalid_schema["schema_version"] = True
    schema_result, schema_report, _elapsed = _run_payload(
        tmp_path, invalid_schema, "case_c.json"
    )
    extra_observation = monotone_payload()
    extra_observation["observations"][0]["extra"] = 1
    extra_observation_result, extra_observation_report, _elapsed = _run_payload(
        tmp_path, extra_observation, "case_d.json"
    )
    missing_observation = monotone_payload()
    missing_observation["observations"][0].pop("event")
    missing_observation_result, missing_observation_report, _elapsed = _run_payload(
        tmp_path, missing_observation, "case_e.json"
    )
    relative_input = tmp_path / "input_a.json"
    relative_input.write_bytes(_json_bytes(valid))
    relative = subprocess.run(
        [sys.executable, ANALYZE, "input_a.json", str(tmp_path / "target_b" / "report.json")],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    same_path = subprocess.run(
        [sys.executable, ANALYZE, str(relative_input), str(relative_input)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert extra_result.returncode == 3
    assert not extra_report.exists()
    assert missing_result.returncode == 3
    assert not missing_report.exists()
    assert schema_result.returncode == 3
    assert not schema_report.exists()
    assert extra_observation_result.returncode == 3
    assert not extra_observation_report.exists()
    assert missing_observation_result.returncode == 3
    assert not missing_observation_report.exists()
    assert relative.returncode == 3
    assert same_path.returncode == 3


def test_identifiers_and_unit_are_valid(tmp_path):
    """题面：「`study_id` 采用 `^CS-[0-9A-F]{4}$`」。"""
    # CASE ID-01 RECORD-ID-01 UNIT-01
    bad_study = monotone_payload()
    bad_study["study_id"] = "cs-7a31"
    study_result, study_report, _elapsed = _run_payload(
        tmp_path, bad_study, "case_h.json"
    )
    duplicate_record = monotone_payload()
    duplicate_record["observations"][1]["record_id"] = duplicate_record["observations"][0]["record_id"]
    record_result, record_report, _elapsed = _run_payload(
        tmp_path, duplicate_record, "case_i.json"
    )
    bad_unit = monotone_payload()
    bad_unit["time_unit"] = "day"
    unit_result, unit_report, _elapsed = _run_payload(tmp_path, bad_unit, "case_j.json")
    assert study_result.returncode == 3
    assert not study_report.exists()
    assert record_result.returncode == 3
    assert not record_report.exists()
    assert unit_result.returncode == 3
    assert not unit_report.exists()


def test_observation_month_boundaries_are_accepted(tmp_path):
    """题面：「`observations` 的记录总数落在 `36` 到 `60` 之间，月份覆盖 `12` 到 `30` 个不同值。」"""
    # CASE OBS-MIN-ACCEPT-01 MONTH-MIN-ACCEPT-01 QUERY-MIN-ACCEPT-01
    minimum_result, minimum_report, _elapsed = _run_payload(
        tmp_path, minimum_payload(), "case_k.json"
    )
    maximum_result, maximum_report, _elapsed = _run_payload(
        tmp_path, maximum_payload(), "case_l.json"
    )
    assert minimum_result.returncode == 0
    assert minimum_report.exists()
    assert maximum_result.returncode == 0
    assert maximum_report.exists()


def test_observation_month_boundaries_are_refused(tmp_path):
    """题面：「`query_times` 有 `2` 到 `6` 个严格递增且已观测的月份。」"""
    # CASE OBS-REJECT-01 MONTH-REJECT-01 QUERY-REJECT-01
    too_few_observations = monotone_payload()
    too_few_observations["observations"] = too_few_observations["observations"][:-1]
    obs_low_result, obs_low_report, _elapsed = _run_payload(
        tmp_path, too_few_observations, "case_m.json"
    )
    too_many_observations = maximum_payload()
    template = too_many_observations["observations"][0]
    too_many_observations["observations"].append(dict(template, record_id="CS-7A33-0FF"))
    obs_high_result, obs_high_report, _elapsed = _run_payload(
        tmp_path, too_many_observations, "case_n.json"
    )
    eleven_months = make_payload(
        [0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 3],
        exposed_counts=[4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3],
        query_times=[1, 11],
        study_id="CS-7A34",
    )
    months_low_result, months_low_report, _elapsed = _run_payload(
        tmp_path, eleven_months, "case_o.json"
    )
    thirty_one_months = make_payload(
        [0] * 5 + [1] * 26,
        exposed_counts=[2] * 5 + [1] * 26,
        query_times=[1, 31],
        study_id="CS-7A35",
    )
    months_high_result, months_high_report, _elapsed = _run_payload(
        tmp_path, thirty_one_months, "case_p.json"
    )
    one_query = minimum_payload()
    one_query["query_times"] = [1]
    query_low_result, query_low_report, _elapsed = _run_payload(
        tmp_path, one_query, "case_q.json"
    )
    seven_queries = minimum_payload()
    seven_queries["query_times"] = [1, 2, 3, 4, 5, 6, 7]
    query_high_result, query_high_report, _elapsed = _run_payload(
        tmp_path, seven_queries, "case_r.json"
    )
    unordered_queries = minimum_payload()
    unordered_queries["query_times"] = [12, 1]
    unordered_result, unordered_report, _elapsed = _run_payload(
        tmp_path, unordered_queries, "case_s.json"
    )
    unobserved_query = minimum_payload()
    unobserved_query["query_times"] = [1, 13]
    unobserved_result, unobserved_report, _elapsed = _run_payload(
        tmp_path, unobserved_query, "case_t.json"
    )
    assert obs_low_result.returncode == 3
    assert not obs_low_report.exists()
    assert obs_high_result.returncode == 3
    assert not obs_high_report.exists()
    assert months_low_result.returncode == 3
    assert not months_low_report.exists()
    assert months_high_result.returncode == 3
    assert not months_high_report.exists()
    assert query_low_result.returncode == 3
    assert not query_low_report.exists()
    assert query_high_result.returncode == 3
    assert not query_high_report.exists()
    assert unordered_result.returncode == 3
    assert not unordered_report.exists()
    assert unobserved_result.returncode == 3
    assert not unobserved_report.exists()


def test_event_and_time_values_are_validated(tmp_path):
    """题面：「`event` 只能取整数 `0` 或 `1`，布尔值不算整数。」「`query_times` 有 `2` 到 `6` 个严格递增且已观测的月份。」"""
    # CASE TIME-RANGE-01 EVENT-RANGE-01 EVENT-TYPE-01
    bad_time = monotone_payload()
    bad_time["observations"][0]["time"] = 0
    time_result, time_report, _elapsed = _run_payload(
        tmp_path, bad_time, "case_u.json"
    )
    bad_event = monotone_payload()
    bad_event["observations"][0]["event"] = 2
    event_result, event_report, _elapsed = _run_payload(
        tmp_path, bad_event, "case_v.json"
    )
    bool_event = monotone_payload()
    bool_event["observations"][0]["event"] = False
    bool_result, bool_report, _elapsed = _run_payload(
        tmp_path, bool_event, "case_w.json"
    )
    equal_queries = monotone_payload()
    equal_queries["query_times"] = [3, 3]
    equal_result, equal_report, _elapsed = _run_payload(
        tmp_path, equal_queries, "case_x.json"
    )
    assert time_result.returncode == 3
    assert not time_report.exists()
    assert event_result.returncode == 3
    assert not event_report.exists()
    assert bool_result.returncode == 3
    assert not bool_report.exists()
    assert equal_result.returncode == 3
    assert not equal_report.exists()


def test_duplicate_keys_and_malformed_input_are_refused(tmp_path):
    """题面：「UTF-8 JSON 中任何层级出现重复键都拒收。」"""
    # CASE JSON-UTF8-01 JSON-DUP-01
    valid = _json_bytes(minimum_payload())
    duplicate = b'{"schema_version":1,' + valid[1:]
    duplicate_result, duplicate_report = _run_raw(tmp_path, duplicate, "case_x.json")
    malformed_result, malformed_report = _run_raw(tmp_path, b"{", "case_y.json")
    invalid_utf8_result, invalid_utf8_report = _run_raw(
        tmp_path, b"\xff\xfe", "case_z.json"
    )
    assert duplicate_result.returncode == 3
    assert not duplicate_report.exists()
    assert malformed_result.returncode == 3
    assert not malformed_report.exists()
    assert invalid_utf8_result.returncode == 3
    assert not invalid_utf8_report.exists()


def test_refusal_channel_preserves_existing_report(tmp_path):
    """题面：「标准错误只写一行 `survival refused: ` 后接简短原因，标准输出为空，不输出 traceback。」"""
    # CASE REFUSE-CHANNEL-01 REFUSE-PRESERVE-01 WRITE-PARENT-01
    old_report = b"old-survival\x00\xff"
    input_path = tmp_path / "input.json"
    report_path = tmp_path / "report.json"
    input_path.write_bytes(b"{")
    report_path.write_bytes(old_report)
    completed, _elapsed = _run_paths(input_path, report_path)
    text_refusal = subprocess.run(
        [sys.executable, ANALYZE, str(input_path), str(tmp_path / "case_aa.json")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=25,
        check=False,
    )
    valid_input = tmp_path / "input_b.json"
    valid_input.write_bytes(_json_bytes(minimum_payload()))
    missing_parent = tmp_path / "target_a" / "report.json"
    write_failure, _elapsed = _run_paths(valid_input, missing_parent)
    assert completed.returncode == 3
    assert completed.stdout == b""
    assert text_refusal.stdout == ""
    assert completed.stderr.startswith(b"survival refused: ")
    assert completed.stderr.count(b"\n") == 1
    assert b"Traceback" not in completed.stderr
    assert report_path.read_bytes() == old_report
    assert write_failure.returncode == 3
    assert not missing_parent.exists()


def test_refusal_leaves_no_temporary_entries(tmp_path):
    """题面：「拒收不得创建报告，已有报告保持原字节。」"""
    # CASE REFUSE-TEMP-01
    input_path = tmp_path / "input.json"
    report_path = tmp_path / "report.json"
    input_path.write_bytes(b"not-json")
    report_path.write_bytes(b"keep")
    before = sorted(path.name for path in tmp_path.iterdir())
    completed, _elapsed = _run_paths(input_path, report_path)
    after = sorted(path.name for path in tmp_path.iterdir())
    assert completed.returncode == 3
    assert after == before
    assert report_path.read_bytes() == b"keep"


def test_monotone_input_keeps_observed_order(tmp_path):
    """题面：「在全部满足该约束的分布中，选取使 current-status 二项似然最大的非参数估计。」"""
    # CASE ISO-MONO-01
    completed, report_path, _elapsed = _run_payload(tmp_path, monotone_payload())
    report = json.loads(report_path.read_bytes())
    differences = _fraction_differences(report, MONOTONE_EXPECTED)
    assert completed.returncode == 0
    assert not differences, differences


def test_violations_are_pooled(tmp_path):
    """题面：「相邻原始比例发生下降时就要合并成一个受约束块」。"""
    # CASE ISO-POOL-01
    completed, report_path, _elapsed = _run_payload(tmp_path, violation_payload())
    report = json.loads(report_path.read_bytes())
    differences = _fraction_differences(report, VIOLATION_EXPECTED)
    assert completed.returncode == 0
    assert not differences, differences


def test_equal_rates_are_merged(tmp_path):
    """题面：「比例相等也合并，使最终块按 `F` 严格递增。」"""
    # CASE ISO-TIE-01
    completed, report_path, _elapsed = _run_payload(tmp_path, tie_payload())
    report = json.loads(report_path.read_bytes())
    differences = _fraction_differences(report, TIE_EXPECTED)
    assert completed.returncode == 0
    assert not differences, differences
    assert len(report["blocks"]) == 1


def test_queries_and_median_use_exact_fractions(tmp_path):
    """题面：「所有概率写成约分后的分子、分母字符串，分母为正且 `gcd` 为 1。」"""
    # CASE QUERY-EXACT-01 MEDIAN-01
    completed, report_path, _elapsed = _run_payload(tmp_path, monotone_payload())
    report = json.loads(report_path.read_bytes())
    assert completed.returncode == 0
    assert _fraction(report["queries"][0]["cdf"]) == Fraction(1, 2)
    assert _fraction(report["queries"][0]["survival"]) == Fraction(1, 2)
    assert _fraction(report["blocks"][1]["mass"]) == Fraction(1, 2)
    assert report["median_interval"] == {
        "start_time": 2,
        "end_time": 5,
        "cdf": {"numerator": "1", "denominator": "2"},
    }


def test_unreached_median_is_refused(tmp_path):
    """题面：「总体分布没有越过中位数时拒收。」"""
    # CASE MEDIAN-REJECT-01
    completed, report_path, _elapsed = _run_payload(tmp_path, no_median_payload())
    assert completed.returncode == 3
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"survival refused: ")
    assert not report_path.exists()


def test_output_schema_order_is_exact(tmp_path):
    """题面：「报告顶层顺序固定为 `schema_version`、`study_id`、`time_unit`、`blocks`、`queries`、`median_interval`、`log_likelihood`。」"""
    # CASE OUT-ORDER-01 OUT-ORDER-02 OUT-BLOCK-KEYS-01 OUT-BLOCK-ORDER-02 OUT-QUERY-KEYS-01 OUT-QUERY-ORDER-02 OUT-MEDIAN-KEYS-01 OUT-MEDIAN-KEYS-02
    completed, report_path, _elapsed = _run_payload(tmp_path, monotone_payload())
    report = json.loads(report_path.read_bytes())
    assert completed.returncode == 0
    assert list(report) == [
        "schema_version",
        "study_id",
        "time_unit",
        "blocks",
        "queries",
        "median_interval",
        "log_likelihood",
    ]
    assert list(report["blocks"][0]) == [
        "start_time",
        "end_time",
        "events",
        "exposed",
        "cdf",
        "mass",
    ]
    assert list(report["queries"][0]) == ["time", "cdf", "survival"]
    assert list(report["median_interval"]) == ["start_time", "end_time", "cdf"]


def test_maximum_public_case_finishes_within_limit(tmp_path):
    """题面：「公开上限为 `60` 条记录和 `30` 个不同月份」。"""
    # CASE PERF-20 PERF-TRUTH-01
    completed, report_path, elapsed = _run_payload(
        tmp_path, maximum_payload(), timeout=25
    )
    report = json.loads(report_path.read_bytes())
    differences = _fraction_differences(report, MAXIMUM_EXPECTED)
    assert completed.returncode == 0
    assert elapsed < 20.0
    assert not differences, differences


def test_repeated_runs_are_byte_identical(tmp_path):
    """题面：「同一冻结输入重复运行必须得到相同报告字节。」"""
    # CASE DETERMINISM-01
    first_result, first_path, _elapsed = _run_payload(
        tmp_path, monotone_payload(), "case_ab.json"
    )
    second_result, second_path, _elapsed = _run_payload(
        tmp_path, monotone_payload(), "case_ac.json"
    )
    assert first_result.returncode == 0
    assert second_result.returncode == 0
    assert first_path.read_bytes() == second_path.read_bytes()
