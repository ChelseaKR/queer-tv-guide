import Foundation

/// Where the snapshot lives on disk and how it is replaced.
///
/// Load order: the last good *downloaded* snapshot in Application Support if
/// it exists and decodes; otherwise the snapshot bundled with the app. A
/// replacement is written to a temporary file in the same directory and then
/// swapped in with a single atomic rename, so a crash mid-write can never
/// leave a half-written file where the app will look for it.
public final class SnapshotStore: @unchecked Sendable {
    public struct Loaded: Equatable, Sendable {
        public enum Origin: Equatable, Sendable {
            case bundled
            case downloaded
        }
        public let snapshot: Snapshot
        public let origin: Origin
        public let etag: String?
    }

    public enum StoreError: Error, Equatable {
        case bundledSnapshotMissing
    }

    public let directory: URL
    public let bundledURL: URL?
    private let decoder = SnapshotDecoder()
    private let fileManager = FileManager.default

    public var snapshotFileURL: URL { directory.appendingPathComponent("snapshot.v1.json") }
    public var etagFileURL: URL { directory.appendingPathComponent("snapshot.v1.etag") }

    /// - Parameters:
    ///   - directory: where downloaded snapshots are kept. Defaults to
    ///     `<Application Support>/Snapshot`. Tests pass a temporary directory.
    ///   - bundledURL: the snapshot shipped inside the app bundle.
    public init(directory: URL, bundledURL: URL?) {
        self.directory = directory
        self.bundledURL = bundledURL
    }

    public static func defaultDirectory() -> URL {
        let base = (try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true))
            ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("Snapshot", isDirectory: true)
    }

    /// Returns the best available snapshot. A downloaded file that no longer
    /// decodes (e.g. after an app update that changed the supported schema
    /// version) is ignored — not deleted — and the bundled copy is used.
    public func load() throws -> Loaded {
        if let data = try? Data(contentsOf: snapshotFileURL),
           let snapshot = try? decoder.decode(data) {
            return Loaded(snapshot: snapshot, origin: .downloaded, etag: readETag())
        }
        guard let bundledURL else { throw StoreError.bundledSnapshotMissing }
        let data = try Data(contentsOf: bundledURL)
        let snapshot = try decoder.decode(data)
        return Loaded(snapshot: snapshot, origin: .bundled, etag: nil)
    }

    /// Validates `data` as a snapshot and, only if it decodes, replaces the
    /// stored file atomically and records `etag`. On any failure the previous
    /// file is untouched.
    @discardableResult
    public func replace(with data: Data, etag: String?) throws -> Snapshot {
        let snapshot = try decoder.decode(data)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
        let temp = directory.appendingPathComponent("snapshot.v1.json.\(UUID().uuidString).tmp")
        try data.write(to: temp, options: [.atomic])
        do {
            _ = try fileManager.replaceItemAt(snapshotFileURL, withItemAt: temp)
        } catch {
            try? fileManager.removeItem(at: temp)
            throw error
        }
        writeETag(etag)
        return snapshot
    }

    public func readETag() -> String? {
        guard let s = try? String(contentsOf: etagFileURL, encoding: .utf8) else { return nil }
        let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func writeETag(_ etag: String?) {
        if let etag, !etag.isEmpty {
            try? etag.write(to: etagFileURL, atomically: true, encoding: .utf8)
        } else {
            try? fileManager.removeItem(at: etagFileURL)
        }
    }
}
