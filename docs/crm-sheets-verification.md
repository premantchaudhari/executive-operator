# HubSpot and Sheets postcondition contracts

Status: credential-independent handlers and fake-SDK integration/failure tests implemented. No live contact was created and no live spreadsheet was modified during implementation. Full Phase 3 and the combined email/CRM/sheet/reply scenario remain incomplete.

## Common configuration and authorization

Configure actual reviewed SDK tool slugs, dated versions, complete argument maps, explicit `result_path` JSON pointers, account ownership and destination allowlists. The supplied example keeps auth configuration, versions, slugs and `verification_contract` empty; writes stay disabled until reviewed setup. A result path selects within the SDK response's `data`, with empty string selecting the whole data object. Responses must match the documented normalized provider contracts; incompatible schemas require a reviewed adapter rather than guessed field names.

Both handlers run through the existing production gateway and persisted workflow dispatcher. Each write still requires exact owner approval, current submitter/owner permissions and an explicitly selected active account. Readback uses that same account. Configured static defaults cannot overwrite mapped approved arguments. Review all other default fields and side effects against the actual tool schema. The additional read must be authorized by the selected account's scopes and consumes provider resources; complete cost reconciliation is still pending.

## HubSpot contact creation

Set `hubspot.verification_contract` to `hubspot.contact_properties.v1`. Configure both `hubspot.create_contact(email, firstname, lastname)` and `hubspot.get_contact(contact_id)`, including explicit response projections. Readback must include email, firstname and lastname; the sample `properties` default is illustrative and must match the reviewed SDK schema. Review the actual underlying API version rather than assuming a legacy endpoint is current.

The create response projection supplies a bounded contact ID. The handler retrieves that exact ID and requires the same ID, `archived: false`, and exact approved email/name property values. Success evidence contains the contact ID, contract version, a hash of the approved properties and `postcondition_confirmed: true`. This confirms the checked record state; it does not prove duplicate-free identity resolution or prevent a later edit. Missing properties, archived records, changed values and failed readback require review.

## Sheets append

Set `googlesheets.verification_contract` to `google.sheets.raw_append.v1`. Configure `sheets.append` and `sheets.read` with explicit response projections. This contract requires trusted append defaults `value_input_option: RAW` and read defaults `value_render_option: UNFORMATTED_VALUE`; both use row-major data. These parameter names are this reviewed SDK contract's assumptions and must be checked against the selected tool schema. Do not silently use USER_ENTERED/formatted output or adapt incompatible tools by changing only the contract label.

Supported approved ranges name the sheet and an explicit column interval, optionally with row bounds, such as `Tracking!A:C` or `'Owner''s report'!A1:C1000`. The append response must identify the approved spreadsheet and a concrete `updates.updatedRange`/`updatedRows`. The handler validates sheet/column/row bounds and expected row count before reading any returned range. It then reads exactly the appended rows with the full input column width, on the same spreadsheet/account. Every returned scalar must match the approved value. Missing trailing blank cells are treated as empty; booleans are distinct from numeric 0/1. RAW formula-looking strings must read back as the same strings.

Inputs must be rectangular, with at least one nonblank cell in every row. Nonfinite numbers are rejected. Integers outside the exact binary64 integer range must be supplied as strings to avoid precision loss. All-blank rows, ambiguous sheet names/ranges and unsupported shapes fail before dispatch; broader transformations remain part of the file/sandbox backlog. Quoted sheet names and single-cell update receipts are supported.

Success evidence contains the approved spreadsheet ID, returned update range, exact readback range, a hash of the approved rows and `postcondition_confirmed: true`. This is evidence of the checked cells at read time, not an atomic transaction across services or a guarantee against later concurrent edits. The input range participates in provider table detection; review append behavior in the controlled live test, especially bounded row ranges and existing neighboring data.

## Uncertain outcomes and acceptance gates

If an ID/range was returned but readback fails, times out, mismatches or loses authorization, the step becomes `needs_review` with `postcondition_confirmed: false` and available receipt fields. It never becomes a resumable pre-dispatch connection pause. Completed prior steps and their receipts are preserved; repeated worker dispatch cannot silently repeat the write. A provider failure before a usable response may leave no receipt and still requires manual reconciliation. Readback is not rollback and cannot undo an incorrect provider side effect.

Controlled tests cover separate approvals, same-account/version binding, property/cell/range mismatches, RAW/unformatted preflight, revoked readback, timeout receipts, blank-cell normalization, precision protection and a contact→sheet partial failure. These do not establish live SDK compatibility or live acceptance. Remaining gates include reviewed scopes/tool schemas/API versions, controlled read/write/revocation tests, resource ambiguity and duplicate resolution, concurrent-edit handling, typed inter-step dataflow, the complete A02 scenario and production audit.

Official provider references consulted on 2026-11-08:
- https://developers.hubspot.com/docs/api-reference/legacy/crm/objects/contacts/guide
- https://developers.hubspot.com/blog/date-based-api-versioning-migration-playbook
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/UpdateValuesResponse
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption
