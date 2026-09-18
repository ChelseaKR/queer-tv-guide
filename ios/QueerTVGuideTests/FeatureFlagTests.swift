import XCTest
@testable import QueerTVGuide

/// Built-but-unapproved features ship off. Turning one on changes this test
/// in the same diff, so it cannot happen by accident.
@MainActor
final class FeatureFlagTests: XCTestCase {
    func testEpisodeRemindersShipOff() {
        XCTAssertFalse(FeatureFlags.episodeRemindersShipped, "episode reminders need the owner's decision before they ship")
    }

    /// With the flag off (and no Debug override), the user's stored choice
    /// cannot turn reminders on, so nothing ever asks for permission.
    func testTheFlagGatesTheStoredChoice() {
        let defaults = UserDefaults.standard
        let previous = defaults.object(forKey: ReminderScheduler.enabledKey)
        defer { defaults.set(previous, forKey: ReminderScheduler.enabledKey) }
        defaults.set(true, forKey: ReminderScheduler.enabledKey)
        XCTAssertEqual(ReminderScheduler.isEnabled, FeatureFlags.episodeReminders)
        if !FeatureFlags.episodeReminders {
            XCTAssertFalse(ReminderScheduler.isEnabled)
        }
    }
}
