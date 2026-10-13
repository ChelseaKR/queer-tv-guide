import Foundation

/// When the app may ask iOS to show its rating prompt (DECISIONS 0017,
/// accepted). iOS decides whether the prompt actually appears and caps it
/// at three times a year; this policy decides when the app is allowed to
/// ask at all, and asks far less often than that:
///
/// - never during the first launch;
/// - only after a good moment: a show opened from Favorites in this launch,
///   or the third launch with at least one favorite saved;
/// - at most once per app version, and at least `minimumInterval` (120
///   days) after the last ask.
///
/// It never asks after a failure, never offers anything for a rating, and
/// never asks how the person feels first (App Review 5.6.1): everyone who
/// reaches a good moment is asked the same way.
///
/// The counters live in `UserDefaults` on this device, under one key, and
/// are never sent anywhere: no identifier, no analytics. The suite and the
/// clock are injectable so tests never touch the real defaults or wait.
public final class ReviewPromptPolicy: @unchecked Sendable {
    public struct State: Codable, Equatable, Sendable {
        /// Launches recorded, this one included.
        public var launches = 0
        /// Launches that began with at least one favorite saved.
        public var launchesWithFavorites = 0
        public var lastAskedAt: Date?
        public var lastAskedVersion: String?

        public init() {}
    }

    // Persisted UserDefaults key: never rename it, or the spacing resets on update.
    public static let defaultsKey = "reviewPrompt.v1"
    /// At least this long between two asks, whatever the version.
    public static let minimumInterval: TimeInterval = 120 * 24 * 60 * 60
    /// Launches with a favorite saved before one counts as a good moment.
    public static let launchesWithFavoritesNeeded = 3

    private let defaults: UserDefaults
    private let now: () -> Date
    private let lock = NSLock()
    private var cached: State
    private var goodMomentThisLaunch = false

    public init(defaults: UserDefaults = .standard, now: @escaping () -> Date = Date.init) {
        self.defaults = defaults
        self.now = now
        self.cached = Self.read(from: defaults)
    }

    public var state: State {
        lock.lock(); defer { lock.unlock() }
        return cached
    }

    /// Call once per launch, once favorites are readable.
    public func recordLaunch(hasFavorites: Bool) {
        lock.lock(); defer { lock.unlock() }
        cached.launches += 1
        if hasFavorites { cached.launchesWithFavorites += 1 }
        goodMomentThisLaunch = false
        persist()
    }

    /// A show was opened from Favorites: the person came back for
    /// something they follow.
    public func recordGoodMoment() {
        lock.lock(); defer { lock.unlock() }
        goodMomentThisLaunch = true
    }

    /// Whether the app may ask now, without spending the ask.
    public func isDue(appVersion: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return due(appVersion: appVersion)
    }

    /// Whether the app may ask now; if so, records the ask, so the next
    /// one waits for a new version and `minimumInterval`. iOS may still
    /// show nothing, and that counts as an ask: the app cannot tell.
    public func takeAskIfDue(appVersion: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard due(appVersion: appVersion) else { return false }
        cached.lastAskedAt = now()
        cached.lastAskedVersion = appVersion
        goodMomentThisLaunch = false
        persist()
        return true
    }

    private func due(appVersion: String) -> Bool {
        guard cached.launches >= 2, !appVersion.isEmpty else { return false }
        if cached.lastAskedVersion == appVersion { return false }
        if let last = cached.lastAskedAt {
            // A clock set back before the last ask is not 120 days later.
            let elapsed = now().timeIntervalSince(last)
            if elapsed < Self.minimumInterval { return false }
        }
        return goodMomentThisLaunch || cached.launchesWithFavorites >= Self.launchesWithFavoritesNeeded
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(cached) {
            defaults.set(data, forKey: Self.defaultsKey)
        }
    }

    private static func read(from defaults: UserDefaults) -> State {
        guard let data = defaults.data(forKey: defaultsKey),
              let state = try? JSONDecoder().decode(State.self, from: data) else { return State() }
        return state
    }
}
