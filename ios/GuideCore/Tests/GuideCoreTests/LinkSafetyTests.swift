import XCTest
@testable import GuideCore

/// Every link the app takes from a data file is an https link, and a
/// where-to-watch label names the host its link opens.
///
/// URLs in this file are built from parts (`link(_:_:)`), so the file holds
/// no address of its own for `SourceTreeGuardTests` to refuse.
final class LinkSafetyTests: XCTestCase {
    /// "scheme://rest", e.g. `link("http", "www.example.com/a")`.
    private func link(_ scheme: String, _ rest: String) -> String { scheme + "://" + rest }

    // MARK: The rule

    func testAnHTTPSLinkIsKeptAsRecorded() {
        for rest in ["www.example.com/watch/a", "www.example.com/a%20b?x=1&y=2#top", "example.com", "www.example.com:8443/a"] {
            XCTAssertEqual(SecureLink.https(link("https", rest))?.absoluteString, link("https", rest))
        }
        XCTAssertEqual(SecureLink.https(link("HTTPS", "www.example.com/a"))?.scheme?.lowercased(), "https")
    }

    func testAnHTTPLinkIsOpenedAsHTTPSOnTheSameHostAndPath() {
        XCTAssertEqual(SecureLink.https(link("http", "www.example.com/dp/B074?x=1#top"))?.absoluteString, link("https", "www.example.com/dp/B074?x=1#top"))
        XCTAssertEqual(SecureLink.https(link("HTTP", "www.example.com/"))?.absoluteString, link("https", "www.example.com/"))
        XCTAssertEqual(SecureLink.https(link("http", "www.example.com:80/a"))?.absoluteString, link("https", "www.example.com/a"), "plain HTTP's own port is not carried over")
        XCTAssertEqual(SecureLink.https(link("http", "www.example.com:8080/a"))?.absoluteString, link("https", "www.example.com:8080/a"))
    }

    func testAnythingElseIsNotALink() {
        let refused = [
            "tel:+15555550100", "sms:+15555550100", "mailto:someone@example.com", "facetime:someone@example.com",
            "javascript:alert(1)", "data:text/html,hello", "file:///etc/hosts", "otherapp" + "://open/thing",
            "ftp" + "://www.example.com/a", "www.example.com/a", "//www.example.com/a", "/a/b", "", " ",
            link("https", "/no-host"), link("https", ""), link("http", ""),
            link("https", "someone@www.example.com/a"), link("https", "someone:secret@www.example.com/a"),
            link("https", "www.example.com@elsewhere.example/a"),
        ]
        for raw in refused {
            XCTAssertNil(SecureLink.https(raw), raw)
        }
    }

    // MARK: Every link field of the snapshot

    /// The JSON keys that hold a link the app decodes, apart from a
    /// where-to-watch entry's.
    private static let linkKeys: Set<String> = ["url", "licence_url", "terms_url", "source_url", "tvmaze_url"]

    /// Rewrites every link the app decodes in a JSON document (every value
    /// under `linkKeys`; a where-to-watch entry only when `watch` says so)
    /// and returns how many it rewrote.
    private func rewriteLinks(in data: Data, watch: Bool, _ change: (String) -> String) throws -> (Data, Int) {
        var count = 0
        func walk(_ value: Any, inWatchLinks: Bool) -> Any {
            if let object = value as? [String: Any] {
                var out: [String: Any] = [:]
                for (key, item) in object {
                    if Self.linkKeys.contains(key), let text = item as? String {
                        if inWatchLinks == watch {
                            count += 1
                            out[key] = change(text)
                        } else {
                            out[key] = text
                        }
                    } else {
                        out[key] = walk(item, inWatchLinks: inWatchLinks || key == "watch_links")
                    }
                }
                return out
            }
            if let array = value as? [Any] { return array.map { walk($0, inWatchLinks: inWatchLinks) } }
            return value
        }
        let rewritten = walk(try JSONSerialization.jsonObject(with: data), inWatchLinks: false)
        return (try JSONSerialization.data(withJSONObject: rewritten), count)
    }

