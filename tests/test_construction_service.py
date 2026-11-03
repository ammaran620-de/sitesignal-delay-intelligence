from app.construction_service import (
    ConstructionDataError,
    get_project_overview,
    investigate_delay,
    load_project,
    simulate_named_recovery,
)


def test_project_dataset_is_explicitly_synthetic_and_complete():
    project = load_project()
    assert project["project"]["data_status"] == "SYNTHETIC_DEMO_DATA"
    assert len(project["activities"]) == 12
    assert len(project["delay_events"]) == 2


def test_overview_calculates_baseline_and_combined_delay():
    result = get_project_overview()
    assert result["metrics"]["baseline_duration_days"] == 33
    assert result["metrics"]["forecast_duration_days"] == 35
    assert result["metrics"]["completion_delay_days"] == 2
    assert result["metrics"]["baseline_finish_date"] == "2026-12-05"
    assert result["metrics"]["forecast_finish_date"] == "2026-12-07"


def test_noncritical_mobilisation_event_is_absorbed_by_float():
    result = get_project_overview()
    event = next(item for item in result["impact"]["events"] if item["event_id"] == "EV-002")
    assert event["project_completion_delta_if_applied_alone_days"] == 0
    assert event["baseline_activity_was_critical"] is False


def test_investigation_returns_source_provenance_and_synthetic_notice():
    result = investigate_delay("EV-001")
    assert result["evidence"]["source"] == "site_report_001.md"
    assert result["evidence"]["synthetic"] is True
    assert "2026-11-09" in result["evidence"]["content"]


def test_recovery_is_schedule_only_and_does_not_change_baseline():
    result = simulate_named_recovery("REC-001")
    assert result["simulation"]["delayed_duration_days"] == 35
    assert result["simulation"]["recovered_duration_days"] == 34
    assert result["approval_required"] is True
    assert "does not verify" in result["simulation"]["feasibility_warning"]


def test_unknown_event_is_rejected():
    try:
        investigate_delay("EV-DOES-NOT-EXIST")
    except LookupError as exc:
        assert "Unknown delay event" in str(exc)
    else:
        raise AssertionError("Unknown event should be rejected")
