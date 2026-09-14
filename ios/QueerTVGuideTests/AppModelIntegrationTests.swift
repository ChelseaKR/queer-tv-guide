import XCTest
import GuideCore
@testable import QueerTVGuide

/// Unlike `GuideCoreTests` (which decodes the fixture file directly off
/// disk), this exercises the real path the shipped app uses: the fixture
/// bundled as an app resource, found via `Bundle.main`, on the actual host
/// app process. It fails if the resource is ever dropped from the target's
/// build phase, which a pure package test cannot catch.
@MainActor
final class AppModelIntegrationTests: XCTestCase {
    func testBundledSnapshotIsReachableFromTheAppBundle() {
        XCTAssertNotNil(
            Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"),
            "snapshot.v1.json must be a resource of the app bundle"
        )
    }

    func testAppModelLoadsTheBundledSnapshotOnFirstLaunch() {
        let model = AppModel.live()
        model.loadInitial()
        XCTAssertEqual(model.loadState, .loaded)
        XCTAssertEqual(model.origin, .bundled)
        XCTAssertNotNil(model.snapshot)
        XCTAssertGreaterThan(model.snapshot?.shows.count ?? 0, 0)
        XCTAssertNotNil(model.searchIndex)
    }

    func testPrivacyManifestShipsInTheAppBundle() {
        XCTAssertNotNil(
            Bundle.main.url(forResource: "PrivacyInfo", withExtension: "xcprivacy"),
            "PrivacyInfo.xcprivacy must be a resource of the app bundle"
        )
    }

    func testFavouritesRoundTripThroughTheRealAppModel() {
        let suiteName = "QueerTVGuideTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let model = AppModel(store: SnapshotStore(directory: SnapshotStore.defaultDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")), favourites: FavouritesStore(defaults: defaults))
        model.loadInitial()
        guard let show = model.snapshot?.shows.first else { return XCTFail("no shows in bundled snapshot") }
        XCTAssertFalse(model.favourites.isFavourite(.show, id: show.id))
        model.favourites.toggle(.show, id: show.id)
        XCTAssertTrue(model.favourites.isFavourite(.show, id: show.id))
    }
}
