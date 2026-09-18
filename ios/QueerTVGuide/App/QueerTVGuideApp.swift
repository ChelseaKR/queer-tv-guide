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
                    UpNextPublisher.publish(model)
                    await model.refresh()
                    UpNextPublisher.publish(model)
                }
                // The widget's copy of the favorites' next episodes is
                // rewritten as the app leaves the foreground, so a star
                // added or removed anywhere reaches the home screen.
                .onChange(of: scenePhase) { _, phase in
                    if phase != .active { UpNextPublisher.publish(model) }
                }
        }
    }
}

struct RootTabView: View {
    var body: some View {
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
