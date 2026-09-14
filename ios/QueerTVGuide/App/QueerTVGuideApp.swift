import SwiftUI

@main
struct QueerTVGuideApp: App {
    @State private var model = AppModel.live()

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environment(model)
                .task {
                    model.loadInitial()
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
