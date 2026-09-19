import XCTest
import GuideCore
@testable import QueerTVGuide

/// Unlike `GuideCoreTests` (which read files directly off disk), this
/// exercises the real path the shipped app uses: the snapshot bundled as an
/// app resource, found via `Bundle.main`, on the actual host app process. It
/// fails if the resource is ever dropped from the target's build phase, or if
/// what ships is not real published data, which a pure package test cannot
/// catch.
@MainActor
final class AppModelIntegrationTests: XCTestCase {
    func testBundledSnapshotIsReachableFromTheAppBundle() {
        XCTAssertNotNil(
            Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"),
            "snapshot.v1.json must be a resource of the app bundle"
        )
    }

    /// The copy inside the built app, not just the file in the repo, is a
    /// real pipeline-published snapshot: never the hand-made fixture.
    func testTheAppBundleShipsRealPublishedDataNotTheFixture() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"))
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let build = try XCTUnwrap(root["build"] as? [String: Any])
        let version = try XCTUnwrap(build["pipeline_version"] as? String)
        XCTAssertFalse(version.localizedCaseInsensitiveContains("fixture"), "the app bundle ships the fixture (\(version))")
        let run = try XCTUnwrap(build["run"] as? [String: Any])
        XCTAssertNotNil(run["workflow_run_id"] as? String, "the bundled snapshot was not published by the nightly workflow")
    }

    func testAppModelLoadsTheBundledSnapshotOnFirstLaunch() async {
        let model = AppModel(store: SnapshotStore(directory: try! Self.emptyDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")))
        await model.loadInitial()
        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertEqual(model.origin, .bundled)
        XCTAssertNotNil(model.snapshot)
        XCTAssertGreaterThan(model.snapshot?.shows.count ?? 0, 1_000)
        XCTAssertNotNil(model.searchIndex)
    }

    func testPrivacyManifestShipsInTheAppBundle() {
        XCTAssertNotNil(
            Bundle.main.url(forResource: "PrivacyInfo", withExtension: "xcprivacy"),
            "PrivacyInfo.xcprivacy must be a resource of the app bundle"
        )
    }

    func testFavoritesRoundTripThroughTheRealAppModel() async {
        let suiteName = "QueerTVGuideTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let model = AppModel(store: SnapshotStore(directory: try! Self.emptyDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")), favorites: FavoritesStore(defaults: defaults))
        await model.loadInitial()
        guard let show = model.snapshot?.shows.first else { return XCTFail("no shows in bundled snapshot") }
        XCTAssertFalse(model.favorites.isFavorite(.show, id: show.id))
        model.favorites.toggle(.show, id: show.id)
        XCTAssertTrue(model.favorites.isFavorite(.show, id: show.id))
    }

    /// Import through the model the app uses, checked against the real
    /// bundled snapshot: a real show is added, an id the snapshot does not
    /// have is skipped and counted, and nothing else is stored.
    func testImportThroughTheRealAppModelSkipsIdsNotInTheSnapshot() async throws {
        let suiteName = "QueerTVGuideTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let model = AppModel(store: SnapshotStore(directory: try Self.emptyDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")), favorites: FavoritesStore(defaults: defaults))

        XCTAssertThrowsError(try model.importFavorites(from: Data()), "import before the catalog loads must refuse, not guess")
        await model.loadInitial()
        let show = try XCTUnwrap(model.snapshot?.shows.first)
        let unknown = "lwtv:show:999999999"
        XCTAssertNil(model.snapshot?.show(id: unknown), "the unknown id must really be unknown")
        let file = try FavoritesBackup.export([
            FavoritesStore.Entry(kind: .show, id: show.id, addedAt: Date(timeIntervalSince1970: 1_789_724_682)),
            FavoritesStore.Entry(kind: .show, id: unknown, addedAt: Date(timeIntervalSince1970: 1_789_724_682)),
        ])

        let summary = try model.importFavorites(from: file)
        XCTAssertEqual(summary, "Added 1 favorite. 1 is not in this snapshot and was skipped.")
        XCTAssertEqual(model.favorites.entries.map(\.id), [show.id])
        XCTAssertEqual(try model.importFavorites(from: file), "No new favorites were added. 1 was already saved. 1 is not in this snapshot and was skipped.")
    }

    /// The model judges the loaded snapshot's age by its own clock, read at
    /// load and again whenever `readClock()` runs (the app does that each
    /// time it comes to the foreground).
    func testTheModelWarnsOnceTheBundledSnapshotIsPastItsSLA() async throws {
        let bundled = try XCTUnwrap(Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"))
        let generatedAt = try SnapshotDecoder().decode(Data(contentsOf: bundled)).generatedAt
        var clock = generatedAt.addingTimeInterval(60 * 60)
        let model = AppModel(store: SnapshotStore(directory: try Self.emptyDirectory(), bundledURL: bundled), now: { clock })
        await model.loadInitial()
        let snapshot = try XCTUnwrap(model.snapshot)
        XCTAssertNil(model.freshnessWarning(for: snapshot), "an hour-old snapshot is current")

        clock = generatedAt.addingTimeInterval(49 * 60 * 60)
        XCTAssertNil(model.freshnessWarning(for: snapshot), "the clock is only read when asked to")
        model.readClock()
        XCTAssertEqual(model.freshnessWarning(for: snapshot)?.title, "This data is out of date")
    }

    /// A fresh directory per test, so a snapshot some earlier run downloaded
    /// into Application Support can never stand in for the bundled one.
    private static func emptyDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("AppModelIntegrationTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}
