import XCTest
@testable import GuideCore

final class SnapshotStoreTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        dir = try Repo.temporaryDirectory()
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
        try super.tearDownWithError()
    }

    func testFallsBackToBundledWhenNothingDownloaded() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertNil(loaded.etag)
        XCTAssertEqual(loaded.snapshot.shows.count, 4)
    }

    func testMissingBundledSnapshotIsAnError() {
        let store = SnapshotStore(directory: dir, bundledURL: nil)
        XCTAssertThrowsError(try store.load()) { error in
            XCTAssertEqual(error as? SnapshotStore.StoreError, .bundledSnapshotMissing)
        }
    }

    func testReplaceWritesFileAndETagAndIsPreferredOnLoad() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        let newer = try JSONEdit.edit(try Repo.fixtureData()) { $0["generated_at"] = "2026-09-14T00:00:00Z" }
        let snapshot = try store.replace(with: newer, etag: "\"abc\"")
        XCTAssertEqual(snapshot.generatedAt, ISO8601SecondFormatter.date(from: "2026-09-14T00:00:00Z"))

        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .downloaded)
        XCTAssertEqual(loaded.etag, "\"abc\"")
        XCTAssertEqual(loaded.snapshot.generatedAt, ISO8601SecondFormatter.date(from: "2026-09-14T00:00:00Z"))
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), newer, "bytes are stored verbatim")
    }

    func testFailedReplaceKeepsLastGoodByteForByte() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")

        XCTAssertThrowsError(try store.replace(with: Data("{\"schema_version\": \"1\"".utf8), etag: "\"v2\""))
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
        XCTAssertEqual(store.readETag(), "\"v1\"", "a rejected body must not advance the ETag")

        let wrongVersion = try JSONEdit.edit(good) { $0["schema_version"] = "99" }
        XCTAssertThrowsError(try store.replace(with: wrongVersion, etag: "\"v3\""))
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
        XCTAssertEqual(store.readETag(), "\"v1\"")
    }

    func testNoTemporaryFilesLeftBehind() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        try store.replace(with: try Repo.fixtureData(), etag: nil)
        try store.replace(with: try Repo.fixtureData(), etag: "\"x\"")
        let names = try FileManager.default.contentsOfDirectory(atPath: dir.path).sorted()
        XCTAssertEqual(names, ["snapshot.v1.etag", "snapshot.v1.json"])
    }

    func testUndecodableDownloadedFileFallsBackToBundled() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try Data("garbage".utf8).write(to: store.snapshotFileURL)
        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertTrue(FileManager.default.fileExists(atPath: store.snapshotFileURL.path), "the bad file is ignored, not deleted")
    }

    func testNilETagRemovesSidecar() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.bundledFixture)
        try store.replace(with: try Repo.fixtureData(), etag: "\"x\"")
        XCTAssertEqual(store.readETag(), "\"x\"")
        try store.replace(with: try Repo.fixtureData(), etag: nil)
        XCTAssertNil(store.readETag())
    }
}
