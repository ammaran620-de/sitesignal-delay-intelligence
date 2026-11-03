import pytest

from app.schedule_engine import (
    ScheduleValidationError,
    analyze_delay_events,
    calculate_cpm,
    simulate_recovery,
)


@pytest.fixture
def schedule():
    return [
        {"id": "A", "name": "Permits", "duration_days": 3, "predecessors": []},
        {"id": "B", "name": "Structural approval", "duration_days": 2, "predecessors": ["A"]},
        {"id": "C", "name": "Procurement", "duration_days": 5, "predecessors": ["B"]},
        {"id": "D", "name": "Foundation", "duration_days": 4, "predecessors": ["B"]},
        {"id": "E", "name": "Material delivery", "duration_days": 3, "predecessors": ["C"]},
        {"id": "F", "name": "Ground works", "duration_days": 4, "predecessors": ["D", "E"]},
        {"id": "G", "name": "Framing", "duration_days": 5, "predecessors": ["F"]},
        {"id": "H", "name": "Electrical rough-in", "duration_days": 3, "predecessors": ["G"]},
        {"id": "I", "name": "Inspection", "duration_days": 2, "predecessors": ["H"]},
        {"id": "J", "name": "Finishes", "duration_days": 5, "predecessors": ["I"]},
        {"id": "K", "name": "Landscaping", "duration_days": 3, "predecessors": ["F"]},
        {"id": "L", "name": "Handover", "duration_days": 1, "predecessors": ["J", "K"]},
    ]


@pytest.fixture
def events():
    return [
        {
            "id": "EV-001",
            "activity_id": "B",
            "delay_days": 2,
            "summary": "Structural approval was received two days later than planned.",
            "evidence_source": "site_report_001.txt",
        },
        {
            "id": "EV-002",
            "activity_id": "D",
            "delay_days": 2,
            "summary": "Foundation crew mobilization was delayed.",
            "evidence_source": "site_report_002.txt",
        },
    ]


def test_cpm_calculates_project_duration_and_critical_path(schedule):
    result = calculate_cpm(schedule, "2026-11-02")
    assert result["project_duration_days"] == 33
    assert result["project_finish_date"] == "2026-12-05"
    assert result["critical_path"] == ["A", "B", "C", "E", "F", "G", "H", "I", "J", "L"]


def test_noncritical_activity_has_float(schedule):
    result = calculate_cpm(schedule)
    rows = {row["id"]: row for row in result["activities"]}
    assert rows["D"]["total_float_days"] == 4
    assert rows["D"]["is_critical"] is False


def test_missing_predecessor_is_rejected(schedule):
    schedule[0]["predecessors"] = ["DOES-NOT-EXIST"]
    with pytest.raises(ScheduleValidationError, match="missing predecessor"):
        calculate_cpm(schedule)


def test_circular_dependency_is_rejected(schedule):
    schedule[0]["predecessors"] = ["L"]
    with pytest.raises(ScheduleValidationError, match="Circular dependency"):
        calculate_cpm(schedule)


def test_delay_event_propagates_and_preserves_evidence(schedule, events):
    result = analyze_delay_events(schedule, events)
    assert result["baseline"]["project_duration_days"] == 33
    assert result["impacted_schedule"]["project_duration_days"] == 35
    assert result["total_project_completion_delay_days"] == 2
    assert result["events"][0]["evidence_source"] == "site_report_001.txt"
    # The Foundation delay is fully absorbed by its available float.
    assert result["events"][1]["project_completion_delta_if_applied_alone_days"] == 0


def test_recovery_simulation_reports_assumptions(schedule, events):
    result = simulate_recovery(schedule, events, {"C": 1})
    assert result["delayed_duration_days"] == 35
    assert result["recovered_duration_days"] == 34
    assert result["days_recovered_vs_delayed_schedule"] == 1
    assert "does not verify crew availability" in result["feasibility_warning"]


def test_delay_event_without_evidence_is_rejected(schedule):
    bad_event = [{"id": "EV-X", "activity_id": "B", "delay_days": 1, "summary": "Late approval"}]
    with pytest.raises(ScheduleValidationError, match="evidence_source"):
        analyze_delay_events(schedule, bad_event)
