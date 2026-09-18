import XCTest
import GuideCore
@testable import QueerTVGuide

/// The app's side of the widget: what it writes, from the real app model and
/// the real bundled snapshot, into the directory the widget reads.
@MainActor
final class UpNextPublisherTests: XCTestCase {
    private func temporaryDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("UpNextPublisherTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    func testPublishWritesFavoriteShowsNewestFirstAndOnlyWhenChanged() async throws {
        let suiteName = "UpNextPublisherTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defer { defaults.removePersistentDomain(forName: suiteName) }
        var clock = Date(timeIntervalSince1970: 1_800_000_000)
        let favorites = FavouritesStore(defaults: defaults, now: { clock })
        let model = AppModel(
            store: SnapshotStore(directory: try temporaryDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")),
            favourites: favorites
        )
        await model.loadInitial()
        let snapshot = try XCTUnwrap(model.snapshot)
        let directory = try temporaryDirectory()
        let store = UpNextStore(directory: directory)

        XCTAssertTrue(UpNextPublisher.publish(model, to: directory), "the first write is a change")
        XCTAssertEqual(store.read()?.items, [], "no favorites yet")

        let first = snapshot.shows[0], second = snapshot.shows[1]
        favorites.toggle(.show, id: first.id)
        clock += 60
        favorites.toggle(.show, id: second.id)
        favorites.toggle(.character, id: snapshot.characters[0].id)
        XCTAssertTrue(UpNextPublisher.publish(model, to: directory))
        let written = try XCTUnwrap(store.read())
        XCTAssertEqual(written.items.map(\.showID), [second.id, first.id], "shows only, newest first")
        XCTAssertEqual(written.snapshotGeneratedAt, snapshot.generatedAt)

        XCTAssertFalse(UpNextPublisher.publish(model, to: directory), "nothing changed, so nothing is rewritten")
    }

    /// Without the App Group (an unsigned build), publishing is a no-op, not
    /// a crash or a write somewhere else.
    func testNoContainerMeansNoWrite() async throws {
        let model = AppModel(store: SnapshotStore(directory: try temporaryDirectory(), bundledURL: Bundle.main.url(forResource: "snapshot.v1", withExtension: "json")))
        await model.loadInitial()
        XCTAssertFalse(UpNextPublisher.publish(model, to: nil))
        print("UpNextPublisherTests: App Group container in this build: \(UpNextPublisher.appGroupDirectory?.path ?? "none (unsigned build)")")
    }
}
