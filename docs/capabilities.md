# Capability and claim ledger

**Current as of:** 2026-09-17.

What this project may honestly claim today (DOCUMENTATION-STANDARD §10,
DOC-21). Automated evidence shows behaviour under test fixtures and static
checks of the source. It does not establish what the shipped binary does on a
device, App Review's view, legal fitness, or that a disabled person can use
the app. When this ledger and a dated research or planning document disagree,
this ledger is current.

Status vocabulary:

- **Shipped**: on `main` with linked automated evidence.
- **Partial**: an implementation exists, but the named gap limits the claim.
- **Planned**: nothing usable on `main` yet.
- **Externally unvalidated**: implemented with automated evidence, but the
  outcome still needs independent human or platform review.

| Capability | Status | Current claim | Evidence | Explicit gap |
| --- | --- | --- | --- | --- |
| No data collected | Externally unvalidated | The app source contains one network host (the snapshot URL), one URLSession, no third-party code, no analytics or tracking, and a privacy manifest declaring nothing collected; the privacy policy says the one request reveals an IP address to GitHub Pages, whose logs are GitHub's. | [source-tree guards](../ios/GuideCore/Tests/GuideCoreTests/SourceTreeGuardTests.swift), [privacy manifest](../ios/QueerTVGuide/PrivacyInfo.xcprivacy), [privacy policy](site/privacy.html), [decision 0002](DECISIONS.md) | Static checks of the source, not a capture of what the running binary sends. The App Store privacy label has not been submitted or reviewed. |
| Unrecorded deaths shown as unknown | Shipped | A death LezWatch.TV has not recorded is `null` in the snapshot (the schema forbids `false`). The app states it as not recorded, never as survival, per character and per show (never "nobody dies"), behind a reveal that is closed by default. | [schema](../schema/snapshot.v1.json), [pipeline test](../pipeline/tests/test_build_end_to_end.py), [app wording tests](../ios/GuideCore/Tests/GuideCoreTests/PresentationTests.swift) | Only as complete as LezWatch.TV's records. Deaths are recorded per character, so a character who appears in several shows is not pinned on one. |
| Licensed, attributed data | Shipped | Every source was read, quoted and snapshotted before use; the pipeline re-reads LezWatch.TV's terms on every run and stops if the reuse grant is gone; the snapshot carries the CC BY-SA 4.0 notice and both sources' credits; every show and character screen links its LezWatch.TV page, and every TVmaze schedule shown carries TVmaze's credit and licence link (audited 2026-09-17, DECISIONS 0013). | [licences and attribution audit](LICENSES-AND-ATTRIBUTION.md), [terms gate tests](../pipeline/tests/test_terms.py), [terms snapshot checksums](../pipeline/tests/test_terms_snapshots.py), [snapshot attribution tests](../pipeline/tests/test_attribution.py), [app attribution tests](../ios/GuideCore/Tests/GuideCoreTests/AttributionTests.swift) | Not a legal opinion. LezWatch.TV's grant is a terms-of-use page that can change, not a formal licence. |
| Works offline, refreshes with one request | Shipped | The app bundles the real published snapshot (checksum-verified, never the test fixture) and refreshes it with a conditional GET of one static file; a failed refresh keeps the last good copy. | [bundled snapshot tests](../ios/GuideCore/Tests/GuideCoreTests/BundledSnapshotTests.swift), [refresher tests](../ios/GuideCore/Tests/GuideCoreTests/SnapshotRefresherTests.swift), [store tests](../ios/GuideCore/Tests/GuideCoreTests/SnapshotStoreTests.swift) | The bundled copy is only as fresh as the last build. The app shows its data-as-of date, and a next-episode date that has passed says so. |
| Accessible with VoiceOver and Dynamic Type | Partial | Rows and reveals carry explicit VoiceOver labels, and a UI test checks that a row's label names its network. VoiceOver focus moves to an answer when it is revealed. Reveals respect Reduce Motion. Text uses Dynamic Type styles, and rows stack at accessibility sizes. Text and accent colours were chosen for 4.5:1 contrast. | [UI tests](../ios/QueerTVGuideUITests/QueerTVGuideUITests.swift), [accessibility audit tests](../ios/QueerTVGuideUITests/AccessibilityAuditTests.swift), [contrast colours](../ios/QueerTVGuide/Views/Components/AccessibleStyle.swift) | CI runs Xcode's accessibility audit on every screen, in the iOS 26.5 simulator only. It also checks that a closed "does she die" answer is not in the accessibility tree. No person has done a VoiceOver walkthrough on a device yet ([checklist](a11y/voiceover-walkthrough-checklist.md)). No WCAG or conformance claim is made. |
