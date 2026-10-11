import UIKit
import UserNotifications
import GuideCore

/// The few things SwiftUI's `App` cannot do itself, all about the local
/// episode reminders: a tap on one opens its show, and one that arrives
/// while the app is open still shows as a banner (iOS drops it silently
/// otherwise). The delegate is set at launch, before a cold start from a
/// tap delivers its response. Local notifications only: nothing here
/// registers for push (`SourceTreeGuardTests.testRemindersAreLocalOnly`).
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    let router: AppRouter

    @MainActor
    override init() {
        router = AppRouter()
        super.init()
    }

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard response.actionIdentifier == UNNotificationDefaultActionIdentifier,
              let showID = response.notification.request.content.userInfo[AppLink.reminderShowIDKey] as? String
        else { return }
        await router.open(.show(showID))
    }
}
