import Foundation
import XCTest
@testable import GuideCore

/// When the app may ask for a rating: never at first launch, only after a
/// good moment, once per version, 120 days apart. Every test runs on its
/// own defaults suite and a clock it moves by hand.
final class ReviewPromptPolicyTests: XCTestCase {
    private var suiteName = ""
    private var defaults: UserDefaults!
    private var clock = Date(timeIntervalSince1970: 1_790_000_000)
    private let day: TimeInterval = 24 * 60 * 60

    override func setUpWithError() throws {
        suiteName = "ReviewPromptPolicyTests-\(UUID().uuidString)"
        defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
    }

    /// A fresh process: what the app builds at each launch.
    private func launch(hasFavorites: Bool = false) -> ReviewPromptPolicy {
        let policy = ReviewPromptPolicy(defaults: defaults, now: { [unowned self] in self.clock })
        policy.recordLaunch(hasFavorites: hasFavorites)
        return policy
    }

    func testNeverDuringTheFirstLaunchEvenAfterAGoodMoment() {
        let policy = launch(hasFavorites: true)
        policy.recordGoodMoment()
        XCTAssertFalse(policy.isDue(appVersion: "1.1.0"))
        XCTAssertFalse(policy.takeAskIfDue(appVersion: "1.1.0"))
        XCTAssertNil(policy.state.lastAskedAt, "a refused ask must not be recorded")
    }

    func testAGoodMomentOnTheSecondLaunchIsEnough() {
        _ = launch()
        let policy = launch()
        XCTAssertFalse(policy.isDue(appVersion: "1.1.0"), "no good moment yet")
        policy.recordGoodMoment()
        XCTAssertTrue(policy.isDue(appVersion: "1.1.0"))
    }

    func testTheThirdLaunchWithAFavoriteIsAGoodMoment() {
        _ = launch(hasFavorites: true)
        _ = launch(hasFavorites: false)
        XCTAssertFalse(launch(hasFavorites: true).isDue(appVersion: "1.1.0"), "two launches with a favorite")
        XCTAssertTrue(launch(hasFavorites: true).isDue(appVersion: "1.1.0"), "the third launch with a favorite")
        XCTAssertEqual(ReviewPromptPolicy.launchesWithFavoritesNeeded, 3)
    }

    func testAGoodMomentDoesNotCarryIntoTheNextLaunch() {
        _ = launch()
        launch().recordGoodMoment()
        XCTAssertFalse(launch().isDue(appVersion: "1.1.0"))
    }

    func testTakingTheAskRecordsItAndSpendsTheGoodMoment() {
        _ = launch()
        let policy = launch()
        policy.recordGoodMoment()
        XCTAssertTrue(policy.takeAskIfDue(appVersion: "1.1.0"))
        XCTAssertEqual(policy.state.lastAskedAt, clock)
        XCTAssertEqual(policy.state.lastAskedVersion, "1.1.0")
        clock += 365 * day
        policy.recordGoodMoment()
        XCTAssertFalse(policy.takeAskIfDue(appVersion: "1.1.0"), "asked twice in one version")
    }

    func testOncePerVersionAndAtLeast120DaysApart() {
        _ = launch()
        var policy = launch()
        policy.recordGoodMoment()
        XCTAssertTrue(policy.takeAskIfDue(appVersion: "1.1.0"))

        // A new version, but too soon.
        clock += 119 * day
        policy = launch()
        policy.recordGoodMoment()
        XCTAssertFalse(policy.isDue(appVersion: "1.2.0"), "119 days after the last ask")

        // 120 days to the second: allowed.
        clock += day
        XCTAssertEqual(ReviewPromptPolicy.minimumInterval, 120 * day)
        XCTAssertTrue(policy.isDue(appVersion: "1.2.0"), "120 days after the last ask")

        // The same version as the last ask, however long after: never.
        clock += 1000 * day
        XCTAssertFalse(policy.isDue(appVersion: "1.1.0"))
    }

    func testAClockSetBackIsNotTimePassing() {
        _ = launch()
        let policy = launch()
        policy.recordGoodMoment()
        XCTAssertTrue(policy.takeAskIfDue(appVersion: "1.1.0"))
        clock -= 400 * day
        policy.recordGoodMoment()
        XCTAssertFalse(policy.isDue(appVersion: "1.2.0"))
    }

    func testAnUnknownVersionNeverAsks() {
        _ = launch()
        let policy = launch(hasFavorites: true)
        policy.recordGoodMoment()
        XCTAssertFalse(policy.isDue(appVersion: ""))
    }

    /// The state survives relaunch under its one key, and holds counts,
    /// a date and a version string: nothing that identifies anyone.
    func testStateIsLocalCountsUnderOneKey() throws {
        _ = launch(hasFavorites: true)
        let policy = launch()
        policy.recordGoodMoment()
        XCTAssertTrue(policy.takeAskIfDue(appVersion: "1.1.0"))

        let reread = ReviewPromptPolicy(defaults: defaults, now: { [unowned self] in self.clock })
        XCTAssertEqual(reread.state.launches, 2)
        XCTAssertEqual(reread.state.launchesWithFavorites, 1)
        XCTAssertEqual(reread.state.lastAskedVersion, "1.1.0")

        XCTAssertEqual(ReviewPromptPolicy.defaultsKey, "reviewPrompt.v1")
        let stored = try XCTUnwrap(defaults.data(forKey: ReviewPromptPolicy.defaultsKey))
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: stored) as? [String: Any])
        XCTAssertEqual(Set(object.keys), ["launches", "launchesWithFavorites", "lastAskedAt", "lastAskedVersion"])
        let keys = defaults.persistentDomain(forName: suiteName)?.keys.map { $0 } ?? []
        XCTAssertEqual(keys, [ReviewPromptPolicy.defaultsKey])
    }

    func testUnreadableStoredStateStartsOver() {
        defaults.set(Data("not json".utf8), forKey: ReviewPromptPolicy.defaultsKey)
        let policy = launch()
        XCTAssertEqual(policy.state.launches, 1)
        policy.recordGoodMoment()
        XCTAssertFalse(policy.isDue(appVersion: "1.1.0"), "a reset counts as a first launch")
    }
}
