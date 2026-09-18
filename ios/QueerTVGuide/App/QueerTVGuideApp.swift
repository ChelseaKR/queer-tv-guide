import SwiftUI

@main
struct QueerTVGuideApp: App {
    @State private var model = AppModel.live()

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
            // The catalogue loads behind it (QueerTVGuideApp's task), so
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
            FavouritesView()
                .tabItem { Label("Favourites", systemImage: "star") }
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
        }
        // Every scroll view and labelled value in every tab
        // (AccessibleStyle.swift).
        .legibleScrollEdges()
        .labeledContentStyle(SubduedValueLabeledContentStyle())
    }
}
