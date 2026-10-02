import Foundation

public enum SnapshotDecodingError: Error, Equatable, LocalizedError {
    case unsupportedSchemaVersion(String)
    case malformed(String)

    public var errorDescription: String? {
        switch self {
        case .unsupportedSchemaVersion(let v):
            return "Snapshot schema_version \"\(v)\" is not supported (this app reads \"\(Snapshot.supportedSchemaVersion)\")."
        case .malformed(let detail):
            return "Snapshot is malformed: \(detail)"
        }
    }
}

/// Decodes `schema/snapshot.v1.json` documents (the JSON Schema at that path
/// is the contract; this decodes instances of it).
///
/// Per `schema/README.md`: "the app should validate `schema_version == \"1\"`
/// and otherwise trust the shape." Beyond the schema version, this decoder
/// checks what the schema cannot say and the app cannot do without: each
/// source's credit is present exactly once (`requireEachCredit`). The
/// schema's `attribution` needs two items with `source` of `lezwatch` or
/// `tvmaze`, so two LezWatch items validate, and the app would then show
/// TVmaze's dates with no TVmaze credit.
///
/// Everything else relies on `Decodable` conformances that mirror the
/// schema's own `required`/nullable structure: a field the schema marks
/// nullable decodes to `nil` on absence, never to a default; a field the
/// schema requires but this document omits fails the whole decode (a genuine
/// contract violation, not a soft absence).
///
/// In the app, every snapshot it reads, bundled or downloaded, comes through
/// `decode(_:)` by way of `SnapshotStore`, so a rule enforced here holds for
/// both (SnapshotAttributionGateTests pins that no other code decodes a
/// `Snapshot` directly).
public struct SnapshotDecoder {
    public init() {}

    public func decode(_ data: Data) throws -> Snapshot {
        let decoder = JSONDecoder()
        let snapshot: Snapshot
        do {
            snapshot = try decoder.decode(Snapshot.self, from: data)
        } catch let error as SnapshotDecodingError {
            throw error
        } catch let error as DecodingError {
            throw SnapshotDecodingError.malformed(Self.describe(error))
        } catch {
            throw SnapshotDecodingError.malformed("\(error)")
        }
        try Self.requireEachCredit(in: snapshot)
        return snapshot
    }

    /// LezWatch.TV's and TVmaze's credits must each appear exactly once. A
    /// file without TVmaze's would put TVmaze's next-episode dates on screen
    /// with no credit, and the terms of both sources require one, so it is
    /// refused whole (`SnapshotStore.replace` then keeps the last good file)
    /// rather than shown uncredited. Sources other than these two are not
    /// this rule's business.
    static func requireEachCredit(in snapshot: Snapshot) throws {
        for source in [Attribution.lezWatchSource, Attribution.tvmazeSource] {
            switch snapshot.attribution.filter({ $0.source == source }).count {
            case 1:
                continue
            case 0:
                throw SnapshotDecodingError.malformed("attribution has no entry for source \(source)")
            case let count:
                throw SnapshotDecodingError.malformed("attribution has \(count) entries for source \(source), expected exactly one")
            }
        }
    }

    private static func describe(_ error: DecodingError) -> String {
        switch error {
        case .keyNotFound(let key, let ctx):
            return "missing key '\(key.stringValue)' at \(path(ctx))"
        case .typeMismatch(_, let ctx):
            return "type mismatch at \(path(ctx)): \(ctx.debugDescription)"
        case .valueNotFound(_, let ctx):
            return "null where a value is required at \(path(ctx))"
        case .dataCorrupted(let ctx):
            return "data corrupted at \(path(ctx)): \(ctx.debugDescription)"
        @unknown default:
            return "\(error)"
        }
    }

    private static func path(_ ctx: DecodingError.Context) -> String {
        let p = ctx.codingPath.map { $0.intValue.map(String.init) ?? $0.stringValue }.joined(separator: ".")
        return p.isEmpty ? "<root>" : p
    }
}
