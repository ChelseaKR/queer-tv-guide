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
    /// When the clock was last read for judging the snapshot's age: at
    /// load, after every refresh, and each time the app comes to the
    /// foreground (`QueerTVGuideApp`). A stored property, so every screen
    /// showing the data's age redraws when it moves on.
    private(set) var clockReading: Date

    let favourites: FavouritesStore
    private let store: SnapshotStore
    private let refresher: SnapshotRefresher
    private let now: () -> Date

    init(store: SnapshotStore, favourites: FavouritesStore = FavouritesStore(), now: @escaping () -> Date = Date.init) {
        self.store = store
        self.refresher = SnapshotRefresher(store: store)
        self.favourites = favourites
        self.now = now
        self.clockReading = now()
    }

    /// The bundled snapshot shipped inside the app, matched to
    /// `SnapshotStore.defaultDirectory()` for downloaded replacements.
    static func live() -> AppModel {
        AppModel(
            store: SnapshotStore(
                directory: SnapshotStore.defaultDirectory(),
                bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")
            ),
            now: uiTestClock() ?? Date.init
        )
    }

    /// Debug builds only: a UI test can pin the clock with the launch
    /// argument `-UITestClock <ISO 8601 date>`, to show the app holding data
    /// older than its SLA without waiting two days. A Release build never
    /// reads it.
    private static func uiTestClock() -> (() -> Date)? {
        #if DEBUG
        let formatter = ISO8601DateFormatter()
        if let value = UserDefaults.standard.string(forKey: "UITestClock"),
           let pinned = formatter.date(from: value) {
            return { pinned }
        }
        #endif
        return nil
    }

    // MARK: Data freshness (DG-04)

    func readClock() {
        clockReading = now()
    }

    func freshness(of snapshot: Snapshot) -> DataFreshness {
        DataFreshness.assess(generatedAt: snapshot.generatedAt, now: clockReading)
    }

    /// What a stale or unknown-age snapshot says about itself; nil while
    /// it is current.
    func freshnessWarning(for snapshot: Snapshot) -> Presentation.FreshnessWarning? {
        Presentation.freshnessWarning(generatedAt: snapshot.generatedAt, freshness: freshness(of: snapshot))
    }

    // MARK: Favourites backup (DG-10)

    enum BackupError: Error, LocalizedError {
        case catalogueNotLoaded

        var errorDescription: String? {
            "The catalogue hasn't finished loading, so the backup can't be checked against it yet. Try again in a moment."
        }
    }

    /// Validates `data` as a favourites backup against the loaded snapshot,
    /// adds the favourites that are new, and says what happened to every
    /// entry. Ids the snapshot does not have are skipped, never stored.
    func importFavourites(from data: Data) throws -> String {
        guard let snapshot else { throw BackupError.catalogueNotLoaded }
        let parsed = try FavouritesBackup.parse(data, now: now()) { kind, id in
            switch kind {
            case .show: snapshot.show(id: id) != nil
            case .character: snapshot.character(id: id) != nil
            }
        }
        let merged = favourites.merge(parsed.entries)
        return Presentation.importSummary(
            added: merged.added,
            alreadySaved: merged.alreadySaved,
            notInSnapshot: parsed.notInSnapshot,
            unreadable: parsed.unreadable
        )
    }

    /// Decodes the snapshot (12.5 MB of real LezWatch + TVmaze data) and
    /// builds the search index off the main actor, so launch shows
    /// "Loading catalogue…" instead of a frozen screen.
    func loadInitial() async {
        let store = self.store
        do {
            let (loaded, index) = try await Task.detached(priority: .userInitiated) {
                let loaded = try store.load()
                return (loaded, SearchIndex(snapshot: loaded.snapshot))
            }.value
            apply(loaded.snapshot, origin: loaded.origin, index: index)
        } catch {
            loadState = .failed(error.localizedDescription)
        }
    }

    private func apply(_ snapshot: Snapshot, origin: SnapshotStore.Loaded.Origin, index: SearchIndex) {
        self.snapshot = snapshot
        self.origin = origin
        searchIndex = index
        loadState = .loaded
        readClock()
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
            if case .updated(let fresh) = outcome {
                // The refresher already decoded and stored this snapshot;
                // use it rather than decoding the file a second time, and
                // build the index off the main actor.
                let index = await Task.detached(priority: .userInitiated) {
                    SearchIndex(snapshot: fresh)
                }.value
                apply(fresh, origin: .downloaded, index: index)
            }
            lastRefreshError = nil
        } catch {
            lastRefreshError = error.localizedDescription
        }
        readClock()
    }
}
