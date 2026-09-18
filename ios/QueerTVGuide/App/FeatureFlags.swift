import Foundation

/// Features built but not yet approved to ship. Each is one constant here,
/// OFF by default; a test pins every default, so turning one on is a
/// deliberate, reviewed change.
enum FeatureFlags {
    /// Optional local reminders for favorite shows' next episodes
    /// (Reminders/). OFF pending the owner's decision on whether an app
    /// whose premise is "no telemetry" should ask for notification
    /// permission at all, even for reminders that never leave the device.
    static let episodeRemindersShipped = false

    /// `episodeRemindersShipped`, unless, in Debug builds only, the launch
    /// argument `-feature.episodeReminders YES` or `NO` overrides it so UI
    /// tests can check both states. Release builds read the constant alone.
    static var episodeReminders: Bool {
        #if DEBUG
        // A launch argument arrives as the string "YES" or "NO", which
        // `bool(forKey:)` reads and a cast to Bool does not.
        let key = "feature.episodeReminders"
        if UserDefaults.standard.object(forKey: key) != nil {
            return UserDefaults.standard.bool(forKey: key)
        }
        #endif
        return episodeRemindersShipped
    }
}
