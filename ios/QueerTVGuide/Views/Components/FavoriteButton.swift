import SwiftUI
import GuideCore

/// Favorites are local-only (`UserDefaults`, no sync, no account) — this is
/// the one control that changes them.
struct FavoriteButton: View {
    let kind: FavoritesStore.Kind
    let id: String

    @Environment(AppModel.self) private var model
    @State private var isFavorite = false
    /// Counts taps, so the haptic answers a tap and not the state read on
    /// appear.
    @State private var taps = 0

    var body: some View {
        Button {
            isFavorite = model.favorites.toggle(kind, id: id)
            taps += 1
        } label: {
            Image(systemName: isFavorite ? "star.fill" : "star")
        }
        .accessibilityLabel(isFavorite ? "Remove from favorites" : "Add to favorites")
        .sensoryFeedback(.selection, trigger: taps)
        .onAppear { isFavorite = model.favorites.isFavorite(kind, id: id) }
    }
}
