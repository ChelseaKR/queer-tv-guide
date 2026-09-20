import Foundation
import GuideCore
import WidgetKit

/// Hands the home-screen widget what it shows: the next episode of each
/// favorite show, as one small file in the App Group container the app and
/// the widget share (`UpNext`). The widget reads only that file; it makes no
/// network request and never sees the snapshot, so it cannot show anything
/// the file does not carry, and the file carries no death data.
///
/// Everything stays on this device. Nothing here is sent anywhere.
@MainActor
enum UpNextPublisher {
    /// Writes the file when its contents changed and asks WidgetKit to
    /// redraw the widget. Called after the snapshot loads or refreshes and
    /// whenever the app leaves the foreground, which covers every way the
    /// favorites can change while the app is open.
    ///
    /// `directory` is the App Group container; tests pass their own. With
    /// no container (a build without the App Group entitlement, such as an
    /// unsigned simulator build) there is nowhere to write, and nothing
    /// happens. Returns whether the file changed.
    @discardableResult
    static func publish(_ model: AppModel, to directory: URL? = appGroupDirectory) -> Bool {
        guard let snapshot = model.snapshot, let directory else { return false }
        let showIDs = model.favourites.entries
            .filter { $0.kind == .show }
            .sorted { $0.addedAt > $1.addedAt }
            .map(\.id)
        let upNext = UpNext(favoriteShowIDs: showIDs, snapshot: snapshot)
        let changed = (try? UpNextStore(directory: directory).write(upNext)) ?? false
        if changed {
            WidgetCenter.shared.reloadTimelines(ofKind: UpNext.widgetKind)
        }
        return changed
    }

    static var appGroupDirectory: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: UpNext.appGroupIdentifier)
    }
}
