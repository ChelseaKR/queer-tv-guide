import XCTest
@testable import GuideCore

/// A snapshot must carry LezWatch.TV's credit and TVmaze's credit, each once,
/// or the app refuses it. The credit shown next to TVmaze's next-episode
/// dates comes only from the downloaded file, and the schema does not require
/// one entry per source (two `lezwatch` items validate), so the check is
/// code. Bundled and downloaded snapshots take the same route, through
/// `SnapshotDecoder`.
final class SnapshotAttributionGateTests: XCTestCase {
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

    // MARK: Editing the credits

    private func sources(in data: Data) throws -> [String] {
        let root = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        return (root["attribution"] as! [[String: Any]]).map { $0["source"] as! String }
    }

    /// The fixture with its `attribution` rewritten by `change`.
    private func fixtureWithAttribution(_ change: ([[String: Any]]) -> [[String: Any]]) throws -> Data {
        try JSONEdit.edit(try Repo.fixtureData()) { root in
            root["attribution"] = change(root["attribution"] as! [[String: Any]])
        }
    }

    private func entry(_ source: String, in items: [[String: Any]]) -> [String: Any] {
        items.first { $0["source"] as? String == source }!
    }

    private var withoutTVmaze: Data {
        get throws { try fixtureWithAttribution { $0.filter { $0["source"] as? String != "tvmaze" } } }
    }

    private var withoutLezWatch: Data {
        get throws { try fixtureWithAttribution { $0.filter { $0["source"] as? String != "lezwatch" } } }
    }

    /// Two items, so the schema's `minItems: 2` is met, both for one source.
    private var twoLezWatchEntries: Data {
        get throws { try fixtureWithAttribution { [entry("lezwatch", in: $0), entry("lezwatch", in: $0)] } }
    }

    private var twoTVmazeEntriesAndNoLezWatch: Data {
        get throws { try fixtureWithAttribution { [entry("tvmaze", in: $0), entry("tvmaze", in: $0)] } }
    }

