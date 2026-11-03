# Demonstration Procedure — Delay Investigation and Escalation

> **Demo-data notice:** This is an illustrative internal procedure created solely for the SiteSignal portfolio prototype. It is not a real company's policy, contract, or legal advice.

## 1. Record the event

Capture a unique event identifier, affected activity, observed date, reported variance, reporter, and source document. Preserve the original evidence. Do not replace an observed fact with an inferred cause.

## 2. Validate schedule context

Confirm the activity identifier exists in the approved schedule version. Check predecessor relationships, baseline dates, duration units, and the schedule calendar. Flag missing, duplicate, or circular dependencies before calculating impact.

## 3. Calculate downstream impact

Use the dependency network and Critical Path Method to calculate the baseline and impacted schedule. Report the affected activities, total float, critical-path status, and forecast completion-date movement. Distinguish a delay to an individual activity from a delay to overall project completion.

## 4. Assess evidence confidence

Classify information as:

- **Recorded fact:** explicitly present in a supplied source.
- **Calculated result:** computed from the supplied schedule and declared assumptions.
- **Assumption:** an input used for a scenario but not independently verified.
- **Unknown:** information not present in the evidence set.

Do not infer contractual responsibility, cost exposure, safety impact, or root cause without supporting evidence.

## 5. Compare recovery options

A schedule-only simulation may test proposed activity-duration reductions or sequencing changes. Before adopting a recovery option, a competent project manager must verify crew capacity, supplier commitments, cost, overtime, safety, permits, and contractual feasibility.

## 6. Approval and audit

The AI assistant may retrieve evidence, calculate schedules, and draft recommendations. It must not change an approved baseline or issue instructions to contractors. Any operational change requires review and approval by an authorised human decision-maker, with the decision recorded in an audit trail.
