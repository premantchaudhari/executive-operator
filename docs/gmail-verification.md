# Gmail sent-copy verification contract

Implementation status: credential-independent handler and controlled failure journeys implemented; live Composio schemas, consent/scopes and mailbox acceptance remain unverified. No live messages were sent during implementation.

## Deployment configuration

The example configuration leaves auth IDs, reviewed tool slugs/versions and `verification_contract` empty, so sending remains disabled. Before enabling it, review the actual SDK tool definitions and confirm their request/response schemas with controlled accounts. Configure:

- `gmail.verification_contract`: `google.gmail.sent_plaintext.v1`.
- `gmail.tools.gmail.send`: reviewed dated version, actual send slug, complete argument map and an explicit `result_path`.
- `gmail.tools.gmail.get`: reviewed dated version, actual exact-message read slug, `message_id` argument map and an explicit `result_path`.
- `gmail.allowed_destinations.gmail.send`: exact permitted recipient email strings. This policy does not replace owner approval.

`result_path` is a JSON pointer within the SDK response's `data`. Empty string selects that entire object. No response-field guessing occurs. The send projection must be a Google Gmail Message object with a valid `id`; the read projection must be a complete Gmail Message with that ID, labels and parsed payload. Missing paths or changed schemas fail verification. Non-Google tool response shapes need a reviewed adapter or projection before this contract can work.

Trusted `defaults` can supply SDK-specific static request parameters such as authenticated user `me` and full response format. The sample names are illustrative and must match the reviewed tool schema. Defaults cannot overwrite mapped action arguments. Review every default and tool parameter; the readback must target the authenticated mailbox. Do not add recipients, attachments or content outside the approved action through configuration.

The connected account must support both send and full-message read. Review the chosen OAuth application's scopes; a send-only grant cannot provide full readback. Do not broaden permissions automatically or infer authorization from the hosted callback. `gmail.get` is a read action, not permission to expose retrieved mail elsewhere.

## Verified conditions

The worker pauses for owner approval before sending. The gateway verifies account ownership/selection and destination policy. It sends once, extracts the returned ID, and reads that exact ID through the same selected account and reviewed tool version. The handler requires:

1. Matching message ID, `SENT` label and no `DRAFT` label.
2. Exactly one To and Subject header; the recipient and decoded subject match the approved action. Nonempty Cc/Bcc/Resent recipient headers fail.
3. Single-part plaintext with no attachment, multipart/HTML body or unsupported charset.
4. UTF-8 inline body matching the approved body. Only CRLF-to-LF conversion and one MIME-added terminal newline are accepted.

Evidence includes contract version, message ID, approved-body hash, `sent_copy_confirmed: true` and `delivery_confirmed: false`. This confirms the checked copy in Gmail's sent mailbox; it does not prove delivery, reading, or the business recipient's response. The extra read consumes provider resources; full usage reconciliation remains pending.

## Failure and recovery

Missing verification configuration blocks before any send. Other native writes remain disabled unless their own provider-specific verifier is supplied by trusted application code. A send timeout or failure without a usable ID remains uncertain review. If send returns an ID but lookup, account revalidation or content verification fails, the step stores that ID with unconfirmed sent-copy/delivery flags and enters `needs_review`. No automatic resend, connection resume or following step is allowed. Readback is not rollback; the effect may already exist even when the postcondition fails.

Reconcile uncertain messages in the correct mailbox before making a new intent/approval. Never turn an uncertain send into a pre-dispatch connection failure. The current handler deliberately fails closed for attachments, HTML, richer MIME and response shapes it cannot verify; those features remain on the full backlog.

## Evidence and external gates

Controlled tests cover exact-account/version binding, production approval/dispatch/evidence, repeated dispatch without resend, missing configuration, destination policy, header injection, MIME/body/recipient/ID mismatches and revocation after send. These are fake-SDK contract tests, not live acceptance. Required later: lock/test the actual Composio SDK, review both tools/scopes, verify one controlled approved send/readback, reject once, repeat the same request, exercise timeout/revocation, and inspect receipts in Gmail. The complete email → HubSpot → Sheets → draft → approved reply workflow remains unfinished.

Official response contracts consulted on 2026-11-08:
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/Format
