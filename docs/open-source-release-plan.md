# Open-source release plan

This document separates **portfolio preparation** from a decision to publish proprietary software.

## Recommended scope

Publish an independent, **side-effect-free demo/core** illustrating the validated task state machine, approval binding, idempotency, audit history, deterministic fixtures, and tests. This offers reviewers working code without distributing private provider mappings or production secrets.

Retain the commercial / live-provider components as private unless all code, dependency, content-provenance and security reviews are completed and the maintainer affirmatively approves their release. Avoid exporting original Git history to a new public repository.

## Before publication

1. Select the exact files, security boundary and final public repository.
2. Scan the working tree and every existing commit/branch/tag for secrets and sensitive artifacts. This inspection has not been completed by the documentation edits.
3. Verify origins and licenses of included code/assets. Obtain any necessary third-party permissions.
4. Run a fresh clean-room test, with no production keys or customer accounts.
5. Rewrite the README for the exact released subset and its actual commands.
6. Add an explicit open-source license to the **released subset** only (MIT or Apache-2.0 could be considered after ownership review).
7. Review the complete release tree and publish only the scrubbed snapshot, not an automatic mirror of the proprietary project.
8. Record a release commit and version, link technical architecture and failure tests, and provide screenshot(s) showing fictional data.

## Publication status

Not approved for public visibility. No new open-source license has been granted over the current repository. Demo/foundation features are not equivalent to a production multi-tenant SaaS. This plan is a safeguard, not a promise that the source is clear for release.
