# Security policy

This is a small, one-maintainer project: an iOS app that shows TV data from
a static file, plus the pipeline that builds that file. The app has no
accounts, no server of its own, no analytics and no third-party SDKs. Its
only network call is one HTTPS GET of the published snapshot. Reports are
still welcome and are read by the maintainer.

## Supported versions

| Version | Receives security fixes |
|---|---|
| `main` (pre-release; nothing has shipped yet) | yes |
| Released App Store builds | none exist yet. After launch, only the current App Store version receives fixes. |

The published snapshot file (`snapshot.v1.json` on GitHub Pages) is rebuilt
nightly from `main`, so a fix to the pipeline reaches it on the next run.

## Reporting a vulnerability

**Do not put exploit details in a public place** (a public issue, an App Store
review, a social post).

- **While this repository is private:** only its collaborators can read it.
  Open an issue here with `[security]` at the start of the title, or contact
  the maintainer directly. GitHub's private vulnerability reporting is only available on
  public repositories, so it is not offered here yet.
- **After the app launches:** use the support link on the app's App Store
  page, the same route the privacy policy gives for questions.
- **If this repository is ever made public:** private vulnerability reporting
  will be switched on, and this section will point to it.

You can expect an acknowledgement within **72 hours** and an assessment
within a week. Please include what you did, what you saw, and which version
or snapshot `content_digest` you were looking at. No bug bounty is offered.

## What is in scope

- The iOS app in `ios/`, including anything that would make it send data
  anywhere other than the one snapshot URL, store data off the device, or
  display data from a source it did not verify.
- The pipeline in `pipeline/` and the workflows in `.github/workflows/`,
  including anything that could publish a tampered snapshot or leak a
  credential.
- The published snapshot, for example a way to get content into it that did
  not come from LezWatch.TV or TVmaze.

## Out of scope

LezWatch.TV and TVmaze themselves. Report problems with their data or
services to them. This project never contacts them on anyone's behalf.

## How the repository defends itself

These gates run on every pull request, on every push to `main`, and weekly:
secret scanning (gitleaks, over history and the tracked tree), SAST
(semgrep, plus a rule against credentials or personal data in log calls),
dependency CVEs (pip-audit and osv-scanner over the locked set), and
workflow SAST (zizmor). A weekly TruffleHog scan reads the full history and
reports all three result tiers, so a credential that was committed and later
revoked is still found. `make verify` runs the same pull-request gates
locally. See `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` in `docs/standards/`
for the policy these implement.
