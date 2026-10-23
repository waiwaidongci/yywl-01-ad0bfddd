import pytest

from case_manifest import TEST_CASE_IDS


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or item.name not in TEST_CASE_IDS:
        return
    status = "PASS" if report.passed else "FAIL"
    for case_id in TEST_CASE_IDS[item.name]:
        print(f"CASE {case_id} {status}")
