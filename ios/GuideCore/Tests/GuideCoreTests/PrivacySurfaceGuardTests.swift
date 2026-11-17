import XCTest
@testable import GuideCore

/// Static gates over the two places where what someone follows or looks up
/// could reach beyond the app: the home-screen widget on a locked iPhone,
/// and the keyboard's learned words.
///
/// SwiftUI gives a test no way to ask a view "are you privacy-sensitive?"
/// or a search field "is autocorrection off?", so these read the source, as
/// `SourceTreeGuardTests` does. `WidgetRenderTests` draws the widget
/// redacted in the simulator; this file is what fails first, on any Mac.
/// Each rule has a negative control.
final class PrivacySurfaceGuardTests: XCTestCase {
    private func source(_ relative: String) throws -> String {
        try String(contentsOf: Repo.iosRoot.appendingPathComponent(relative), encoding: .utf8)
    }

    // MARK: The widget on a locked iPhone

    /// In the widget's `row(_:)`, each view that draws a show's title or its
    /// episode line, with the modifiers chained onto it. A chain starts at a
    /// line holding `Text(item.` or at the bare name `line` (the episode
    /// text, built once above and placed twice) and runs over the
    /// following lines that start with a dot.
    static func showTextChains(inWidgetSource text: String) -> [String] {
        guard let start = text.range(of: "private func row(_ item: UpNext.Item)"),
              let end = text.range(of: "\n    }\n", range: start.upperBound..<text.endIndex)
        else { return [] }
        let lines = text[start.upperBound..<end.lowerBound].components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
        var chains: [String] = []
        var index = 0
        while index < lines.count {
            let line = lines[index]
            index += 1
            guard line.hasPrefix("Text(item.") || line == "line" else { continue }
            var chain = line
            while index < lines.count, lines[index].hasPrefix(".") {
                chain += lines[index]
                index += 1
            }
            chains.append(chain)
        }
        return chains
    }

    static func unmarked(_ chains: [String]) -> [String] {
        chains.filter { !$0.contains(".privacySensitive()") }
    }

    private static let widgetView = "QueerTVGuideWidgets/UpNextWidgetView.swift"

    func testEveryShowTitleAndEpisodeLineInTheWidgetIsPrivacySensitive() throws {
        let chains = Self.showTextChains(inWidgetSource: try source(Self.widgetView))
        XCTAssertEqual(chains.count, 4, "the title and the episode line, at each of the two sizes: \(chains)")
        XCTAssertEqual(chains.filter { $0.hasPrefix("Text(item.title)") }.count, 2)
        XCTAssertEqual(Self.unmarked(chains), [])
    }

