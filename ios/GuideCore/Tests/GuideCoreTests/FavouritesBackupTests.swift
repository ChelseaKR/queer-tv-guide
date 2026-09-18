import XCTest
@testable import GuideCore

/// DG-10: the favourites backup is documented and tested, not assumed. The
/// round trip goes through a real file, the way a user's export does.
final class FavouritesBackupTests: XCTestCase {
    private var suites: [String] = []
    private let now = Date(timeIntervalSince1970: 1_790_000_000)

    override func tearDown() {
        for name in suites { UserDefaults(suiteName: name)?.removePersistentDomain(forName: name) }
        suites = []
        super.tearDown()
    }

    private func freshStore(now: Date? = nil) -> FavouritesStore {
        let name = "GuideCoreTests.backup.\(UUID().uuidString)"
        suites.append(name)
        let clock = now ?? self.now
        return FavouritesStore(defaults: UserDefaults(suiteName: name)!, now: { clock })
    }

    private func isKnown(in snapshot: Snapshot) -> (FavouritesStore.Kind, String) -> Bool {
        { kind, id in kind == .show ? snapshot.show(id: id) != nil : snapshot.character(id: id) != nil }
    }

    private func json(_ object: Any) throws -> Data {
        try JSONSerialization.data(withJSONObject: object)
    }

    // MARK: Round trip

    func testRoundTripThroughAFileRestoresEveryFavourite() throws {
        let snapshot = try Repo.fixture()
        var tick = now.addingTimeInterval(-3_600)
        let original = freshStore()
        let saving = FavouritesStore(defaults: UserDefaults(suiteName: suites[0])!, now: {
            tick = tick.addingTimeInterval(60)
            return tick
        })
        saving.toggle(.show, id: snapshot.shows[0].id)
        saving.toggle(.character, id: snapshot.characters[1].id)
        saving.toggle(.show, id: snapshot.shows[2].id)
        let saved = saving.entries
        XCTAssertEqual(saved.count, 3)
        XCTAssertEqual(Set(saved.map(\.addedAt)).count, 3, "each favourite has its own date to carry across")
        XCTAssertEqual(original.entries, [], "a store reads its suite once, at init")

        let file = try Repo.temporaryDirectory().appendingPathComponent(FavouritesBackup.suggestedFileName)
        try FavouritesBackup.export(saved).write(to: file)
        let parsed = try FavouritesBackup.parse(try Data(contentsOf: file), now: now, isKnown: isKnown(in: snapshot))
        XCTAssertEqual(parsed.notInSnapshot, 0)
        XCTAssertEqual(parsed.unreadable, 0)

        let restored = freshStore()
        XCTAssertEqual(restored.entries, [])
        let result = restored.merge(parsed.entries)
        XCTAssertEqual(result.added, 3)
        XCTAssertEqual(result.alreadySaved, 0)
        XCTAssertEqual(restored.entries, saved, "kind, id and added date all survive the file")
        let reopened = FavouritesStore(defaults: UserDefaults(suiteName: suites.last!)!)
        XCTAssertEqual(reopened.entries, saved, "the import was persisted, not just held in memory")
    }

