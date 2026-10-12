import StoreKit
import SwiftUI
import GuideCore

/// Asks iOS for its rating prompt when `ReviewPromptPolicy` says the moment
/// is right. The one file allowed to import StoreKit (DECISIONS 0017,
/// proposed), and only for SwiftUI's `requestReview` action: iOS draws the
/// prompt, decides whether it appears at all, and sends any rating to the
/// App Store itself. The app learns nothing, not even whether the prompt
/// showed. No purchase, product or receipt API is used anywhere
/// (`SourceTreeGuardTests`, `scripts/check_app_store.py`).
struct AsksForReviewWhenDue: ViewModifier {
    @Environment(AppModel.self) private var model
    @Environment(\.requestReview) private var requestReview

    func body(content: Content) -> some View {
        content.task {
            // Let the screen settle (the way back from a show), and ask
            // nothing if the person has already moved on.
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled, Self.enabled,
                  model.reviewPrompt.takeAskIfDue(appVersion: Self.appVersion) else { return }
            requestReview()
        }
    }

    private static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
    }

    /// Debug builds only: UI tests turn the prompt off with the launch
    /// argument `-reviewPrompt.uiTestOff YES`, because a development build
    /// shows it every time it is asked. A Release build never reads it.
    static let uiTestOffKey = "reviewPrompt.uiTestOff"

    private static var enabled: Bool {
        #if DEBUG
        return !UserDefaults.standard.bool(forKey: uiTestOffKey)
        #else
        return true
        #endif
    }
}

extension View {
    /// Ask for a rating here, if this is a good moment (`ReviewPromptPolicy`).
    func asksForReviewWhenDue() -> some View {
        modifier(AsksForReviewWhenDue())
    }
}
