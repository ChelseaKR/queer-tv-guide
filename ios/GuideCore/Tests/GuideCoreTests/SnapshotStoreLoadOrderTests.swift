import XCTest
@testable import GuideCore

/// `SnapshotStore.load()` shows the freshest snapshot on hand: the later
/// `generated_at` of the downloaded file and the bundled one. Before, any
/// downloaded file beat the bundled one, so after an app update that shipped
/// newer data, a months-old download was what people saw (offline, for the
/// whole session).
final class SnapshotStoreLoadOrderTests: XCTestCase {
    private var dir: URL!

    /// The bundled fixture's own date, `2026-09-13T20:00:00Z`.
    private let bundledDate = ISO8601SecondFormatter.date(from: "2026-09-13T20:00:00Z")!

    override func setUpWithError() throws {
        try super.setUpWithError()
        dir = try Repo.temporaryDirectory()
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
        try super.tearDownWithError()
    }

    /// The fixture, dated `generatedAt`.
    private func fixture(dated generatedAt: String) throws -> Data {
        try JSONEdit.edit(try Repo.fixtureData()) { $0["generated_at"] = generatedAt }
    }

    private func makeStore(bundledURL: URL? = Repo.fixtureURL) -> SnapshotStore {
        SnapshotStore(directory: dir, bundledURL: bundledURL)
    }

    func testAnOlderDownloadedSnapshotLosesToTheBundledOne() throws {
        let store = makeStore()
        let older = try fixture(dated: "2026-09-01T00:00:00Z")
        try store.replace(with: older, etag: "\"old\"")

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertEqual(loaded.snapshot.generatedAt, bundledDate)
        XCTAssertNil(loaded.etag, "the bundled file has no ETag; the stored one belongs to the older download")
        // Nothing is deleted or rewritten: the older file and its ETag stay on disk.
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), older)
        XCTAssertEqual(store.readETag(), "\"old\"")
    }

    func testANewerDownloadedSnapshotWins() throws {
        let store = makeStore()
        try store.replace(with: try fixture(dated: "2026-09-14T00:00:00Z"), etag: "\"new\"")

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .downloaded)
        XCTAssertEqual(loaded.snapshot.generatedAt, ISO8601SecondFormatter.date(from: "2026-09-14T00:00:00Z"))
        XCTAssertEqual(loaded.etag, "\"new\"")
    }

    func testEqualDatesPreferTheDownloadedFile() throws {
        let store = makeStore()
        try store.replace(with: try Repo.fixtureData(), etag: "\"same\"")

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .downloaded)
        XCTAssertEqual(loaded.etag, "\"same\"", "so the next refresh can be conditional")
    }

    func testTheSecondBeforeAndAfterTheBundledDate() throws {
        let store = makeStore()
        try store.replace(with: try fixture(dated: "2026-09-13T19:59:59Z"), etag: "\"a\"")
        XCTAssertEqual(try store.load().origin, .bundled, "one second older loses")
        try store.replace(with: try fixture(dated: "2026-09-13T20:00:01Z"), etag: "\"b\"")
        XCTAssertEqual(try store.load().origin, .downloaded, "one second newer wins")
    }

    func testABundledSnapshotThatWouldWinButDoesNotDecodeLosesToTheDownloadedOne() throws {
        // Dated later than the download, but a schema version this app does
        // not read: it is not a snapshot the app can show.
        let bundled = dir.appendingPathComponent("bundled-newer-but-unreadable.json")
        try JSONEdit.edit(try Repo.fixtureData()) {
            $0["generated_at"] = "2030-01-01T00:00:00Z"
            $0["schema_version"] = "99"
        }.write(to: bundled)
        let store = makeStore(bundledURL: bundled)
        try store.replace(with: try fixture(dated: "2026-09-01T00:00:00Z"), etag: "\"old\"")

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .downloaded)
        XCTAssertEqual(loaded.etag, "\"old\"")
    }

    func testADownloadWithNoBundledSnapshotAtAllStillLoads() throws {
        let store = makeStore(bundledURL: nil)
        try store.replace(with: try fixture(dated: "2026-09-01T00:00:00Z"), etag: "\"old\"")
        XCTAssertEqual(try store.load().origin, .downloaded)
        let missing = makeStore(bundledURL: dir.appendingPathComponent("no-such-file.json"))
        XCTAssertEqual(try missing.load().origin, .downloaded)
    }

    func testAnUndecodableDownloadStillFallsBackToTheBundledOne() throws {
        let store = makeStore()
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try Data("garbage".utf8).write(to: store.snapshotFileURL)
        XCTAssertEqual(try store.load().origin, .bundled)
    }

    func testNothingDownloadedLoadsTheBundledOne() throws {
        let loaded = try makeStore().load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertNil(loaded.etag)
    }

    // MARK: On the real bundled snapshot

    func testAMonthsOldDownloadLosesToTheRealBundledSnapshot() throws {
        guard let realData = try? Data(contentsOf: Repo.bundledSnapshot) else {
            return XCTFail("\(Repo.bundledSnapshot.path) is missing: run `make -C ios bundle-snapshot`")
        }
        let realDate = try SnapshotDecoder().decode(realData).generatedAt
        let store = makeStore(bundledURL: Repo.bundledSnapshot)
        // The fixture (2026-09-13) is the "old" download here: skip, rather
        // than pass for the wrong reason, if the bundled file is not newer.
        try XCTSkipUnless(realDate > bundledDate, "the bundled snapshot is not newer than the fixture")
        try store.replace(with: try Repo.fixtureData(), etag: "\"old\"")

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertEqual(loaded.snapshot.generatedAt, realDate)
        XCTAssertGreaterThan(loaded.snapshot.shows.count, 1000, "it is the real catalog, not the fixture")

        // And a download newer than the real one wins.
        try store.replace(with: try fixture(dated: "2099-01-01T00:00:00Z"), etag: "\"future\"")
        XCTAssertEqual(try store.load().origin, .downloaded)
    }
}
