# queer-tv-guide: the one local gate for the whole repository.
#
# `make verify` runs every merge-blocking check CI runs, as the same commands
# (CI-CD-STANDARD §9, CICD-27). CI jobs call these targets by name, and
# tests/test_ci_parity.py fails if a verify target is not called by any
# workflow or a workflow calls a root target that verify does not run.
#
# The repository holds two projects (pipeline/ in Python, ios/ in Swift). This
# file exposes both from the root, as CI-CD §9 asks of a nested project; each
# project keeps its own build files.
#
# Needs: uv (>= 0.11), git, curl, and the Swift toolchain on macOS for
# `guidecore`. Scanner binaries are downloaded and SHA-256-verified by
# scripts/fetch-tool.sh; the Python-based scanners run at pinned versions
# through uvx.

SHELL := bash
# GNU make >= 3.82 applies .SHELLFLAGS; the make 3.81 that macOS ships ignores
# it, and there `false; echo ok` in a recipe exits 0. So every recipe line that
# runs more than one command also starts with `set -euo pipefail;` itself, and
# tests/test_ci_parity.py fails on one that does not.
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := verify

UV_RUN := uv run --no-project --python 3.12 python
ZIZMOR := uvx --python 3.12 zizmor@1.30.1
SEMGREP := uvx --python 3.12 semgrep@1.177.0
PIP_AUDIT := uvx --python 3.12 pip-audit@2.10.1
# Same ruff release as pipeline/uv.lock. The root Python (tests/, scripts/) has
# no pyproject of its own (the pipeline's is the one Python config), so its
# CODE-QUALITY §2 rule set is passed here and config files are ignored.
RUFF := uvx --python 3.12 ruff@0.16.7
RUFF_ROOT := --isolated --target-version py312 --line-length 100
ROOT_PY := tests scripts

VERIFY_TARGETS := pipeline guidecore a11y policy workflows secrets sast sca

.PHONY: verify $(VERIFY_TARGETS)

verify: $(VERIFY_TARGETS)
	@echo "verify: $(words $(VERIFY_TARGETS)) gates passed: $(VERIFY_TARGETS)"

# The Python pipeline's own gate. The lockfile check comes first because a
# bare `uv run` or `uv sync` silently rewrites a stale uv.lock (CQ-09).
pipeline:
	cd pipeline && uv lock --check
	$(MAKE) -C pipeline verify

# The iOS app's logic package. It uses Apple's Foundation networking types,
# so it builds on macOS, not Linux. ios/Makefile's package-test first fetches
# and checksum-verifies the bundled snapshot that BundledSnapshotTests check.
guidecore:
	$(MAKE) -C ios package-test

# The app's accessibility gate (#22): Xcode's accessibility audit over every
# screen, and the check that a closed "does she die" answer is not in the
# accessibility tree, in the iOS simulator. Needs Xcode 26 with the iOS 26.5
# simulator runtime (ios/Makefile's test-a11y says why the version is pinned).
a11y:
	$(MAKE) -C ios test-a11y

# Repository policy tests (tests/): workflow invariants, make/CI parity,
# vendored-standards integrity, and the gitleaks allowlist negative controls,
# after lint and format checks over the root Python. The gitleaks fetch runs
# as its own statement so a failed download stops here instead of handing
# the tests an empty path.
policy:
	$(RUFF) format --check $(RUFF_ROOT) $(ROOT_PY)
	$(RUFF) check $(RUFF_ROOT) --select E,W,F,I,UP,B,SIM,S,C90,RUF --ignore E501 \
		--per-file-ignores 'tests/*:S101' --per-file-ignores 'tests/*:S603' $(ROOT_PY)
	set -euo pipefail; gitleaks="$$(scripts/fetch-tool.sh gitleaks)"; \
	GITLEAKS="$$gitleaks" $(UV_RUN) -m unittest discover --start-directory tests --verbose

# Workflow SAST (CICD-19). The first zizmor run is the gate: any finding at
# medium or above that .github/zizmor.yml does not waive fails it. The second
# run ignores the config and proves every waiver still matches a real
# finding, so a waiver cannot outlive the defect it excuses. zizmor exits
# 10-14 when it reports findings; any other non-zero exit means it did not run.
workflows:
	$(ZIZMOR) --offline --config .github/zizmor.yml --min-severity medium .github/workflows
	set -euo pipefail; report="$$(mktemp)"; trap 'rm -f "$$report"' EXIT; rc=0; \
	$(ZIZMOR) --offline --no-config --format json .github/workflows > "$$report" || rc=$$?; \
	case "$$rc" in 0|1[0-4]) ;; *) echo "zizmor did not run (exit $$rc)" >&2; exit 1 ;; esac; \
	$(UV_RUN) scripts/check_zizmor_waivers.py "$$report" .github/zizmor.yml

# Secret scanning (SEC-17/SEC-18): every commit in history, then the tracked
# tree as plain files. History mode scans patches, so it misses a secret
# introduced while resolving a merge and anything .gitattributes marks binary;
# the file pass catches those. It scans `git checkout-index` output rather
# than the working directory, so untracked trees like pipeline/.venv are not
# read. It runs from inside that copy because the allowlist in .gitleaks.toml
# matches repository-relative paths.
secrets:
	set -euo pipefail; gitleaks="$$(scripts/fetch-tool.sh gitleaks)"; \
	"$$gitleaks" git --no-banner --redact --exit-code 1 --config .gitleaks.toml .; \
	tree="$$(mktemp -d)"; trap 'rm -rf "$$tree"' EXIT; \
	git checkout-index --all --prefix="$$tree/"; \
	cd "$$tree"; \
	"$$gitleaks" dir --no-banner --redact --exit-code 1 --config "$(CURDIR)/.gitleaks.toml" .

# SAST (SEC-07) and the no-sensitive-values-in-logs rule (OBS-11). `--test`
# runs first: each custom rule in .semgrep/ must still fire on its `ruleid:`
# fixture lines and stay quiet on its `ok:` lines, so the scan below cannot
# pass on a rule that has stopped matching anything. The engine is pinned; the
# p/ rule packs are fetched from the Semgrep registry at scan time and can
# change between runs.
sast:
	$(SEMGREP) --test --metrics off .semgrep
	$(SEMGREP) scan --metrics off --error --severity WARNING --severity ERROR \
		--config p/python --config p/secrets --config p/swift --config .semgrep \
		--exclude .semgrep --exclude docs/standards --exclude docs/terms-snapshots .

# Dependency CVEs (SEC-11, SEC-13, CQ-11): pip-audit over the exact locked and
# hashed requirement set, then osv-scanner over pipeline/uv.lock itself. No
# `|| true` anywhere: a finding fails the target. The count line is the
# denominator: `grep -c` exits non-zero on zero matches, so an empty export
# stops here instead of letting pip-audit report a clean audit of nothing.
sca:
	set -euo pipefail; req="$$(mktemp)"; trap 'rm -f "$$req"' EXIT; \
	uv export --project pipeline --frozen --all-groups --format requirements-txt \
		--no-emit-project --output-file "$$req" >/dev/null; \
	count="$$(grep -cE '^[A-Za-z0-9]' "$$req")"; \
	echo "sca: auditing $$count locked packages"; \
	$(PIP_AUDIT) --requirement "$$req" --require-hashes --disable-pip --strict --progress-spinner off; \
	osv="$$(scripts/fetch-tool.sh osv-scanner)"; \
	"$$osv" scan source --lockfile pipeline/uv.lock