    /// The real snapshot the app ships: favourite a spread of its shows and
    /// characters, export, import into an empty store.
    func testRoundTripOnTheBundledSnapshot() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let store = freshStore()
        for show in snapshot.shows.prefix(40) { store.toggle(.show, id: show.id) }
        for character in snapshot.characters.suffix(40) { store.toggle(.character, id: character.id) }
        let parsed = try FavouritesBackup.parse(try FavouritesBackup.export(store.entries), now: now, isKnown: isKnown(in: snapshot))
        XCTAssertEqual(parsed.entries, store.entries)
        let restored = freshStore()
        restored.merge(parsed.entries)
        XCTAssertEqual(restored.entries.map(\.key), store.entries.map(\.key))
        XCTAssertEqual(restored.entries.count, 80)
    }

    /// Unknown ids are ignored: counted, never stored.
    func testIdsNotInTheSnapshotAreSkippedAndCounted() throws {
        let snapshot = try Repo.fixture()
        let entries = [
            FavouritesStore.Entry(kind: .show, id: snapshot.shows[0].id, addedAt: now),
            FavouritesStore.Entry(kind: .show, id: "lwtv:show:987654321", addedAt: now),
            FavouritesStore.Entry(kind: .character, id: "lwtv:character:987654321", addedAt: now),
        ]
        XCTAssertNil(snapshot.show(id: "lwtv:show:987654321"), "the unknown id must really be unknown")
        let parsed = try FavouritesBackup.parse(try FavouritesBackup.export(entries), now: now, isKnown: isKnown(in: snapshot))
        XCTAssertEqual(parsed.entries.map(\.id), [snapshot.shows[0].id])
        XCTAssertEqual(parsed.notInSnapshot, 2)
        XCTAssertEqual(parsed.unreadable, 0)
    }

    // MARK: The file

    func testTheFileHoldsOnlyKindIdAndDate() throws {
        let entries = [FavouritesStore.Entry(kind: .show, id: "lwtv:show:26", addedAt: Date(timeIntervalSince1970: 1_789_724_682))]
        let data = try FavouritesBackup.export(entries)
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(Set(root.keys), ["format", "version", "favourites"])
        XCTAssertEqual(root["format"] as? String, "favourites-backup")
        XCTAssertEqual(root["version"] as? Int, 1)
        let items = try XCTUnwrap(root["favourites"] as? [[String: Any]])
        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(Set(items[0].keys), ["kind", "id", "added_at"], "nothing but the favourite itself leaves in the file")
        XCTAssertEqual(items[0]["added_at"] as? String, "2026-09-18T09:44:42Z")
        XCTAssertEqual(try FavouritesBackup.export(entries), data, "the same favourites export to the same bytes")
    }

    // MARK: Validation

    func testFilesThatAreNotABackupAreRefused() throws {
        let notBackups: [Data] = [
            Data("lwtv:show:26\n".utf8),
            Data([0xFF, 0xD8, 0xFF, 0xE0]),
            try json([["kind": "show", "id": "lwtv:show:26"]]),
            try json(["format": "something-else", "version": 1, "favourites": []]),
            try json(["format": "favourites-backup", "version": 1]),
            try json(["format": "favourites-backup", "favourites": []]),
        ]
        for data in notBackups {
            XCTAssertThrowsError(try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })) { error in
                XCTAssertEqual(error as? FavouritesBackup.ImportError, .notABackup, String(decoding: data, as: UTF8.self))
            }
        }
    }

    func testANewerBackupVersionIsRefusedNotGuessedAt() throws {
        let data = try json(["format": "favourites-backup", "version": 2, "favourites": []])
        XCTAssertThrowsError(try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })) { error in
            XCTAssertEqual(error as? FavouritesBackup.ImportError, .unsupportedVersion(2))
        }
    }

    func testAnOversizedFileIsRefusedBeforeItIsParsed() {
        let data = Data(count: FavouritesBackup.maxBytes + 1)
        XCTAssertThrowsError(try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })) { error in
            XCTAssertEqual(error as? FavouritesBackup.ImportError, .tooLarge(bytes: FavouritesBackup.maxBytes + 1))
        }
    }

    func testTooManyEntriesAreRefused() throws {
        let items = Array(repeating: ["kind": "show", "id": "lwtv:show:1"], count: FavouritesBackup.maxEntries + 1)
        let data = try json(["format": "favourites-backup", "version": 1, "favourites": items])
        XCTAssertLessThanOrEqual(data.count, FavouritesBackup.maxBytes, "must reach the entry cap, not the size cap")
        XCTAssertThrowsError(try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })) { error in
            XCTAssertEqual(error as? FavouritesBackup.ImportError, .tooManyEntries(FavouritesBackup.maxEntries + 1))
        }
    }

    func testMalformedEntriesAreSkippedAndCounted() throws {
        let items: [Any] = [
            ["kind": "show", "id": "lwtv:show:26"], // the one good entry
            ["kind": "episode", "id": "lwtv:show:26"], // unknown kind
            ["kind": "show", "id": "lwtv:character:26"], // kind and id disagree
            ["kind": "show", "id": "lwtv:show:"], // no number
            ["kind": "show", "id": "lwtv:show:26x"], // not digits
            ["kind": "show", "id": "lwtv:show:\u{0662}\u{0666}"], // non-ASCII digits
            ["kind": "show", "id": "lwtv:show:1234567890123"], // longer than any real id
            ["kind": "show", "id": 26], // not a string
            ["kind": "show"], // no id
            "lwtv:show:26", // not an object
        ]
        let data = try json(["format": "favourites-backup", "version": 1, "favourites": items])
        let parsed = try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })
        XCTAssertEqual(parsed.entries.map(\.key), ["show:lwtv:show:26"])
        XCTAssertEqual(parsed.unreadable, items.count - 1)
        XCTAssertEqual(parsed.notInSnapshot, 0)
    }

    func testDuplicatesCollapseAndDatesAreKeptOrReplacedSafely() throws {
        let items: [[String: Any]] = [
            ["kind": "show", "id": "lwtv:show:26", "added_at": "2026-01-02T03:04:05Z"],
            ["kind": "show", "id": "lwtv:show:26", "added_at": "2026-05-05T05:05:05Z"],
            ["kind": "character", "id": "lwtv:character:7", "added_at": "not a date"],
            ["kind": "character", "id": "lwtv:character:8", "added_at": "2099-01-01T00:00:00Z"],
        ]
        let data = try json(["format": "favourites-backup", "version": 1, "favourites": items, "future_field": true])
        let parsed = try FavouritesBackup.parse(data, now: now, isKnown: { _, _ in true })
        XCTAssertEqual(parsed.entries.map(\.key), ["show:lwtv:show:26", "character:lwtv:character:7", "character:lwtv:character:8"])
        XCTAssertEqual(parsed.entries[0].addedAt, ISO8601DateFormatter().date(from: "2026-01-02T03:04:05Z"), "first occurrence wins")
        XCTAssertEqual(parsed.entries[1].addedAt, now, "an unreadable date becomes the import time")
        XCTAssertEqual(parsed.entries[2].addedAt, now, "a future date is clamped to the import time")
    }

    func testMergeKeepsWhatIsAlreadySaved() throws {
        let store = freshStore()
        store.toggle(.show, id: "lwtv:show:26")
        let saved = store.entries[0]
        let result = store.merge([
            FavouritesStore.Entry(kind: .show, id: "lwtv:show:26", addedAt: Date(timeIntervalSince1970: 0)),
            FavouritesStore.Entry(kind: .character, id: "lwtv:character:7", addedAt: now),
        ])
        XCTAssertEqual(result.added, 1)
        XCTAssertEqual(result.alreadySaved, 1)
        XCTAssertEqual(store.entries.first, saved, "the saved entry keeps its own date")
        XCTAssertEqual(store.entries.map(\.key), ["show:lwtv:show:26", "character:lwtv:character:7"])
    }

    // MARK: Negative controls

    /// A corrupted export must be refused. The sabotage is checked first: if
    /// the format marker were not in the bytes, the replacement would do
    /// nothing and the refusal below would be testing an intact file.
    func testACorruptedExportIsRefused() throws {
        let good = try FavouritesBackup.export([FavouritesStore.Entry(kind: .show, id: "lwtv:show:26", addedAt: now)])
        let text = String(decoding: good, as: UTF8.self)
        let corrupted = Data(text.replacingOccurrences(of: "\"favourites-backup\"", with: "\"favourites-backuq\"").utf8)
        XCTAssertNotEqual(corrupted, good, "the sabotage did not land")
        XCTAssertNoThrow(try FavouritesBackup.parse(good, now: now, isKnown: { _, _ in true }))
        XCTAssertThrowsError(try FavouritesBackup.parse(corrupted, now: now, isKnown: { _, _ in true })) { error in
            XCTAssertEqual(error as? FavouritesBackup.ImportError, .notABackup)
        }
    }

    /// The known-id check is really consulted: drop one id from what the
    /// snapshot knows, and that one entry, and only it, is skipped.
    func testRemovingAnIdFromTheSnapshotSkipsExactlyThatEntry() throws {
        let snapshot = try Repo.fixture()
        let entries = snapshot.shows.map { FavouritesStore.Entry(kind: .show, id: $0.id, addedAt: now) }
        let data = try FavouritesBackup.export(entries)
        var known = Set(snapshot.shows.map(\.id))
        let dropped = snapshot.shows[1].id
        XCTAssertNotNil(known.remove(dropped), "the sabotage did not land: \(dropped) was not in the known set")
        XCTAssertFalse(known.contains(dropped))
        let parsed = try FavouritesBackup.parse(data, now: now, isKnown: { kind, id in kind == .show && known.contains(id) })
        XCTAssertEqual(parsed.notInSnapshot, 1)
        XCTAssertEqual(parsed.entries.map(\.id), entries.map(\.id).filter { $0 != dropped })
    }

    // MARK: What the app says after an import

    func testImportSummaryAccountsForEveryEntry() {
        XCTAssertEqual(Presentation.importSummary(added: 3, alreadySaved: 0, notInSnapshot: 0, unreadable: 0), "Added 3 favourites.")
        XCTAssertEqual(Presentation.importSummary(added: 1, alreadySaved: 1, notInSnapshot: 1, unreadable: 1),
                       "Added 1 favourite. 1 was already saved. 1 is not in this snapshot and was skipped. 1 entry could not be read and was skipped.")
        XCTAssertEqual(Presentation.importSummary(added: 0, alreadySaved: 2, notInSnapshot: 3, unreadable: 0),
                       "No new favourites were added. 2 were already saved. 3 are not in this snapshot and were skipped.")
        XCTAssertEqual(Presentation.importSummary(added: 0, alreadySaved: 0, notInSnapshot: 0, unreadable: 0), "The file lists no favourites. Nothing was added.")
    }
}
