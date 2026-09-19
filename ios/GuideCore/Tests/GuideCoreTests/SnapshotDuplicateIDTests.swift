import XCTest
@testable import GuideCore

/// A downloaded file that repeats a show or character id must be refused like
/// any other bad download: the previous snapshot stays. It must never reach
/// `Dictionary(uniqueKeysWithValues:)`, which traps (a `Fatal error:
/// Duplicate values for key`) and so would crash the app at every launch,
/// because a refresh runs at launch. The schema cannot say "unique by id",
/// so these tests are the guard.
final class SnapshotDuplicateIDTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        try super.setUpWithError()
        dir = try Repo.temporaryDirectory()
        StubURLProtocol.reset()
    }

    override func tearDownWithError() throws {
        StubURLProtocol.reset()
        try? FileManager.default.removeItem(at: dir)
        try super.tearDownWithError()
    }

    // MARK: Planting a duplicate

    /// The fixture with `copies` of the record at `index` appended to `key`
    /// ("shows" or "characters"), each retitled or renamed so it is a
    /// different record that merely shares an id.
    private func fixtureRepeating(_ key: String, at index: Int, times copies: Int = 1) throws -> Data {
        try JSONEdit.edit(try Repo.fixtureData()) { root in
            var records = root[key] as! [[String: Any]]
            var copy = records[index]
            if key == "shows" { copy["title"] = "Imposter" } else { copy["name"] = "Imposter" }
            records += Array(repeating: copy, count: copies)
            root[key] = records
        }
    }

    private func ids(_ data: Data, _ key: String) throws -> [String] {
        let root = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        return (root[key] as! [[String: Any]]).map { $0["id"] as! String }
    }

    /// Negative control for every test below: the duplicate really is in the
    /// bytes they feed the decoder, and the untouched fixture is not refused.
    func testThePlantedDuplicatesAreReallyThereAndTheFixtureIsClean() throws {
        let clean = try ids(try Repo.fixtureData(), "shows")
        XCTAssertEqual(Set(clean).count, clean.count)
        XCTAssertNoThrow(try Repo.fixture())

        let shows = try ids(try fixtureRepeating("shows", at: 0), "shows")
        XCTAssertEqual(shows.count, clean.count + 1)
        XCTAssertEqual(Set(shows).count, clean.count, "one id appears twice")
        let characters = try ids(try fixtureRepeating("characters", at: 0), "characters")
        XCTAssertEqual(Set(characters).count, characters.count - 1, "one id appears twice")
    }

    // MARK: The decoder refuses, and names the id

    func testADuplicatedShowIDIsRefusedNamingTheID() throws {
        let data = try fixtureRepeating("shows", at: 0)
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed("duplicate show id lwtv:show:101"))
        }
    }

    func testADuplicatedCharacterIDIsRefusedNamingTheID() throws {
        let data = try fixtureRepeating("characters", at: 2)
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed("duplicate character id lwtv:character:203"))
        }
    }

    func testAnIdenticalCopyIsRefusedToo() throws {
        // Not just a conflicting record: a file that lists one show twice is
        // as suspect as one that lists two different shows under one id.
        let data = try JSONEdit.edit(try Repo.fixtureData()) { root in
            let shows = root["shows"] as! [[String: Any]]
            root["shows"] = shows + [shows[1]]
        }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed("duplicate show id lwtv:show:102"))
        }
    }

    func testTheReportedIDIsDeterministic() throws {
        // Two repeated ids: the report names the one whose repeat comes first
        // in the file, however many times it is decoded, and shows are checked
        // before characters.
        let data = try JSONEdit.edit(try Repo.fixtureData()) { root in
            let shows = root["shows"] as! [[String: Any]]
            root["shows"] = shows + [shows[2], shows[0]]
            let characters = root["characters"] as! [[String: Any]]
            root["characters"] = characters + [characters[0]]
        }
        for _ in 0..<3 {
            XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
                XCTAssertEqual(error as? SnapshotDecodingError, .malformed("duplicate show id lwtv:show:103"))
            }
        }
        // With the shows repaired, the character duplicate is what is named.
        let onlyCharacters = try JSONEdit.edit(data) { root in
            root["shows"] = Array((root["shows"] as! [[String: Any]]).prefix(4))
        }
        XCTAssertThrowsError(try SnapshotDecoder().decode(onlyCharacters)) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed("duplicate character id lwtv:character:201"))
        }
    }

    func testTheErrorReadsAsAPlainSentence() throws {
        XCTAssertThrowsError(try SnapshotDecoder().decode(try fixtureRepeating("shows", at: 0))) { error in
            XCTAssertEqual(error.localizedDescription, "Snapshot is malformed: duplicate show id lwtv:show:101")
        }
    }

    // MARK: A refused download changes nothing

    func testReplaceGivenADuplicateKeepsTheLastGoodFileByteForByte() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")

        for (key, index) in [("shows", 0), ("characters", 3)] {
            let bad = try fixtureRepeating(key, at: index)
            XCTAssertThrowsError(try store.replace(with: bad, etag: "\"v2\""))
            XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good, "duplicate \(key): the previous file is untouched")
            XCTAssertEqual(store.readETag(), "\"v1\"", "duplicate \(key): a refused body must not advance the ETag")
        }
        let names = try FileManager.default.contentsOfDirectory(atPath: dir.path).sorted()
        XCTAssertEqual(names, ["snapshot.v1.etag", "snapshot.v1.json"], "no temporary file left behind")
    }

    func testAFileWithADuplicateOnDiskFallsBackToTheBundledSnapshot() throws {
        // An earlier build could have stored such a file. Loading it must
        // neither crash nor be preferred over the bundled snapshot.
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try fixtureRepeating("shows", at: 0).write(to: store.snapshotFileURL)
        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertEqual(loaded.snapshot.shows.count, 4)
    }

    func testADownloadWithADuplicateIsRejectedAndTheLastGoodStays() async throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        let bad = try fixtureRepeating("characters", at: 1)
        StubURLProtocol.handler = { _ in .init(status: 200, headers: ["ETag": "\"bad\""], body: bad) }
        let refresher = SnapshotRefresher(store: store, protocolClasses: [StubURLProtocol.self])
        do {
            _ = try await refresher.refresh()
            XCTFail("expected the download to be rejected")
        } catch let error as SnapshotRefresher.RefreshError {
            guard case .rejected = error else { return XCTFail("\(error)") }
        }
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
        XCTAssertEqual(store.readETag(), "\"v1\"")
    }

    // MARK: Building a Snapshot in code never traps either

    private func snapshot(showing shows: [Show], characters: [Character]) throws -> Snapshot {
        let s = try Repo.fixture()
        return Snapshot(
            schemaVersion: s.schemaVersion, generatedAt: s.generatedAt, contentDigest: s.contentDigest,
            license: s.license, attribution: s.attribution, coverage: s.coverage, taxonomies: s.taxonomies,
            shows: shows, characters: characters
        )
    }

    private func imposter(of json: [String: Any], retitling key: String) throws -> Data {
        var copy = json
        copy[key] = "Imposter"
        return try JSONSerialization.data(withJSONObject: copy)
    }

    func testTheInitializerKeepsTheFirstRecordOfARepeatedID() throws {
        let fixture = try Repo.fixture()
        let root = try JSONSerialization.jsonObject(with: try Repo.fixtureData()) as! [String: Any]
        let showJSON = (root["shows"] as! [[String: Any]])[0]
        let characterJSON = (root["characters"] as! [[String: Any]])[0]
        let imposterShow = try JSONDecoder().decode(Show.self, from: try imposter(of: showJSON, retitling: "title"))
        let imposterCharacter = try JSONDecoder().decode(Character.self, from: try imposter(of: characterJSON, retitling: "name"))
        XCTAssertEqual(imposterShow.id, fixture.shows[0].id, "the planted record shares the id")
        XCTAssertEqual(imposterCharacter.id, fixture.characters[0].id)

        // This is the call that used to end in `Fatal error: Duplicate values for key`.
        let s = try snapshot(showing: fixture.shows + [imposterShow], characters: fixture.characters + [imposterCharacter])

        XCTAssertEqual(s.shows.map(\.id), fixture.shows.map(\.id), "one record per id, in the original order")
        XCTAssertEqual(s.characters.map(\.id), fixture.characters.map(\.id))
        XCTAssertEqual(s.show(id: fixture.shows[0].id)?.title, fixture.shows[0].title, "the first record wins")
        XCTAssertEqual(s.character(id: fixture.characters[0].id)?.name, fixture.characters[0].name)
        let cast = s.characters(inShow: "lwtv:show:101").map(\.id)
        XCTAssertEqual(Set(cast).count, cast.count, "a cast lists each character once")
        XCTAssertEqual(s, fixture, "the same snapshot as the one without the extra records")
    }

    func testTheInitializerAcceptsUniqueRecordsUnchanged() throws {
        let fixture = try Repo.fixture()
        XCTAssertEqual(try snapshot(showing: fixture.shows, characters: fixture.characters), fixture)
    }

    // MARK: The trapping call stays out of the app

    /// Source lines (comments excluded) that build a dictionary with
    /// `Dictionary(uniqueKeysWithValues:)`.
    static func trappingCalls(in text: String) -> [Int] {
        text.split(separator: "\n", omittingEmptySubsequences: false).enumerated().compactMap { offset, line in
            let code = line.trimmingCharacters(in: .whitespaces)
            return !code.hasPrefix("//") && code.contains("uniqueKeysWithValues") ? offset + 1 : nil
        }
    }

    func testNoAppSourceBuildsADictionaryThatTrapsOnARepeatedKey() throws {
        var scanned = 0
        var problems: [String] = []
        for file in Repo.sourceFiles(extensions: ["swift"]) {
            let path = file.path
            guard path.contains("/GuideCore/Sources/") || path.contains("/ios/QueerTVGuide/") else { continue }
            scanned += 1
            for line in Self.trappingCalls(in: try String(contentsOf: file, encoding: .utf8)) {
                problems.append("\(file.lastPathComponent):\(line)")
            }
        }
        XCTAssertGreaterThan(scanned, 10, "the scan saw the app's sources")
        XCTAssertEqual(problems, [], "use Dictionary(_:uniquingKeysWith:), which cannot trap")
    }

    /// Negative control: the scan really flags the call it exists to keep out.
    func testTheScanCatchesTheTrappingCall() {
        let old = "        showsByID = Dictionary(uniqueKeysWithValues: shows.map { ($0.id, $0) })"
        XCTAssertEqual(Self.trappingCalls(in: "let a = 1\n" + old), [2])
        XCTAssertEqual(Self.trappingCalls(in: "/// mentions uniqueKeysWithValues in prose"), [])
    }
}
