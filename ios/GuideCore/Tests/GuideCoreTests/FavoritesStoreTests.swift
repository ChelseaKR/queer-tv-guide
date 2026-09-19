import XCTest
@testable import GuideCore

final class FavoritesStoreTests: XCTestCase {
    private var suiteName: String!
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        suiteName = "GuideCoreTests.favorites.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suiteName)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: suiteName)
        super.tearDown()
    }

    func testStartsEmpty() {
        XCTAssertEqual(FavoritesStore(defaults: defaults).entries, [])
    }

    func testToggleAddsThenRemoves() {
        let store = FavoritesStore(defaults: defaults, now: { Date(timeIntervalSince1970: 100) })
        XCTAssertTrue(store.toggle(.show, id: "show-harbor-lights"))
        XCTAssertTrue(store.isFavorite(.show, id: "show-harbor-lights"))
        XCTAssertFalse(store.isFavorite(.character, id: "show-harbor-lights"), "kind is part of the key")
        XCTAssertFalse(store.toggle(.show, id: "show-harbor-lights"))
        XCTAssertEqual(store.entries, [])
    }

    func testPersistsAcrossInstances() {
        let a = FavoritesStore(defaults: defaults, now: { Date(timeIntervalSince1970: 100) })
        a.toggle(.show, id: "show-harbor-lights")
        a.toggle(.character, id: "char-odile-brandt")

        let b = FavoritesStore(defaults: defaults)
        XCTAssertEqual(b.entries.map(\.key), ["show:show-harbor-lights", "character:char-odile-brandt"])
        XCTAssertEqual(b.entries.first?.addedAt, Date(timeIntervalSince1970: 100))
    }

    func testRemoveAndRemoveAll() {
        let store = FavoritesStore(defaults: defaults)
        store.toggle(.show, id: "a")
        store.toggle(.show, id: "b")
        store.remove(.show, id: "a")
        XCTAssertEqual(store.entries.map(\.id), ["b"])
        store.removeAll()
        XCTAssertEqual(FavoritesStore(defaults: defaults).entries, [])
    }

    func testStoredValueIsPlainJSONUnderOneKey() throws {
        let store = FavoritesStore(defaults: defaults)
        store.toggle(.show, id: "a")
        let data = try XCTUnwrap(defaults.data(forKey: FavoritesStore.defaultsKey))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [[String: Any]])
        XCTAssertEqual(json.count, 1)
        XCTAssertEqual(Set(json[0].keys), ["kind", "id", "addedAt"], "nothing but the favorite itself is stored")
    }

    func testCorruptDefaultsReadAsEmpty() {
        defaults.set(Data("nope".utf8), forKey: FavoritesStore.defaultsKey)
        XCTAssertEqual(FavoritesStore(defaults: defaults).entries, [])
    }
}
