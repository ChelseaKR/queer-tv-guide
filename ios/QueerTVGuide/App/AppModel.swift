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
    /// Why the last look for new data failed, in terms a person can act
    /// on; nil after one that worked (new data, or none newer).
    private(set) var lastRefreshProblem: RefreshProblem?
    private(set) var isRefreshing = false
    /// Counts refreshes the person asked for (pull to refresh, Try again)
    /// as they finish, so a view can answer each one with a haptic. Launch
    /// and return-to-foreground refreshes do not count: nobody is waiting
    /// on those.
    private(set) var requestedRefreshesFinished = 0
    private(set) var searchIndex: SearchIndex?
    /// When the clock was last read for judging the snapshot's age: at
    /// load, after every refresh, and each time the app comes to the
    /// foreground (`QueerTVGuideApp`). A stored property, so every screen
    /// showing the data's age redraws when it moves on.
    private(set) var clockReading: Date

    let favorites: FavoritesStore
    private let store: SnapshotStore
    private let refresher: SnapshotRefresher
    private let now: () -> Date
    /// When the app last looked for new data, and whether coming back to it
    /// should (`ForegroundRefreshGate`). In memory only.
    private var refreshGate = ForegroundRefreshGate()

    init(store: SnapshotStore, favorites: FavoritesStore = FavoritesStore(), now: @escaping () -> Date = Date.init) {
        self.store = store
        self.refresher = SnapshotRefresher(store: store)
        self.favorites = favorites
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

    #if DEBUG
    private static func uiTestRefreshProblem() -> RefreshProblem? {
        switch UserDefaults.standard.string(forKey: "UITestRefreshProblem") {
        case "offline": .offline
        case "unreachable": .unreachable
        case "unusable": .unusable
        default: nil
        }
    }
    #endif

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

    // MARK: Favorites backup (DG-10)

    enum BackupError: Error, LocalizedError {
        case catalogNotLoaded

        var errorDescription: String? {
            "The catalog hasn't finished loading, so the backup can't be checked against it yet. Try again in a moment."
        }
    }

    /// Validates `data` as a favorites backup against the loaded snapshot,
    /// adds the favorites that are new, and says what happened to every
    /// entry. Ids the snapshot does not have are skipped, never stored.
    func importFavorites(from data: Data) throws -> String {
        guard let snapshot else { throw BackupError.catalogNotLoaded }
        let parsed = try FavoritesBackup.parse(data, now: now()) { kind, id in
            switch kind {
            case .show: snapshot.show(id: id) != nil
            case .character: snapshot.character(id: id) != nil
            }
        }
        let merged = favorites.merge(parsed.entries)
        return Presentation.importSummary(
            added: merged.added,
            alreadySaved: merged.alreadySaved,
            notInSnapshot: parsed.notInSnapshot,
            unreadable: parsed.unreadable
        )
    }

    /// Decodes the snapshot (12.5 MB of real LezWatch + TVmaze data) and
    /// builds the search index off the main actor, so launch shows
    /// "Loading catalog…" instead of a frozen screen.
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

    /// The app has come back to the foreground: re-reads the clock, and if
    /// the snapshot on hand is more than `ForegroundRefreshGate.staleAfter`
    /// old (and no look was made in the last `minimumInterval`) looks for new
    /// data, the same single GET as `refresh()`. Called from a background
    /// task, so nothing waits on it; offline or a bad response leaves the
    /// snapshot as it was and shows no alert, only the footer's line.
    func refreshIfStaleOnReturn() async {
        readClock()
        guard let snapshot, refreshGate.shouldRefresh(generatedAt: snapshot.generatedAt, now: clockReading) else { return }
        await refresh()
    }

    /// A refresh the person asked for: the same one GET, then a count that
    /// views watch for a success or warning haptic.
    func requestedRefresh() async {
        await refresh()
        requestedRefreshesFinished += 1
    }

    /// One GET, conditional on the stored ETag. On success and a real
    /// change, swaps in the new snapshot. On any failure — offline, a bad
    /// response, a body that fails to decode — the last good snapshot and
    /// its `generated_at` stay exactly as they were; only `lastRefreshProblem`
    /// changes, so the UI can say a refresh failed without losing data.
    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        refreshGate.recordAttempt(at: now())
        #if DEBUG
        // UI tests only: `-UITestRefreshProblem offline|unreachable|unusable`
        // makes every look fail that way without touching the network, so
        // the footer's words and Try again can be tested and shown. A
        // Release build never reads it.
        if let forced = Self.uiTestRefreshProblem() {
            lastRefreshProblem = forced
            readClock()
            return
        }
        #endif
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
            lastRefreshProblem = nil
        } catch {
            lastRefreshProblem = RefreshProblem(error)
        }
        readClock()
    }
}