    /// Every `URL` anywhere in a decoded value, found by reflection, so a
    /// link field added later is covered without being listed here.
    private func urls(in value: Any) -> [URL] {
        if let url = value as? URL { return [url] }
        return Mirror(reflecting: value).children.flatMap { urls(in: $0.value) }
    }

    func testEveryLinkInTheFixtureDecodesAsRecorded() throws {
        let snapshot = try Repo.fixture()
        let found = urls(in: snapshot)
        XCTAssertGreaterThanOrEqual(found.count, 20, "the fixture's links were found")
        XCTAssertEqual(found.filter { $0.scheme != "https" }, [])
        var recorded: [String] = []
        for watch in [false, true] {
            _ = try rewriteLinks(in: try Repo.fixtureData(), watch: watch) { recorded.append($0); return $0 }
        }
        XCTAssertGreaterThanOrEqual(recorded.count, 20, "every kind of link field is in the fixture")
        XCTAssertEqual(Set(found.map(\.absoluteString)), Set(recorded), "an https link is decoded exactly as recorded")
    }

    func testEveryLinkRecordedAsHTTPDecodesAsHTTPS() throws {
        let https = try Repo.fixture()
        for watch in [false, true] {
            let (data, count) = try rewriteLinks(in: try Repo.fixtureData(), watch: watch) { text in
                XCTAssertTrue(text.hasPrefix("https:"), text)
                return "http:" + text.dropFirst("https:".count)
            }
            XCTAssertGreaterThan(count, 0)
            let decoded = try SnapshotDecoder().decode(data)
            XCTAssertEqual(urls(in: decoded).filter { $0.scheme != "https" }, [], "no link is left on plain HTTP")
            XCTAssertEqual(urls(in: decoded).map(\.absoluteString).sorted(), urls(in: https).map(\.absoluteString).sorted(), "the same host and path, over https")
        }
    }

    /// A file whose own links (credits, licenses, source pages, schedules)
    /// are not web links is refused whole, one field at a time.
    func testAFileWithAnUnopenableLinkOfItsOwnIsRefused() throws {
        let original = try Repo.fixtureData()
        let (_, total) = try rewriteLinks(in: original, watch: false) { $0 }
        for bad in ["tel:+15555550100", "otherapp" + "://open", "/relative/path", link("https", "someone@www.example.com/")] {
            for index in 0..<total {
                var seen = 0
                let (data, _) = try rewriteLinks(in: original, watch: false) { text in
                    defer { seen += 1 }
                    return seen == index ? bad : text
                }
                XCTAssertNotEqual(data, original)
                XCTAssertThrowsError(try SnapshotDecoder().decode(data), "link \(index) as \(bad)") { error in
                    guard case SnapshotDecodingError.malformed(let detail) = error else { return XCTFail("\(error)") }
                    XCTAssertTrue(detail.contains(SecureLink.refusal), detail)
                    XCTAssertFalse(detail.contains(bad), "the refusal does not repeat the link")
                }
            }
        }
    }

    // MARK: Where to watch

    /// The fixture with one show's where-to-watch entries replaced.
    private func show(watchLinks: [[String: Any]]) throws -> Show {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { $0["watch_links"] = watchLinks }
        return try SnapshotDecoder().decode(data).shows[0]
    }

    func testAWatchLinkRecordedAsHTTPIsKeptAndOpensAsHTTPS() throws {
        let decoded = try show(watchLinks: [["url": link("http", "www.example.com/dp/B074"), "host": "www.example.com"]])
        XCTAssertEqual(decoded.watchLinks.map(\.url.absoluteString), [link("https", "www.example.com/dp/B074")])
        XCTAssertEqual(decoded.watchLinks.map(\.host), ["www.example.com"])
    }

    func testAWatchLinkTheAppWillNotOpenIsLeftOutAndTheOthersStand() throws {
        let good: [String: Any] = ["url": link("https", "store.example.org/a"), "host": "store.example.org"]
        for bad in ["tel:+15555550100", "sms:+15555550100", "otherapp" + "://open", "file:///etc/hosts", "www.example.com/a", ""] {
            let decoded = try show(watchLinks: [["url": bad, "host": "www.example.com"], good])
            XCTAssertEqual(decoded.watchLinks.map(\.host), ["store.example.org"], bad)
        }
        XCTAssertEqual(try show(watchLinks: [["url": "tel:+15555550100", "host": "www.example.com"]]).watchLinks, [], "a show left with none has none")
    }

