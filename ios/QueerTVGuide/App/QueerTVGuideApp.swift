import SwiftUI

@main
struct QueerTVGuideApp: App {
    @State private var model = AppModel.live()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environment(model)
                // Contrast-checked tint for every link, button and row
                // (Views/Components/AccessibleStyle.swift).
                .tint(.accessibleAccent)
                .task {
                    await model.loadInitial()
                    await model.refresh()
                }
                // An app left in the background for days comes back with
                // its data's age re-read, so a snapshot that went stale
                // meanwhile says so (DG-04), and, when that data is more than
                // ForegroundRefreshGate.staleAfter old, looks for new data
                // once in the background: the same single GET as at launch.
                .onChange(of: scenePhase) { _, phase in
                    if phase == .active { Task { await model.refreshIfStaleOnReturn() } }
                }
        }
    }
}

struct RootTabView: View {
    /// The first-run screen shows until it is finished or skipped once.
    /// Read once at launch and then held here, so a launch argument that
    /// sets the key (UI tests) decides the start without pinning it.
    @State private var onboardingSeen = UserDefaults.standard.bool(forKey: OnboardingView.seenKey)
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if onboardingSeen {
            tabs
        } else {
            // The catalog loads behind it (QueerTVGuideApp's task), so
            // Search is ready when the reader is.
            OnboardingView(finish: {
                UserDefaults.standard.set(true, forKey: OnboardingView.seenKey)
                withAnimation(reduceMotion ? nil : .default) { onboardingSeen = true }
            })
        }
    }

    private var tabs: some View {
        TabView {
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }
            FavoritesView()
                .tabItem { Label("Favorites", systemImage: "star") }
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
        }
        // Every scroll view and labeled value in every tab
        // (AccessibleStyle.swift).
        .legibleScrollEdges()
        .labeledContentStyle(SubduedValueLabeledContentStyle())
        .reduceMotionRespected()
    }
}
