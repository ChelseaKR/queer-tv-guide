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
    var body: some View {
        TabView {
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }
            FavouritesView()
                .tabItem { Label("Favourites", systemImage: "star") }
            AboutView()
                .tabItem { Label("About", systemImage: "info.circle") }
        }
    }
}
