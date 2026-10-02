import Foundation
import GuideCore
import UserNotifications

/// Sets the optional episode reminders with the system's local notification
/// scheduler. Local only: iOS delivers them from this device, and no server,
/// push token or account is involved, so "Data Not Collected" stays true.
///
/// Does nothing at all, not even a permission check, unless
/// `FeatureFlags.episodeReminders` is on and the user turned reminders on.
@MainActor
enum ReminderScheduler {
    /// The user's choice. Off until they turn it on and allow notifications.
    static let enabledKey = "reminders.v1.enabled"

    static var isEnabled: Bool {
        get { FeatureFlags.episodeReminders && UserDefaults.standard.bool(forKey: enabledKey) }
        set { UserDefaults.standard.set(newValue, forKey: enabledKey) }
    }

    /// Asks for permission (the system prompt, once), then schedules.
    /// Returns whether reminders are on afterwards.
    static func enable(_ model: AppModel) async -> Bool {
        guard FeatureFlags.episodeReminders else { return false }
        let center = UNUserNotificationCenter.current()
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
        isEnabled = granted
        if granted { await reschedule(model) }
        return granted
    }

    static func disable() async {
        isEnabled = false
        await removeOurs()
    }

    /// Replaces this app's pending reminders with the current plan. Called
    /// after the snapshot loads or refreshes and when the app leaves the
    /// foreground, so starring or unstarring a show is reflected.
    static func reschedule(_ model: AppModel) async {
        guard isEnabled, let snapshot = model.snapshot else { return }
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else { return }
        await removeOurs()
        let showIDs = model.favourites.entries.filter { $0.kind == .show }.map(\.id)
        for reminder in EpisodeReminders.plan(favoriteShowIDs: showIDs, snapshot: snapshot, now: Date()) {
            let content = UNMutableNotificationContent()
            content.title = reminder.title
            content.body = reminder.body
            content.sound = .default
            let when = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute, .second], from: reminder.fireDate)
            let trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: false)
            try? await center.add(UNNotificationRequest(identifier: reminder.identifier, content: content, trigger: trigger))
        }
    }

    /// Removes only this app's episode reminders.
    static func removeOurs() async {
        let center = UNUserNotificationCenter.current()
        let ours = await center.pendingNotificationRequests()
            .map(\.identifier)
            .filter { $0.hasPrefix(EpisodeReminders.identifierPrefix) }
        center.removePendingNotificationRequests(withIdentifiers: ours)
    }

    /// Whether the system has notifications turned off for this app, so the
    /// screen can say so and point to Settings.
    static func isDeniedInSettings() async -> Bool {
        await UNUserNotificationCenter.current().notificationSettings().authorizationStatus == .denied
    }
}
