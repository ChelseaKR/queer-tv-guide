# 0014. Back up favourites as a file the user holds, not a sync

- **Status:** Proposed
- **Date:** 2026-09-18
- **Deciders:** Chelsea Kelly-Reif (owner)

## Context

DATA-GOVERNANCE-STANDARD DG-10 asks every repository with a persistent local
store to document a backup mechanism and test it with an export and import
round trip (#25). Favourites are the app's only user data: a list of show and
character ids with the date each was added, in `UserDefaults` under
`favourites.v1`. They are already part of the device's own iCloud or computer
backup, but that restores a whole device, not favourites onto a new one, and
the app never tested it.

The product's premise is that the App Store answer "Data Not Collected" is
literally true (DECISIONS 0002). Apple defines "collect" as "transmitting data
off the device in a way that allows you and/or your third-party partners to
access it for a period longer than what is necessary to service the
transmitted request in real time", and says "Data that is processed only on
device is not 'collected'"
(https://developer.apple.com/app-store/app-privacy-details/, read 2026-09-18).

Three options:

1. A server or an account. Collection by definition; ruled out.
2. iCloud key-value sync (`NSUbiquitousKeyValueStore`). Apple hosts that data,
   and Apple says "You are not responsible for disclosing data collected by
   Apple", so the label would stay true. But it adds an entitlement and a
   second network path the app does not control, it breaks the privacy
   policy's "never synced", and `SourceTreeGuardTests` bans the API as part of
   the one-host premise. #25 does not ask for it.
3. A file the user exports and imports. The app writes it and hands it to the
   share sheet; the user picks the destination every time. Nothing reaches
   the developer or any partner.

## Decision

- Favourites are backed up as a file, option 3. The … menu on Favourites has
  Export favourites (a `ShareLink` of `favourites-backup.json`) and Import
  favourites (the system file picker).
- The format is JSON, `{"format": "favourites-backup", "version": 1,
  "favourites": [{"kind", "id", "added_at"}]}`, holding only what
  `FavouritesStore` holds. No titles and no death answers, so the file gives
  nothing away wherever it is opened. `FavouritesBackup` in GuideCore owns it.
- Import trusts nothing: at most 4 MB and 50,000 entries, the format and
  version must match, each id must have the snapshot contract's shape for its
  kind, and an id the loaded snapshot does not have is skipped and counted,
  never stored. Import adds to the saved favourites and keeps their dates.
- No iCloud sync. The device backup stays the second mechanism, and the
  privacy policy and support page say so.

## Consequences

- The label stays "Data Not Collected", with nothing new to disclose, and the
  one-host guard is unchanged.
- The file format is now a contract with files people keep. A change that
  would break reading an old file gets a new `version`, and import must keep
  reading version 1. Today a newer version is refused with "update the app",
  never guessed at.
- A backup made against one snapshot can lose entries on import if LezWatch.TV
  removes a show or character. The app says how many it skipped.
- `FavouritesBackupTests` holds the round trip (through a file, on the fixture
  and on the real bundled snapshot) and the validation rules. If they move,
  this record moves with them.
- Reopen if people ask for automatic sync across their devices. iCloud
  key-value sync would then need its own record, a privacy-policy change and
  a change to the one-host guard.
