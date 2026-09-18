import Foundation

/// Features that ship behind a switch. Each is one constant here; a test
/// pins every default, so changing one is a deliberate, reviewed change.
enum FeatureFlags {
    /// Optional local reminders for favorite shows' next episodes
    /// (Reminders/). ON: the owner decided on 2026-09-18 that the app should
    /// have them. The feature is there for everyone; each person still turns
    /// reminders on themselves, and only then is notification permission
    /// asked for, never at launch. Revert this one line to hide it again.
    static let episodeRemindersShipped = true

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
