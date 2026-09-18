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

    func testFavouritesRoundTripThroughTheRealAppModel() async {
        let suiteName = "QueerTVGuideTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let model = AppModel(store: SnapshotStore(directory: try! Self.emptyDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")), favourites: FavouritesStore(defaults: defaults))
        await model.loadInitial()
        guard let show = model.snapshot?.shows.first else { return XCTFail("no shows in bundled snapshot") }
        XCTAssertFalse(model.favourites.isFavourite(.show, id: show.id))
        model.favourites.toggle(.show, id: show.id)
        XCTAssertTrue(model.favourites.isFavourite(.show, id: show.id))
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
