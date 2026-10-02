import XCTest
@testable import QueerTVGuide

/// Every feature flag's shipped value is pinned here. Changing one changes
/// this test in the same diff, so it cannot happen by accident.
@MainActor
final class FeatureFlagTests: XCTestCase {
    /// The owner decided on 2026-09-18 that reminders ship.
    func testEpisodeRemindersShipOn() {
        XCTAssertTrue(FeatureFlags.episodeRemindersShipped)
    }

    /// Shipping the feature turns nothing on by itself: until a person turns
    /// reminders on, none is set and permission is never asked for.
    func testRemindersStayOffUntilAPersonTurnsThemOn() {
        let defaults = UserDefaults.standard
        let previous = defaults.object(forKey: ReminderScheduler.enabledKey)
        defer { defaults.set(previous, forKey: ReminderScheduler.enabledKey) }
        defaults.removeObject(forKey: ReminderScheduler.enabledKey)
        XCTAssertFalse(ReminderScheduler.isEnabled)
    }

    /// The flag gates the stored choice: with it off (as a revert of the
    /// default-on commit would leave it), a stored "on" cannot set reminders.
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