    /// The label is built from `host`, so `host` must be the host the link
    /// opens.
    func testAWatchLinkLabelledWithAnotherHostIsLeftOut() throws {
        let good: [String: Any] = ["url": link("https", "store.example.org/a"), "host": "store.example.org"]
        let mislabelled: [[String: Any]] = [
            ["url": link("https", "elsewhere.example/watch"), "host": "www.example.com"],
            ["url": link("https", "www.example.com.elsewhere.example/watch"), "host": "www.example.com"],
            ["url": link("https", "www.example.com@elsewhere.example/watch"), "host": "www.example.com"],
            ["url": link("https", "www.example.com/watch"), "host": "example.com"],
            ["url": link("https", "www.example.com/watch"), "host": ""],
            ["url": link("https", "www.example.com/watch"), "host": "Netflix"],
        ]
        for entry in mislabelled {
            let decoded = try show(watchLinks: [entry, good])
            XCTAssertEqual(decoded.watchLinks.map(\.host), ["store.example.org"], "\(entry)")
        }
        let cased = try show(watchLinks: [["url": link("https", "WWW.Example.com/watch"), "host": "www.example.com"]])
        XCTAssertEqual(cased.watchLinks.count, 1, "host names compare without case")
        XCTAssertEqual(Presentation.watchLinkLabel(cased.watchLinks[0], networks: []), "Watch on example.com")
    }

    /// The shape is still the contract: an entry with no `host` at all is a
    /// broken file, not a link to leave out.
    func testAWatchLinkWithoutItsFieldsStillRefusesTheFile() throws {
        XCTAssertThrowsError(try show(watchLinks: [["url": link("https", "www.example.com/a")]]))
        XCTAssertThrowsError(try show(watchLinks: [["host": "www.example.com"]]))
    }

    func testOneEntryDecodedOnItsOwnIsHeldToTheSameRule() throws {
        func entry(_ url: String, _ host: String) throws -> WatchLink {
            try JSONDecoder().decode(WatchLink.self, from: try JSONSerialization.data(withJSONObject: ["url": url, "host": host]))
        }
        XCTAssertEqual(try entry(link("http", "www.example.com/a"), "www.example.com").url.scheme, "https")
        XCTAssertThrowsError(try entry("tel:+15555550100", "www.example.com"))
        XCTAssertThrowsError(try entry(link("https", "elsewhere.example/a"), "www.example.com"))
    }

    // MARK: The real bundled data

    /// No where-to-watch link in the data the app ships is lost to these
    /// rules, every one opens over https, and every label's host is its
    /// link's own.
    func testEveryWatchLinkInTheBundledSnapshotSurvivesOverHTTPS() throws {
        let data = try Data(contentsOf: Repo.bundledSnapshot)
        let root = try XCTUnwrap(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        let recorded = try XCTUnwrap(root["shows"] as? [[String: Any]]).flatMap { $0["watch_links"] as? [[String: Any]] ?? [] }
        let snapshot = try SnapshotDecoder().decode(data)
        let decoded = snapshot.shows.flatMap(\.watchLinks)
        XCTAssertGreaterThan(recorded.count, 1_000, "the bundled snapshot has where-to-watch links")
        XCTAssertEqual(decoded.count, recorded.count, "no recorded link is left out")
        let plain = recorded.filter { ($0["url"] as? String)?.lowercased().hasPrefix("http:") ?? false }.count
        print("LinkSafetyTests: \(recorded.count) where-to-watch links in the bundled snapshot, \(plain) recorded as plain HTTP and opened as https")
        for watch in decoded {
            XCTAssertEqual(watch.url.scheme, "https", watch.id)
            XCTAssertEqual(watch.url.host?.lowercased(), watch.host.lowercased(), watch.id)
        }
        XCTAssertEqual(urls(in: snapshot).filter { $0.scheme != "https" }, [], "and no other link in it is anything but https")
    }
}
