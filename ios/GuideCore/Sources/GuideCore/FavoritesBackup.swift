import Foundation

/// A favorites backup is a file the user holds (DATA-GOVERNANCE-STANDARD
/// DG-10, #25). The app writes it and hands it to the system share sheet;
/// where it goes (Files, AirDrop, another device) is the user's choice each
/// time, and nothing reaches the developer, so the App Store answer stays
/// "Data Not Collected". Import reads a file the user picks. There is no
/// server, no account and no sync (no iCloud key-value store either:
/// `SourceTreeGuardTests` bans it).
///
/// The file is JSON anyone can read:
///
///     {
///       "favourites": [
///         { "added_at": "2026-09-18T09:44:42Z", "id": "lwtv:show:26", "kind": "show" }
///       ],
///       "format": "favourites-backup",
///       "version": 1
///     }
///
/// It holds only what `FavoritesStore` holds: the kind, the snapshot id and
/// when it was added. No titles, no death answers (the file can be opened
/// anywhere, and the spoiler reveal is the app's to keep).
///
/// Import trusts nothing in the file. It is size-capped, must declare this
/// format and a version this build reads, and each entry must be a
/// well-formed id of a kind the app knows. An entry that is well formed but
/// is not in the current snapshot is skipped and counted, never stored.
public enum FavoritesBackup {
    // Written into every backup file: spelling kept so existing files still import.
    public static let format = "favourites-backup"
    public static let version = 1

    /// The largest file import will read. Favoriting every show and
    /// character in the 2026-09-18 snapshot (9,647 entries) exports to about
    /// 1.1 MB; this leaves room for growth and refuses anything far larger.
    public static let maxBytes = 4 * 1024 * 1024

    /// The most entries import will look at.
    public static let maxEntries = 50_000

    // Published file name (docs, support page, ADR 0014): kept to match the format tag.
    public static let suggestedFileName = "favourites-backup.json"

    public enum ImportError: Error, Equatable, LocalizedError {
        case tooLarge(bytes: Int)
        case notABackup
        case unsupportedVersion(Int)
        case tooManyEntries(Int)

        public var errorDescription: String? {
            switch self {
            case .tooLarge:
                return "This file is too large to be a favorites backup."
            case .notABackup:
                return "This file isn't a favorites backup from this app."
            case .unsupportedVersion:
                return "This favorites backup was made by a newer version of the app. Update the app, then import it again."
            case .tooManyEntries(let n):
                return "This file lists \(n) favorites, more than a backup from this app can hold."
            }
        }
    }

    /// What a file held, after validation.
    public struct Parsed: Equatable, Sendable {
        /// Valid entries that are in the current snapshot, first occurrence
        /// of each kept, in file order.
        public let entries: [FavoritesStore.Entry]
        /// Well-formed entries whose show or character is not in the current
        /// snapshot. Skipped.
        public let notInSnapshot: Int
        /// Entries that are not a favorite this app can read (a wrong kind,
        /// a malformed id, not an object). Skipped.
        public let unreadable: Int
    }

    // MARK: Export

    /// The backup file for `entries`: pretty-printed with sorted keys, so
    /// the same favorites always export to the same bytes.
    public static func export(_ entries: [FavoritesStore.Entry]) throws -> Data {
        let items: [[String: Any]] = entries.map { entry in
            ["kind": entry.kind.rawValue, "id": entry.id, "added_at": timestamp.string(from: entry.addedAt)]
        }
        // "favourites" is the file's JSON key: spelling kept so existing files still import.
        let root: [String: Any] = ["format": format, "version": version, "favourites": items]
        return try JSONSerialization.data(withJSONObject: root, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
    }

    // MARK: Import

    /// Validates `data` as a backup. `isKnown` says whether an id is in the
    /// current snapshot; `now` stands in for an `added_at` that is missing,
    /// unreadable or in the future.
    public static func parse(_ data: Data, now: Date, isKnown: (FavoritesStore.Kind, String) -> Bool) throws -> Parsed {
        guard data.count <= maxBytes else { throw ImportError.tooLarge(bytes: data.count) }
        // "favourites" is the file's JSON key, as written by every earlier export.
        guard let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              root["format"] as? String == format,
              let items = root["favourites"] as? [Any] else {
            throw ImportError.notABackup
        }
        guard let fileVersion = root["version"] as? Int else { throw ImportError.notABackup }
        guard fileVersion == version else { throw ImportError.unsupportedVersion(fileVersion) }
        guard items.count <= maxEntries else { throw ImportError.tooManyEntries(items.count) }

        var entries: [FavoritesStore.Entry] = []
        var seen: Set<String> = []
        var notInSnapshot = 0
        var unreadable = 0
        for item in items {
            guard let entry = entry(from: item, now: now) else {
                unreadable += 1
                continue
            }
            guard isKnown(entry.kind, entry.id) else {
                notInSnapshot += 1
                continue
            }
            if seen.insert(entry.key).inserted { entries.append(entry) }
        }
        return Parsed(entries: entries, notInSnapshot: notInSnapshot, unreadable: unreadable)
    }

    /// One file entry, or nil if it is not a favorite this app can read.
    static func entry(from item: Any, now: Date) -> FavoritesStore.Entry? {
        guard let object = item as? [String: Any],
              let kindName = object["kind"] as? String,
              let kind = FavoritesStore.Kind(rawValue: kindName),
              let id = object["id"] as? String,
              isWellFormed(id, kind: kind) else { return nil }
        var added = (object["added_at"] as? String).flatMap(timestamp.date(from:)) ?? now
        if added > now { added = now }
        return FavoritesStore.Entry(kind: kind, id: id, addedAt: added)
    }

    /// The snapshot contract's id shapes (`schema/snapshot.v1.json`):
    /// `lwtv:show:<digits>` and `lwtv:character:<digits>`, and the kind must
    /// match the id.
    public static func isWellFormed(_ id: String, kind: FavoritesStore.Kind) -> Bool {
        let prefix = "lwtv:\(kind.rawValue):"
        guard id.hasPrefix(prefix) else { return false }
        let digits = id.dropFirst(prefix.count)
        return !digits.isEmpty && digits.count <= 12 && digits.allSatisfy { $0.isASCII && $0.isNumber }
    }

    /// Whole-second UTC timestamps, as the snapshot writes its own dates.
    private static let timestamp: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        f.timeZone = TimeZone(identifier: "UTC")
        return f
    }()
}
