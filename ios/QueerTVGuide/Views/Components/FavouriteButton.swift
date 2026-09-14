import SwiftUI
import GuideCore

/// Favourites are local-only (`UserDefaults`, no sync, no account) — this is
/// the one control that changes them.
struct FavouriteButton: View {
    let kind: FavouritesStore.Kind
    let id: String

    @Environment(AppModel.self) private var model
    @State private var isFavourite = false

    var body: some View {
        Button {
            isFavourite = model.favourites.toggle(kind, id: id)
        } label: {
            Image(systemName: isFavourite ? "star.fill" : "star")
        }
        .accessibilityLabel(isFavourite ? "Remove from favourites" : "Add to favourites")
        .onAppear { isFavourite = model.favourites.isFavourite(kind, id: id) }
    }
}