    /// Nothing else in the widget draws from a favorite: the header, the
    /// messages, the "+2 more" count and the data's date name no show.
    func testNoOtherTextInTheWidgetNamesAShow() throws {
        let text = try source(Self.widgetView)
        let drawn = text.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }.filter { $0.contains("Text(") }
        let fromAnItem = drawn.filter { $0.contains("item") }
        XCTAssertEqual(fromAnItem, ["let line = Text(UpNextPresentation.line(item, today: entry.date))", "Text(item.title)", "Text(item.title)"])
    }

    func testVoiceOverDoesNotReadAHiddenRow() throws {
        let item = UpNext.Item(showID: "lwtv:show:1", title: "Harbor Lights", status: .dated, season: 2, number: 3, airdate: "2026-10-15")
        let today = Date(timeIntervalSince1970: 1_790_000_000)
        let shown = UpNextPresentation.spoken(item, today: today, hidden: false)
        XCTAssertEqual(shown, UpNextPresentation.spoken(item, today: today))
        XCTAssertTrue(shown.contains("Harbor Lights"))
        let hidden = UpNextPresentation.spoken(item, today: today, hidden: true)
        XCTAssertEqual(hidden, "Hidden while locked")
        XCTAssertFalse(hidden.contains("Harbor"))
        XCTAssertFalse(hidden.contains("2"), "no season, episode or date either")

        let text = try source(Self.widgetView)
        XCTAssertTrue(text.contains("@Environment(\\.redactionReasons) private var redactionReasons"))
        XCTAssertTrue(text.contains("redactionReasons.contains(.privacy)"))
        XCTAssertTrue(text.contains(".accessibilityLabel(UpNextPresentation.spoken(item, today: entry.date, hidden: hidden))"))
        XCTAssertFalse(text.contains("UpNextPresentation.spoken(item, today: entry.date))"), "a row's label never skips the hidden check")
    }

    func testControlAnUnmarkedTitleOrEpisodeLineIsCaught() throws {
        let text = try source(Self.widgetView)
        XCTAssertEqual(Self.unmarked(Self.showTextChains(inWidgetSource: text)), [])
        let marked = "                    .lineLimit(2)\n                    .privacySensitive()\n                line\n"
        XCTAssertTrue(text.contains(marked), "the sabotage would not land")
        let titleBare = text.replacingOccurrences(of: marked, with: "                    .lineLimit(2)\n                line\n")
        XCTAssertEqual(Self.unmarked(Self.showTextChains(inWidgetSource: titleBare)).count, 1)
        let lineMarked = "                    .layoutPriority(1)\n                    .privacySensitive()\n"
        XCTAssertTrue(text.contains(lineMarked), "the sabotage would not land")
        let lineBare = text.replacingOccurrences(of: lineMarked, with: "                    .layoutPriority(1)\n")
        XCTAssertEqual(Self.unmarked(Self.showTextChains(inWidgetSource: lineBare)), ["line.lineLimit(1).layoutPriority(1)"])
    }

    // MARK: The keyboard

    /// Text inputs in `text` that leave autocorrection on, as "line N: …".
    /// A `.searchable` must be followed by `.autocorrectionDisabled()` (only
    /// comment lines may sit between). Any other kind of text field is
    /// reported outright: the app has none, and one added later has to be
    /// given a rule here.
    static func learningInputs(in text: String) -> [String] {
        let lines = text.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
        var found: [String] = []
        for (index, line) in lines.enumerated() {
            if ["TextField(", "TextEditor(", "SecureField("].contains(where: line.contains) {
                found.append("line \(index + 1): \(line)")
            }
            guard line.contains(".searchable(") else { continue }
            let next = lines[(index + 1)...].first { !$0.hasPrefix("//") } ?? ""
            if !next.hasPrefix(".autocorrectionDisabled()") {
                found.append("line \(index + 1): \(line)")
            }
        }
        return found
    }

    func testEverySearchFieldTurnsAutocorrectionOff() throws {
        var fields: [String] = []
        var problems: [String] = []
        for file in Repo.sourceFiles(extensions: ["swift"]) where file.path.contains("/QueerTVGuide/") || file.path.contains("/QueerTVGuideWidgets/") {
            let text = try String(contentsOf: file, encoding: .utf8)
            if text.contains(".searchable(") { fields.append(file.lastPathComponent) }
            problems += Self.learningInputs(in: text).map { "\(file.lastPathComponent) \($0)" }
        }
        XCTAssertEqual(fields.sorted(), ["SearchFiltersView.swift", "SearchView.swift"], "the app's two search fields")
        XCTAssertEqual(problems, [])
    }

    func testControlASearchFieldLeftToLearnIsCaught() {
        let good = "content\n    .searchable(text: $query)\n    // why\n    .autocorrectionDisabled()\n    .toolbar {}\n"
        XCTAssertEqual(Self.learningInputs(in: good), [])
        let bare = good.replacingOccurrences(of: "    .autocorrectionDisabled()\n", with: "")
        XCTAssertNotEqual(bare, good)
        XCTAssertEqual(Self.learningInputs(in: bare), ["line 2: .searchable(text: $query)"])
        let later = "content\n    .searchable(text: $query)\n    .toolbar {}\n    .autocorrectionDisabled()\n"
        XCTAssertEqual(Self.learningInputs(in: later).count, 1, "it must sit on the search field, not further down")
        XCTAssertEqual(Self.learningInputs(in: "TextField(\"Name\", text: $name)\n").count, 1)
    }
}
