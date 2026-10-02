import Foundation

/// Where the snapshot lives on disk and how it is replaced.
///
/// Load order: the newer, by `generated_at`, of the last good *downloaded*
/// snapshot in Application Support (if it exists and decodes) and the
/// snapshot bundled with the app. A replacement is written to a temporary
/// file in the same directory and then swapped in with a single atomic
/// rename, so a crash mid-write can never leave a half-written file where
/// the app will look for it.
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

    /// Returns the freshest snapshot on hand: whichever of the last good
    /// downloaded one and the bundled one has the later `generated_at`. An
    /// equal date prefers the downloaded one (it carries the ETag, so the
    /// next refresh can be conditional). After an app update that ships a
    /// newer bundled snapshot, an older downloaded file from months ago no
    /// longer wins, offline or not.
    ///
    /// A downloaded file that no longer decodes (e.g. after an app update
    /// that changed the supported schema version) is ignored, not deleted,
    /// and the bundled copy is used. A bundled copy that would win on date
    /// but does not decode loses to the downloaded one. When the bundled
    /// snapshot is what loads, its `etag` is `nil`: the bundled file has
    /// none, and the stored ETag belongs to the downloaded file.
    public func load() throws -> Loaded {
        if let data = try? Data(contentsOf: snapshotFileURL),
           let downloaded = try? decoder.decode(data) {
            if let newerBundled = bundledSnapshot(newerThan: downloaded.generatedAt) {
                return Loaded(snapshot: newerBundled, origin: .bundled, etag: nil)
            }
            return Loaded(snapshot: downloaded, origin: .downloaded, etag: readETag())
        }
        guard let bundledURL else { throw StoreError.bundledSnapshotMissing }
        let data = try Data(contentsOf: bundledURL)
        let snapshot = try decoder.decode(data)
        return Loaded(snapshot: snapshot, origin: .bundled, etag: nil)
    }

    /// The bundled snapshot, decoded in full, if it is dated after `date`
    /// and is a valid snapshot; otherwise `nil`. Its date is read first from
    /// a two-field view of the file, so the common case (the downloaded file
    /// is the newer one) does not decode the whole bundled file a second time.
    private func bundledSnapshot(newerThan date: Date) -> Snapshot? {
        guard let bundledURL,
              let data = try? Data(contentsOf: bundledURL),
              let generatedAt = try? JSONDecoder().decode(GeneratedAtOnly.self, from: data).generatedAt.date,
              generatedAt > date else { return nil }
        return try? decoder.decode(data)
    }

    private struct GeneratedAtOnly: Decodable {
        let generatedAt: TaggedDate
        private enum CodingKeys: String, CodingKey { case generatedAt = "generated_at" }
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
