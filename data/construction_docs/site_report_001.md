# Site Incident Report — EV-001: Structural approval delay

> **Demo-data notice:** This is synthetic portfolio evidence. It is not a real project record, client document, Escalo document, or independently verified incident.

## Record metadata

| Field | Value |
|---|---|
| Project ID | SS-DEMO-001 |
| Event ID | EV-001 |
| Activity ID | B |
| Activity | Structural design approval |
| Reported by | Design Coordinator |
| Event date | 9 November 2026 |
| Evidence reference | AR-001 (synthetic approval register) |
| Status | Verified within synthetic demo dataset |

## Incident statement

The baseline schedule places the finish of Activity B, Structural design approval, on **7 November 2026**. The synthetic approval register records approval on **9 November 2026**, a variance of **two calendar days**.

For schedule analysis, SiteSignal represents this variance as a two-day effective extension to Activity B. This is an explicit modelling assumption; it does not claim the design-review work itself required two additional productive workdays.

## Evidence excerpt

Synthetic approval-register entry:

- Register reference: `AR-001`
- Baseline approval due: `2026-11-07`
- Recorded approval date: `2026-11-09`
- Variance: `+2 calendar days`
- Recorded status: `Approved`

## Dependency context

Activity B is a predecessor to structural material procurement (C). The critical downstream sequence is:

`B → C → E → F → G → H → I → J → L`

The schedule engine recalculates downstream dates from the explicit dependency graph. It does not infer supplier behaviour, contractual liability, cost impact, or safety implications.

## Follow-up questions

1. Confirm the approved drawing revision is the revision released to procurement.
2. Obtain supplier acknowledgement and a committed delivery date.
3. Record any supplier response as a separate dated evidence item.
4. Do not approve acceleration solely from this record.

## Data limitations

No email thread, supplier confirmation, contract clause, cost estimate, or external source is attached. The root cause of the late approval is not established by this report.
