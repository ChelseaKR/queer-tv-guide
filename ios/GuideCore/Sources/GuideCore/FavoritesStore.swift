import Foundation

/// Favorites live in `UserDefaults` on this device and nowhere else. No
/// iCloud key-value store and no sync. The only copy that can leave the
/// device is a backup file the user exports and sends somewhere themselves
/// (`FavoritesBackup`), and the user's own device backup. The suite is
/// injectable so tests never touch the real defaults.
public final class FavoritesStore: @unchecked Sendable {
    public enum Kind: String, Codable, Sendable {
        case show
        case character
    }

    public struct Entry: Codable, Equatable, Sendable, Identifiable {
        public let kind: Kind
        public let id: String
        public let addedAt: Date
        public var key: String { "\(kind.rawValue):\(id)" }
        public init(kind: Kind, id: String, addedAt: Date) {
            self.kind = kind
            self.id = id
            self.addedAt = addedAt
        }
    }

    // Persisted UserDefaults key: never rename it, or saved favorites vanish on update.
    public static let defaultsKey = "favourites.v1"

    private let defaults: UserDefaults
    private let now: () -> Date
    private let lock = NSLock()
    private var cache: [Entry]

    public init(defaults: UserDefaults = .standard, now: @escaping () -> Date = Date.init) {
        self.defaults = defaults
        self.now = now
        self.cache = Self.read(from: defaults)
    }

    public var entries: [Entry] {
        lock.lock(); defer { lock.unlock() }
        return cache
    }

    public func isFavorite(_ kind: Kind, id: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return cache.contains { $0.kind == kind && $0.id == id }
    }

    /// Returns the new state.
    @discardableResult
    public func toggle(_ kind: Kind, id: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        if let idx = cache.firstIndex(where: { $0.kind == kind && $0.id == id }) {
            cache.remove(at: idx)
            persist()
            return false
        }
        cache.append(Entry(kind: kind, id: id, addedAt: now()))
        persist()
        return true
    }

    public func remove(_ kind: Kind, id: String) {
        lock.lock(); defer { lock.unlock() }
        cache.removeAll { $0.kind == kind && $0.id == id }
        persist()
    }

    /// Adds every entry not already saved, keeping the saved ones as they
    /// are (their `addedAt` included). One write for the whole batch.
    @discardableResult
    public func merge(_ incoming: [Entry]) -> (added: Int, alreadySaved: Int) {
        lock.lock(); defer { lock.unlock() }
        var keys = Set(cache.map(\.key))
        var added = 0
        for entry in incoming where keys.insert(entry.key).inserted {
            cache.append(entry)
            added += 1
        }
        if added > 0 { persist() }
        return (added, incoming.count - added)
    }

    public func removeAll() {
        lock.lock(); defer { lock.unlock() }
        cache.removeAll()
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(cache) {
            defaults.set(data, forKey: Self.defaultsKey)
        }
    }

    private static func read(from defaults: UserDefaults) -> [Entry] {
        guard let data = defaults.data(forKey: defaultsKey),
              let entries = try? JSONDecoder().decode([Entry].self, from: data) else { return [] }
        return entries
    }
}
