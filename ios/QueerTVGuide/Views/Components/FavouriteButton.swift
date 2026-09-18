import SwiftUI
import GuideCore

/// Favourites are local-only (`UserDefaults`, no sync, no account) — this is
/// the one control that changes them.
struct FavouriteButton: View {
    let kind: FavouritesStore.Kind
    let id: String

    @Environment(AppModel.self) private var model
    @State private var isFavourite = false
    /// Counts taps, so the haptic answers a tap and not the state read on
    /// appear.
    @State private var taps = 0

    var body: some View {
        Button {
            isFavourite = model.favourites.toggle(kind, id: id)
            taps += 1
        } label: {
            Image(systemName: isFavourite ? "star.fill" : "star")
        }
        .accessibilityLabel(isFavourite ? "Remove from favourites" : "Add to favourites")
        .sensoryFeedback(.selection, trigger: taps)
        .onAppear { isFavourite = model.favourites.isFavourite(kind, id: id) }
    }
}
