# Incident: <one-line description> — YYYY-MM-DD

**Severity:** SEV1–4 (see README.md in this directory)
**Status:** Resolved / Monitoring / Postmortem-only (near-miss)
**Related issue:** #NN

<!-- Blameless: describe what the system and process allowed to happen. A
person appears only as a responder, never as the cause. Unknown facts stay
"unknown"; do not fill a gap with a guess. -->

## Summary

Two or three sentences: what happened, what was affected, how it ended.

## Timeline (UTC)

| Time | Event |
|---|---|
| HH:MM | Detected (how, and by what or whom) |
| HH:MM | Acknowledged |
| HH:MM | Contained or mitigated |
| HH:MM | Resolved |

## Impact

Who or what was affected, and for how long. If any data was exposed, say
which tier (DATA-GOVERNANCE-STANDARD §0) and whether its §6 review applies.

## Detection

How it was found: an alert, a scheduled scan, a report, or by accident. "By
accident" is itself an action item.

## Root cause

Five whys or equivalent, about process and tooling.

## What went well

-

## What went poorly

-

## Action items

| Action | Owner | Due | Tracking issue |
|---|---|---|---|

## Related

The incident issue, PRs, the affected release or snapshot `content_digest`,
and for a leaked secret the rotation and revocation record.
