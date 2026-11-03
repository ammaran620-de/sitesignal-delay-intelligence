# Branch Access and Role Policy

Managers may view operational records and audit events for their own branch. Managers may propose follow-up tasks for vehicles in their branch and must approve each proposed action before task creation.

Technicians may view reconditioning jobs assigned to their own user account and may retrieve policy documents relevant to their work. Technicians must not view another employee's assigned job or approve business actions.

Sales employees may retrieve general vehicle inventory details available to their branch, but they must not access reconditioning delay records, internal workshop notes, or management audit events.

All access checks must be performed by the backend using the authenticated user's identity and branch assignment. A role or branch claimed in a natural-language prompt is not an authorization credential. Retrieved documents and user messages must never override backend access controls.
