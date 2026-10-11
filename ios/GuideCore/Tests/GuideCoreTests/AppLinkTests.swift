import XCTest
@testable import GuideCore

final class AppLinkTests: XCTestCase {
    func testShowLinkRoundTripsARealID() throws {
        let link = AppLink.show("lwtv:show:26")
        XCTAssertEqual(link.url.absoluteString, "queerframe://show/lwtv:show:26")
        XCTAssertEqual(AppLink(url: link.url), link)
    }

    func testCharacterLinkRoundTrips() {
        let link = AppLink.character("lwtv:character:241")
        XCTAssertEqual(AppLink(url: link.url), link)
    }

    func testEveryBundledShowIDRoundTrips() throws {
        let snapshot = try Repo.fixture()
        XCTAssertFalse(snapshot.shows.isEmpty)
        for show in snapshot.shows {
            XCTAssertEqual(AppLink(url: AppLink.show(show.id).url), .show(show.id), show.id)
        }
    }

    func testSchemeAndKindAreCaseInsensitive() throws {
        XCTAssertEqual(AppLink(url: try XCTUnwrap(URL(string: "QueerFrame://SHOW/lwtv:show:1"))), .show("lwtv:show:1"))
    }

    func testAnythingElseIsNil() throws {
        for text in [
            "https://chelseakr.github.io/queer-tv-guide/",
            "queerframe://show",
            "queerframe://show/",
            "queerframe://show/a/b",
            "queerframe://episode/1",
            "otherapp://show/lwtv:show:1",
        ] {
            XCTAssertNil(AppLink(url: try XCTUnwrap(URL(string: text))), text)
        }
    }

    /// The scheme in code and the one the app registers must agree, or a
    /// widget tap opens the app and goes nowhere.
    func testTheAppRegistersTheScheme() throws {
        let plist = Repo.iosRoot.appendingPathComponent("QueerTVGuide/Info.plist")
        let data = try Data(contentsOf: plist)
        let root = try XCTUnwrap(try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any])
        let types = try XCTUnwrap(root["CFBundleURLTypes"] as? [[String: Any]])
        let schemes = types.flatMap { ($0["CFBundleURLSchemes"] as? [String]) ?? [] }
        XCTAssertEqual(schemes, [AppLink.scheme])
    }
}
