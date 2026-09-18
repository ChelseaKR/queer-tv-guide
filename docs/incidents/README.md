# Incidents

How this repository handles an incident, following INCIDENT-RESPONSE-STANDARD
(pinned in `docs/standards/`). None has happened yet.

## When something goes wrong

1. **Open an issue** with the `incident` label and exactly one of `sev1`–`sev4`
   as soon as an event meets the bar (IR-01, IR-02). The issue's open and close
   times are the recovery-time record.
2. **Contain it.** For a leaked credential, follow the standard's §4 runbook
   in order: rotate, revoke, check what it could reach, decide on a history
   scrub (the default is not to rewrite history), then close the way it got in.
3. **Write the postmortem** here as `YYYY-MM-DD-<slug>.md`, copied from
   `TEMPLATE.md`, within 7 days for SEV1/SEV2 and 14 days for SEV3 (IR-05,
   IR-06). Blameless: it names what the system and process allowed, never a
   person as the cause.

## Raised automatically

`freshness.yml` opens a `snapshot freshness:` issue, labelled `incident` and
its severity, when the published snapshot is older than 30 hours (a missed
nightly run, SEV3), older than the 48-hour SLA (SEV2), cannot be read or
dated (SEV2), or the last nightly run failed (SEV3). It comments on that
issue when the situation changes and again when the file is fresh, and
leaves closing it, after the postmortem, to a person.

## What the severities mean here

The standard's ladder, applied to this product:

| Severity | Examples in this repository |
|---|---|
| **SEV1** | The app sends anything, to anyone, beyond the one snapshot GET. A credential or token reaches a pushed commit or a public page. A published snapshot outs a real person: an actor's sexuality or gender, which the pipeline must never store (`docs/data/lezwatch.md`). Data published after a source withdrew its permission. |
| **SEV2** | The published snapshot is wrong in a way users act on: deaths shown for the wrong character or show, or "does she die" answered "no" where the source has no record. The published file is stale past the 48-hour SLA and presented as current. A secret caught by the pre-commit hook before it was pushed. |
| **SEV3** | A subset of shows or characters is wrong or missing. A CI or security gate is found silenced. A nightly run fails and the previous snapshot keeps serving, correctly dated. |
| **SEV4** | A near miss: a gate would have caught something real, or a fixture tripped a scanner. A one-paragraph note here is enough. |

## Contact

See `SECURITY.md` for how to report a vulnerability.
