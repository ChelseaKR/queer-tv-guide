import SwiftUI

@main
struct QueerTVGuideApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var model = AppModel.live()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environment(model)
                .environment(appDelegate.router)
                // A widget row's `queerframe://show/<id>` link (AppLink).
                // Anything that is not one of this app's links is ignored.
                .onOpenURL { url in appDelegate.router.open(url: url) }
                // Contrast-checked tint for every link, button and row
                // (Views/Components/AccessibleStyle.swift).
                .tint(.accessibleAccent)
                .task {
                    await model.loadInitial()
                    UpNextPublisher.publish(model)
                    await model.refresh()
                    UpNextPublisher.publish(model)
                    await ReminderScheduler.reschedule(model)
                }
                // The widget's copy of the favorites' next episodes is
                // rewritten as the app leaves the foreground, so a star
                // added or removed anywhere reaches the home screen. Episode
                // reminders (only if the user turned them on) follow the
                // favorites the same way.
                .onChange(of: scenePhase) { _, phase in
                    if phase != .active {
                        UpNextPublisher.publish(model)
                        Task { await ReminderScheduler.reschedule(model) }
                    }
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
        // A hardware keyboard on iPad, and the menu bar on a Mac: the tabs
        // and the one refresh, with the shortcuts the system shows when
        // Command is held (DECISIONS 0016).
        .commands {
            CommandMenu("Go") {
                Button("Search") { appDelegate.router.tab = .search }
                    .keyboardShortcut("1", modifiers: .command)
                Button("Favorites") { appDelegate.router.tab = .favorites }
                    .keyboardShortcut("2", modifiers: .command)
                Button("About") { appDelegate.router.tab = .about }
                    .keyboardShortcut("3", modifiers: .command)
                Divider()
                Button("Check for New Data") { Task { await model.requestedRefresh() } }
                    .keyboardShortcut("r", modifiers: .command)
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
    @Environment(AppModel.self) private var model
    @Environment(AppRouter.self) private var router

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
        @Bindable var router = router
        return TabView(selection: $router.tab) {
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }
                .tag(AppRouter.Tab.search)
            FavoritesView()
                .tabItem { Label("Favorites", systemImage: "star") }
                .tag(AppRouter.Tab.favorites)
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
                .tag(AppRouter.Tab.about)
        }
        // Every scroll view and labeled value in every tab
        // (AccessibleStyle.swift).
        .legibleScrollEdges()
        .labeledContentStyle(SubduedValueLabeledContentStyle())
        .reduceMotionRespected()
        // A refresh the person asked for (pull to refresh, Try again) ends
        // in a tap they can feel: success when the data is current, a
        // warning when the look failed. Once here, not per screen, so one
        // refresh is one tap. iOS skips it when System Haptics is off.
        .sensoryFeedback(trigger: model.requestedRefreshesFinished) { _, _ in
            model.lastRefreshProblem == nil ? .success : .warning
        }
    }
}