    private func assertRefused(_ data: Data, as detail: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertThrowsError(try SnapshotDecoder().decode(data), file: file, line: line) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed(detail), file: file, line: line)
        }
    }

    // MARK: The decoder refuses, and names the source

    func testTheEditsReallyChangeTheCredits() throws {
        XCTAssertEqual(try sources(in: try Repo.fixtureData()), ["lezwatch", "tvmaze"])
        XCTAssertEqual(try sources(in: try withoutTVmaze), ["lezwatch"])
        XCTAssertEqual(try sources(in: try withoutLezWatch), ["tvmaze"])
        XCTAssertEqual(try sources(in: try twoLezWatchEntries), ["lezwatch", "lezwatch"])
        XCTAssertEqual(try sources(in: try twoTVmazeEntriesAndNoLezWatch), ["tvmaze", "tvmaze"])
        XCTAssertNoThrow(try Repo.fixture(), "the unedited fixture is accepted")
    }

    func testAMissingTVmazeEntryIsRefused() throws {
        assertRefused(try withoutTVmaze, as: "attribution has no entry for source tvmaze")
    }

    func testAMissingLezWatchEntryIsRefused() throws {
        assertRefused(try withoutLezWatch, as: "attribution has no entry for source lezwatch")
    }

    func testTwoEntriesForOneSourceAreRefused() throws {
        assertRefused(try twoLezWatchEntries, as: "attribution has 2 entries for source lezwatch, expected exactly one")
        // Two TVmaze items and no LezWatch item: LezWatch is checked first.
        assertRefused(try twoTVmazeEntriesAndNoLezWatch, as: "attribution has no entry for source lezwatch")
        let bothTwice = try fixtureWithAttribution { $0 + $0 }
        assertRefused(bothTwice, as: "attribution has 2 entries for source lezwatch, expected exactly one")
    }

    func testAnEmptyAttributionListIsRefused() throws {
        assertRefused(try fixtureWithAttribution { _ in [] }, as: "attribution has no entry for source lezwatch")
    }

    func testAFileWithBothCreditsIsAccepted() throws {
        let s = try SnapshotDecoder().decode(try Repo.fixtureData())
        XCTAssertNotNil(s.attribution(for: Attribution.lezWatchSource))
        XCTAssertNotNil(s.attribution(for: Attribution.tvmazeSource))
        XCTAssertNotNil(Attribution.tvmazeCredit(in: s))
        // The order of the entries is not part of the rule.
        let reversed = try fixtureWithAttribution { $0.reversed() }
        XCTAssertEqual(try SnapshotDecoder().decode(reversed).attribution.map(\.source), ["tvmaze", "lezwatch"])
    }

    func testTheRuleNamesNoSourceButTheTwoCredits() throws {
        // A source the app has no credit rules for is left alone; only
        // LezWatch.TV's and TVmaze's must each be present exactly once. (The
        // schema's own `source` enum is what keeps such an entry out.)
        let extra = try fixtureWithAttribution { items in
            var other = entry("tvmaze", in: items)
            other["source"] = "another-source"
            return items + [other]
        }
        XCTAssertEqual(try SnapshotDecoder().decode(extra).attribution.count, 3)
    }

    func testTheErrorReadsAsAPlainSentence() throws {
        XCTAssertThrowsError(try SnapshotDecoder().decode(try withoutTVmaze)) { error in
            XCTAssertEqual(error.localizedDescription, "Snapshot is malformed: attribution has no entry for source tvmaze")
        }
    }

    // MARK: A refused download changes nothing

    func testReplaceGivenAFileWithoutACreditKeepsTheLastGoodFileByteForByte() throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")

        for bad in [try withoutTVmaze, try withoutLezWatch, try twoLezWatchEntries] {
            XCTAssertThrowsError(try store.replace(with: bad, etag: "\"v2\""))
            XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good, "the previous file is untouched")
            XCTAssertEqual(store.readETag(), "\"v1\"", "a refused body must not advance the ETag")
        }
        let names = try FileManager.default.contentsOfDirectory(atPath: dir.path).sorted()
        XCTAssertEqual(names, ["snapshot.v1.etag", "snapshot.v1.json"], "no temporary file left behind")
    }

    func testADownloadWithoutACreditIsRejectedAndTheLastGoodStays() async throws {
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        let bad = try withoutTVmaze
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

    // MARK: Bundled and downloaded files both go through the rule

    func testADownloadedFileWithoutACreditIsIgnoredOnLoad() throws {
        // An earlier build could have stored one. It is not preferred over the
        // bundled snapshot, and it is not deleted.
        let store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try withoutTVmaze.write(to: store.snapshotFileURL)
        let loaded = try store.load()
        XCTAssertEqual(loaded.origin, .bundled)
        XCTAssertNotNil(Attribution.tvmazeCredit(in: loaded.snapshot))
        XCTAssertTrue(FileManager.default.fileExists(atPath: store.snapshotFileURL.path))
    }

    func testABundledFileWithoutACreditFailsToLoad() throws {
        // A bad bundled snapshot must fail loudly (the app then says it could
        // not load the catalog), not load and show data uncredited.
        let bundled = dir.appendingPathComponent("bundled-without-tvmaze.json")
        try withoutTVmaze.write(to: bundled)
        let store = SnapshotStore(directory: dir.appendingPathComponent("Snapshot"), bundledURL: bundled)
        XCTAssertThrowsError(try store.load()) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .malformed("attribution has no entry for source tvmaze"))
        }
    }

    func testTheRealBundledSnapshotHasExactlyOneCreditPerSource() throws {
        guard let data = try? Data(contentsOf: Repo.bundledSnapshot) else {
            return XCTFail("\(Repo.bundledSnapshot.path) is missing: run `make -C ios bundle-snapshot`")
        }
        XCTAssertEqual(try sources(in: data).sorted(), ["lezwatch", "tvmaze"])
        XCTAssertNoThrow(try SnapshotDecoder().decode(data))
    }

    // MARK: No other route decodes a snapshot

    /// Files, by name, whose source decodes a `Snapshot` without `SnapshotDecoder`.
    static func directDecodes(in text: String) -> Bool {
        text.contains("decode(Snapshot.self")
    }

    func testNothingButTheDecoderDecodesASnapshotDirectly() throws {
        var scanned = 0
        var offenders: [String] = []
        for file in Repo.sourceFiles(extensions: ["swift"]) {
            let path = file.path
            guard path.contains("/GuideCore/Sources/") || path.contains("/ios/QueerTVGuide/") else { continue }
            scanned += 1
            if Self.directDecodes(in: try String(contentsOf: file, encoding: .utf8)) { offenders.append(file.lastPathComponent) }
        }
        XCTAssertGreaterThan(scanned, 10, "the scan saw the app's sources")
        XCTAssertEqual(offenders, ["SnapshotDecoder.swift"], "a second decode route would skip the credit rule")
    }

    /// Negative control: the scan really flags a direct decode.
    func testTheScanCatchesADirectDecode() {
        XCTAssertTrue(Self.directDecodes(in: "let s = try JSONDecoder().decode(Snapshot.self, from: data)"))
        XCTAssertFalse(Self.directDecodes(in: "let s = try SnapshotDecoder().decode(data)"))
    }
}
