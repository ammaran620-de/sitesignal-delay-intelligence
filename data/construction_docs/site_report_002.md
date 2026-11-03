# Site Incident Report — EV-002: Site preparation crew mobilisation delay

> **Demo-data notice:** This is synthetic portfolio evidence. It is not a real project record, client document, Escalo document, or independently verified incident.

## Record metadata

| Field | Value |
|---|---|
| Project ID | SS-DEMO-001 |
| Event ID | EV-002 |
| Activity ID | D |
| Activity | Prepare site work area for foundation activities |
| Reported by | Site Manager |
| Event date | 7 November 2026 |
| Evidence reference | SM-002 (synthetic site diary) |
| Status | Verified within synthetic demo dataset |

## Incident statement

The baseline schedule places the early start of Activity D on **5 November 2026**. The synthetic site diary records crew mobilisation on **7 November 2026**, two calendar days later than the baseline early-start date.

The schedule model represents this as a two-day effective extension to Activity D. Activity D is a parallel, non-critical branch in the baseline network. The delay can therefore be absorbed by its available total float in this scenario.

## Evidence excerpt

Synthetic site-diary entry:

- Diary reference: `SM-002`
- Baseline early-start date: `2026-11-05`
- Recorded mobilisation date: `2026-11-07`
- Variance: `+2 calendar days`
- Recorded activity: Site work-area preparation

## Dependency context

Activity D depends on site permits/access (A) and merges into ground works (F). It is independent of structural approval (B) in this synthetic network. This is intentional: it allows the demo to distinguish a critical-path approval delay from a non-critical site mobilisation delay.

The schedule engine calculates whether the delay consumes available float. It does not validate crew availability, site conditions, or actual construction feasibility.

## Follow-up questions

1. Confirm the site area was available and safe for the crew on mobilisation.
2. Confirm whether the two-day shift affected any independent inspection or access constraint.
3. Capture any further progress variance as a separate dated record.

## Data limitations

No signed timesheet, access permit, weather log, safety record, or external evidence is attached. The reason for late mobilisation is not established by this report.
