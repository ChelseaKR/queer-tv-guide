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
/// and otherwise trust the shape." Accordingly this decoder does exactly one
/// semantic check — the schema version — and otherwise relies on `Decodable`
/// conformances that mirror the schema's own `required`/nullable structure:
/// a field the schema marks nullable decodes to `nil` on absence, never to a
/// default; a field the schema requires but this document omits fails the
/// whole decode (a genuine contract violation, not a soft absence).
public struct SnapshotDecoder {
    public init() {}

    public func decode(_ data: Data) throws -> Snapshot {
        let decoder = JSONDecoder()
        do {
            return try decoder.decode(Snapshot.self, from: data)
        } catch let error as SnapshotDecodingError {
            throw error
        } catch let error as DecodingError {
            throw SnapshotDecodingError.malformed(Self.describe(error))
        } catch {
            throw SnapshotDecodingError.malformed("\(error)")
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
