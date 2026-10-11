import Foundation
import Observation
import GuideCore

/// Which tab is showing, and the show or character a link asked for.
///
/// A link (a widget row, a reminder) opens on the Favorites tab with the
/// screen pushed on its stack, so Back returns to Favorites: the place the
/// widget and the reminders come from. A link that arrives before the
/// first-run screen is finished waits until it is.
@Observable
@MainActor
final class AppRouter {
    enum Tab: Hashable {
        case search, favorites, about
    }

    var tab: Tab = .search
    /// What the Favorites stack shows pushed, if anything.
    var favoritesLink: AppLink?

    func open(_ link: AppLink) {
        tab = .favorites
        favoritesLink = link
    }

    /// Opens `url` if it is one of this app's links; anything else is
    /// ignored. Returns whether it was one.
    @discardableResult
    func open(url: URL) -> Bool {
        guard let link = AppLink(url: url) else { return false }
        open(link)
        return true
    }
}
