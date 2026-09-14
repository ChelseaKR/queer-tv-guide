import Foundation
import Observation
import GuideCore

/// The app's one piece of shared state: the current snapshot, how it was
/// loaded, and the one network action (refresh) the whole app can trigger.
/// No accounts, no analytics — this holds exactly the data the UI needs and
/// nothing about who is using it.
@Observable
@MainActor
final class AppModel {
    enum LoadState: Equatable {
        case loading
        case loaded
        /// The bundled snapshot itself failed to load or decode — this
        /// should never happen in a shipped build (it ships inside the
        /// bundle), but the UI states it rather than crashing or showing
        /// an empty screen.
        case failed(String)
    }

    private(set) var snapshot: Snapshot?
    private(set) var loadState: LoadState = .loading
    private(set) var origin: SnapshotStore.Loaded.Origin?
    private(set) var lastRefreshError: String?
    private(set) var isRefreshing = false
    private(set) var searchIndex: SearchIndex?

    let favourites: FavouritesStore
    private let store: SnapshotStore
    private let refresher: SnapshotRefresher

    init(store: SnapshotStore, favourites: FavouritesStore = FavouritesStore()) {
        self.store = store
        self.refresher = SnapshotRefresher(store: store)
        self.favourites = favourites
    }

    /// The bundled snapshot shipped inside the app, matched to
    /// `SnapshotStore.defaultDirectory()` for downloaded replacements.
    static func live() -> AppModel {
        AppModel(store: SnapshotStore(
            directory: SnapshotStore.defaultDirectory(),
            bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")
        ))
    }

    func loadInitial() {
        do {
            apply(try store.load())
        } catch {
            loadState = .failed(error.localizedDescription)
        }
    }

    private func apply(_ loaded: SnapshotStore.Loaded) {
        snapshot = loaded.snapshot
        origin = loaded.origin
        searchIndex = SearchIndex(snapshot: loaded.snapshot)
        loadState = .loaded
    }

    /// One GET, conditional on the stored ETag. On success and a real
    /// change, swaps in the new snapshot. On any failure — offline, a bad
    /// response, a body that fails to decode — the last good snapshot and
    /// its `generated_at` stay exactly as they were; only `lastRefreshError`
    /// changes, so the UI can say a refresh failed without losing data.
    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let outcome = try await refresher.refresh()
            if case .updated = outcome, let loaded = try? store.load() {
                apply(loaded)
            }
            lastRefreshError = nil
        } catch {
            lastRefreshError = error.localizedDescription
        }
    }
}
