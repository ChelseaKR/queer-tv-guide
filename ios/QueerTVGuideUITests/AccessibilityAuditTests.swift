import XCTest
import UIKit

/// Runs Xcode's automated accessibility audit (`performAccessibilityAudit`,
/// iOS 17+) over every screen: element descriptions, hit regions, contrast,
/// Dynamic Type support, clipped text, traits. Then checks that a closed
/// "does she die" answer is nowhere VoiceOver can read it. It does not
/// replace a VoiceOver pass by a person on a device
/// (docs/a11y/voiceover-walkthrough-checklist.md); it catches the
/// regressions a machine can. CI runs it (`make a11y`, #22).
///
/// Navigation is data-agnostic on purpose (browse with a filter, take the
/// first row; the spoiler tests pick their characters from the bundled
/// snapshot file), so it holds for whatever snapshot is bundled.
final class AccessibilityAuditTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = true
    }

    /// Runs the audit. Everything it reports fails the test, printed with
    /// the element it is on so a red run says what to fix, except the four
    /// narrow allowances below. Each covers one issue type on named
    /// elements, and each rests on something measured. Every allowance that
    /// fires is printed ("audit allowance N"), so a run's log shows what was
    /// excused.
    ///
    /// 1. Contrast on text under the tab bar. The bar is drawn over the
    ///    page, and the audit measures the text behind it against the bar's
    ///    backing. The same text is measured normally once it scrolls clear
    ///    of the bar. When the audit attaches an element, its frame must
    ///    overlap the bar. In a `List` (Search, About) it sometimes attaches
    ///    no element to the text of the rows under the bar. Those issues
    ///    are allowed only up to the number of text elements lying under
    ///    the bar, less any already allowed by frame. Measured on the same
    ///    screens: on some runs Search reported 3 issues with no element and
    ///    About 1. On other runs it attached the same 3 to the three texts
    ///    of the one row under the bar ("100 días para enamorarse", "Yes",
    ///    "· Telefe") and that 1 to About's LezWatch.TV credit under the
    ///    bar. With `.subdued` sabotaged to a 60% gray, Search reported 19
    ///    with no element, over the bound, and failed.
    /// 2. Contrast on an element resting within `tabBarBand` points above
    ///    the bar, and only when its own pixels measure at least 4.5:1 (see
    ///    `renderedContrast`). Seen on the show screen: a character row's
    ///    show-title subtitle ("#1 Happy Family USA", `.subdued` #404040 on
    ///    white, about 10:1 in the audit's own element screenshot) was
    ///    reported as "Contrast failed" when it sat just above the bar, and
    ///    passed in the same row one position higher. Text that really is
    ///    low-contrast measures under 4.5:1 and still fails.
    /// 3. "Dynamic Type font sizes are partially unsupported" on the About
    ///    rows in `aboutRowsThatScale`. They are plain list rows in `.body`,
    ///    and `testAboutRowsTheAuditQuestionsDoScaleWithDynamicType` measures
    ///    each one growing at the largest text size. If one stops scaling,
    ///    that test fails. Any other element with the finding still fails.
    ///    Adding an explicit `.font(.body)` did not change the finding. Only
    ///    rows whose accessibility label is their own text get it; list rows
    ///    with a custom label do not. The audit appears to misread list-row
    ///    text; Apple's forums report the same.
    /// 4. The system search field, which the app does not lay out (UIKit's
    ///    UISearchBarTextField from `.searchable`): clipped text on the
    ///    field, and the hit area of its "Clear text" button (20 x 20 pt).
    ///
    /// The audit runs once two reads of the accessibility tree agree
    /// (`waitForStillScreen`), so it does not measure a screen
    /// mid-animation.
    ///
    /// Contrast runs as its own audit, first, then the other checks. Run
    /// together with them, the audit reports its contrast issues with no
    /// element: measured on the filtered Search results, 4 of 4 contrast
    /// issues came with no element in one `.all` audit, and all 4 came with
    /// their element in a `.contrast` audit of the same screen a moment
    /// later. With no element, an issue can only be excused by counting texts
    /// under the tab bar (allowance 1). With its element, each is held to the
    /// rule for where it is: over the bar (allowance 1, by frame), just above
    /// it and measured from its own pixels at 4.5:1 or better (allowance 2),
    /// or failed.
    ///
    /// First, so contrast is measured on the still screen a person sees,
    /// before any other check has worked on it. Measured: with contrast run
    /// after the other checks, CI (run 35407156681) reported the character
    /// screen's navigation title "Gina" as "Contrast failed for UILabel", the
    /// only failure of that run. That title is a standard inline navigation
    /// title in the system's colors, and the same test passed in two CI runs
    /// whose audit measured contrast together with everything else
    /// (35421286344 and 35422900625). The second pass waits for a still
    /// screen again, so it is not measured while the first pass's effects
    /// settle.
    @MainActor
    private func audit(_ app: XCUIApplication, _ types: XCUIAccessibilityAuditType = .all) throws {
        waitForStillScreen(app)
        let tabBar = app.tabBars.firstMatch
        let tabBarFrame = tabBar.exists ? tabBar.frame : .null
        let searchField = app.searchFields.firstMatch
        let searchFieldFrame = searchField.exists ? searchField.frame : .null
        var underBarBudget = tabBarFrame.isNull ? 0 : Self.textsUnderTabBar(app, tabBarFrame)
        let passes: [XCUIAccessibilityAuditType] = types.contains(.contrast)
            ? [.contrast, types.subtracting(.contrast)].filter { !$0.isEmpty }
            : [types]
        for (index, checks) in passes.enumerated() {
            if index > 0 { waitForStillScreen(app) }
            let budgetBeforePass = underBarBudget
            try runPass(app, checks, resetting: { underBarBudget = budgetBeforePass }) { issue in
                guard let element = issue.element, element.exists else {
                    if issue.auditType == .contrast, underBarBudget > 0 {
                        underBarBudget -= 1
                        print("audit allowance 1: \(issue.compactDescription) with no element; \(underBarBudget) more allowed under the tab bar \(tabBarFrame)")
                        return true
                    }
                    print("audit issue: \(issue.compactDescription) | \(issue.detailedDescription) | no element")
                    return false
                }
                let frame = element.frame
                switch issue.auditType {
                case .contrast where !tabBarFrame.isNull && frame.intersects(tabBarFrame):
                    underBarBudget = max(0, underBarBudget - 1)
                    print("audit allowance 1: \(issue.compactDescription) on \(Self.describe(element)); tab bar \(tabBarFrame)")
                    return true
                case .contrast where !tabBarFrame.isNull
                    && frame.maxY <= tabBarFrame.minY && frame.maxY > tabBarFrame.minY - Self.tabBarBand:
                    if let ratio = Self.renderedContrast(of: element), ratio >= 4.5 {
                        print("audit allowance 2: \(issue.compactDescription) on \(Self.describe(element)); drawn at \(String(format: "%.1f", ratio)):1")
                        return true
                    }
                case .dynamicType where Self.aboutRowsThatScale.contains(where: { $0.type == element.elementType && $0.label == element.label }):
                    print("audit allowance 3: \(issue.compactDescription) on \(Self.describe(element))")
                    return true
                case .textClipped where element.elementType == .searchField,
                     .hitRegion where element.elementType == .button && element.label == "Clear text"
                        && !searchFieldFrame.isNull && searchFieldFrame.contains(frame):
                    print("audit allowance 4: \(issue.compactDescription) on \(Self.describe(element))")
                    return true
                default:
                    break
                }
                print("audit issue: \(issue.compactDescription) | \(issue.detailedDescription) | \(Self.describe(element))")
                return false
            }
        }
    }

    /// Runs one audit pass. The audit can stop without a verdict: it reports
    /// "Audit failed to complete in time" (code -56). Measured in CI, on the
    /// first-run screen after it was scrolled: it happened in runs 35399628927,
    /// 35422900625 and 35450246601, and the same test passed in runs 35407156681
    /// and 35421286344, with no reported issue in any of them; the run that
    /// timed out last also needed 44 s to launch the app for another test. So
    /// it tracks a slow runner, not the screen. That error is no finding:
    /// nothing was judged. So that one error, and only it, runs the same pass
    /// once more on a still screen. Every issue the audit does report is
    /// judged as before and is never retried, and a second timeout fails the
    /// test.
    /// `resetting` puts the allowance counters back, so the second run is
    /// judged from the same starting point as the first.
    @MainActor
    private func runPass(
        _ app: XCUIApplication,
        _ checks: XCUIAccessibilityAuditType,
        resetting reset: () -> Void,
        issueHandler: @escaping (XCUIAccessibilityAuditIssue) throws -> Bool
    ) throws {
        let started = Date()
        do {
            try app.performAccessibilityAudit(for: checks, issueHandler)
        } catch let error as NSError where Self.isAuditTimeout(error) {
            print("audit: \(Self.checksLabel(checks)) pass stopped without a verdict after \(String(format: "%.1f", Date().timeIntervalSince(started))) s (\(error.code)); running it once more on a still screen")
            waitForStillScreen(app)
            reset()
            try app.performAccessibilityAudit(for: checks, issueHandler)
        }
        print("audit: \(Self.checksLabel(checks)) pass took \(String(format: "%.1f", Date().timeIntervalSince(started))) s")
    }

    static func checksLabel(_ checks: XCUIAccessibilityAuditType) -> String {
        checks == .contrast ? "contrast" : "non-contrast (\(checks.rawValue))"
    }

    /// `XCUIAccessibilityAuditError`'s "did not complete in time" (-56).
    static func isAuditTimeout(_ error: NSError) -> Bool {
        error.domain == "com.apple.xcode.xctest.accessibilityAudit" && error.code == -56
    }

    /// How far above the tab bar allowance 2 reaches, in points.
    static let tabBarBand: CGFloat = 24

    /// Allowance 1's bound: text elements with no text children (so a
    /// combined row label is not counted on top of its parts) whose frames
    /// overlap the tab bar's frame. The bar's own items are not counted.
    @MainActor
    static func textsUnderTabBar(_ app: XCUIApplication, _ bar: CGRect) -> Int {
        guard let root = try? app.snapshot() else { return 0 }
        var count = 0
        func walk(_ element: XCUIElementSnapshot) {
            if element.elementType == .tabBar { return }
            let leafText = element.elementType == .staticText
                && !element.children.contains { $0.elementType == .staticText }
            if leafText, element.frame.intersects(bar) { count += 1 }
            element.children.forEach(walk)
        }
        walk(root)
        return count
    }

    /// Waits until two reads of the accessibility tree half a second apart
    /// agree on every element's type, label and frame, up to 10 seconds.
    @MainActor
    private func waitForStillScreen(_ app: XCUIApplication) {
        func fingerprint(_ element: XCUIElementSnapshot) -> String {
            "\(element.elementType.rawValue)|\(element.label)|\(element.frame);"
                + element.children.map(fingerprint).joined()
        }
        var previous = ""
        let deadline = Date().addingTimeInterval(10)
        while Date() < deadline {
            let current = (try? app.snapshot()).map(fingerprint) ?? ""
            if !current.isEmpty, current == previous { return }
            previous = current
            Thread.sleep(forTimeInterval: 0.5)
        }
        print("audit: the screen was still changing after 10 s; auditing anyway")
    }

    /// The About rows under allowance 3, by element type and label.
    static let aboutRowsThatScale: [(type: XCUIElement.ElementType, label: String)] = [
        (.staticText, "That file is served by GitHub Pages, which, like any web server, sees your IP address and logs it for security. The developer never sees that log."),
        (.staticText, "Favorites are stored only on this device and are never sent anywhere."),
        (.button, "Privacy policy"),
        (.button, "Support"),
    ]

    /// The contrast ratio between the darkest and lightest pixels of an
    /// element as drawn (WCAG relative luminance). For a text element, its
    /// text against its background.
    @MainActor
    static func renderedContrast(of element: XCUIElement) -> Double? {
        guard let image = element.screenshot().image.cgImage, image.width > 0, image.height > 0 else { return nil }
        let width = image.width, height = image.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        let drawn = pixels.withUnsafeMutableBytes { buffer -> Bool in
            guard let context = CGContext(
                data: buffer.baseAddress, width: width, height: height, bitsPerComponent: 8,
                bytesPerRow: width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
            ) else { return false }
            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard drawn else { return nil }
        return contrast(ofRGBA: pixels)
    }

    /// WCAG contrast between the darkest and lightest pixels of RGBA bytes.
    static func contrast(ofRGBA pixels: [UInt8]) -> Double {
        func linear(_ byte: UInt8) -> Double {
            let c = Double(byte) / 255
            return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
        }
        var darkest = 1.0, lightest = 0.0
        for i in stride(from: 0, to: pixels.count - 3, by: 4) {
            let l = 0.2126 * linear(pixels[i]) + 0.7152 * linear(pixels[i + 1]) + 0.0722 * linear(pixels[i + 2])
            darkest = min(darkest, l)
            lightest = max(lightest, l)
        }
        return (lightest + 0.05) / (darkest + 0.05)
    }

    /// Names the element an issue is on, so a red run says what to fix.
    @MainActor
    private static func describe(_ element: XCUIElement) -> String {
        "type \(element.elementType.rawValue), label '\(element.label)', id '\(element.identifier)', value '\(element.value ?? "")', frame \(element.frame)"
    }

    @MainActor
    private func launch(textSize: String? = nil, arguments: [String] = []) -> XCUIApplication {
        let app = XCUIApplication.guide()
        if let textSize {
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", textSize]
        }
        app.launchArguments += arguments
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30))
        return app
    }

    /// Search → filter to shows with a where-to-watch link → first show.
    @MainActor @discardableResult
    private func openFirstShow(_ app: XCUIApplication) -> Bool {
        app.applyWhereToWatchFilter()
        let firstRow = app.firstShowRow
        guard firstRow.waitForExistence(timeout: 30) else { XCTFail("filter produced no rows"); return false }
        firstRow.tap()
        let heading = app.staticTexts["Do any queer characters die?"]
        if !heading.waitForExistence(timeout: 15), firstRow.exists, firstRow.isHittable {
            // Measured: on a loaded machine the filter sheet can still be
            // closing when the row is tapped, and that tap is lost. One more
            // tap on the same row; the assertion below is unchanged.
            firstRow.tap()
        }
        return heading.waitForExistence(timeout: 30)
    }

    /// Opens the filter sheet from Search and waits for it. Measured in CI:
    /// on a slow runner the tap on Filter was lost, the sheet never opened,
    /// and the test went on to audit the results behind it. One more tap when
    /// the sheet has not appeared and the button is still there to tap; the
    /// assertion that the sheet is open is unchanged.
    @MainActor
    private func openFilterSheet(_ app: XCUIApplication) {
        let filter = app.buttons["Filter"]
        XCTAssertTrue(filter.waitForExistence(timeout: 30), "no Filter button")
        filter.tap()
        let worthIt = app.buttons["Worth it: Yes"]
        if !worthIt.waitForExistence(timeout: 10), filter.exists, filter.isHittable {
            filter.tap()
        }
        XCTAssertTrue(worthIt.waitForExistence(timeout: 10), "the filter sheet did not open")
    }

    /// The filter sheet, its trope picker, and the active-filters row and
    /// empty state it leads to.
    @MainActor
    func testFilterSheetAndItsResultsPassTheAudit() throws {
        let app = launch()
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30), "the catalog did not load")
        openFilterSheet(app)
        try audit(app)

        // Tropes: a searchable list of choices, none of them death-revealing.
        let tropes = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Tropes'")).firstMatch
        for _ in 0..<4 where !(tropes.exists && tropes.isHittable) { app.swipeUp() }
        tropes.tap()
        XCTAssertTrue(app.navigationBars["Tropes"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Bury Your Queers'")).firstMatch.exists, "a death-revealing trope is offered")
        try audit(app)
        let firstTrope = app.buttons.matching(identifier: "filter-term").firstMatch
        XCTAssertTrue(firstTrope.waitForExistence(timeout: 10))
        firstTrope.tap()
        XCTAssertTrue(firstTrope.isSelected, "picking a trope does not mark it selected")
        // Back to the filter sheet (the Tropes bar's own back button, not a
        // button on the Search bar under the sheet).
        app.navigationBars["Tropes"].buttons.element(boundBy: 0).tap()

        app.buttons["filters-show-results"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH '1 filter on'")).firstMatch.waitForExistence(timeout: 30), "no active-filters row")
        XCTAssertTrue(app.firstShowRow.waitForExistence(timeout: 30))
        try audit(app)
    }

    /// A search that matches nothing with a filter on: the empty state says
    /// so and offers to search without filters.
    @MainActor
    func testNoMatchesWithFiltersPassesTheAudit() throws {
        let app = launch()
        app.applyWhereToWatchFilter()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 30))
        search.tap()
        search.typeText("zzzzqqq\n")
        XCTAssertTrue(app.staticTexts["No matches with these filters"].waitForExistence(timeout: 30))
        let without = app.buttons["Search without filters"]
        XCTAssertTrue(without.exists)
        try audit(app)
        without.tap()
        XCTAssertTrue(app.staticTexts["No matches"].waitForExistence(timeout: 30), "clearing the filters did not leave the plain empty state")
    }

    /// The filter sheet at the largest text size: nothing clipped, every
    /// font scales.
    @MainActor
    func testLargestTextSizeFilterSheetPassesDynamicTypeAndClippingAudits() throws {
        let app = launch(textSize: "UICTContentSizeCategoryAccessibilityXXXL")
        openFilterSheet(app)
        try audit(app, [.dynamicType, .textClipped])
        // The bottom of the form, where the results button sits at these
        // sizes.
        let showResults = app.buttons["filters-show-results"]
        for _ in 0..<12 where !(showResults.exists && showResults.isHittable) { app.swipeUp() }
        XCTAssertTrue(showResults.isHittable, "the results button is out of reach")
        try audit(app, [.dynamicType, .textClipped])
    }

    @MainActor
    func testSearchScreenPassesTheAudit() throws {
        let app = launch()
        // Audit the loaded catalog, not the "Loading catalog" state.
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30), "the catalog did not load")
        try audit(app)
    }

    /// Search with a query: character and show rows, a short list with
    /// nothing under the tab bar.
    @MainActor
    func testSearchResultsPassTheAudit() throws {
        let reference = try BundledDeaths.character(recordedDeath: true)
        let app = launch()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 30))
        search.tap()
        search.typeText(reference.name)
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "\(reference.name), from ")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30), "no search result for \(reference.name)")
        // Submit, so the keyboard (system UI, not the app's) is down.
        search.typeText("\n")
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        try audit(app)
    }

    @MainActor
    func testShowScreenPassesTheAuditBeforeAndAfterTheReveal() throws {
        let app = launch()
        XCTAssertTrue(openFirstShow(app), "did not reach a show screen")
        try audit(app)

        let reveal = app.buttons["Reveal"].firstMatch
        XCTAssertTrue(reveal.waitForExistence(timeout: 10))
        reveal.tap()
        // The answer fades in (unless Reduce Motion is on); auditing
        // mid-fade measures a half-transparent frame. Wait for the button
        // to go and the fade to finish.
        XCTAssertTrue(reveal.waitForNonExistence(timeout: 10))
        Thread.sleep(forTimeInterval: 1)
        try audit(app)
    }

    @MainActor
    func testCharacterScreenPassesTheAudit() throws {
        let app = launch()
        XCTAssertTrue(openFirstShow(app), "did not reach a show screen")
        // The first character link below the "Characters" heading.
        let characters = app.staticTexts["Characters"]
        XCTAssertTrue(characters.waitForExistence(timeout: 10))
        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", ", from ")).firstMatch
        if !row.exists { app.swipeUp() }
        guard row.waitForExistence(timeout: 10) else {
            throw XCTSkip("the first filtered show lists no characters in this snapshot")
        }
        row.tap()
        XCTAssertTrue(app.buttons["Reveal"].waitForExistence(timeout: 30))
        try audit(app)
    }

    @MainActor
    func testFavoritesAndAboutPassTheAudit() throws {
        let app = launch()
        app.tabBars.buttons["Favorites"].tap()
        XCTAssertTrue(app.staticTexts["No favorites yet"].waitForExistence(timeout: 30))
        try audit(app)

        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
        // The sections below Privacy appear once the snapshot has loaded.
        XCTAssertTrue(app.staticTexts["Data sources"].waitForExistence(timeout: 30))
        try audit(app)
    }

    // MARK: Data freshness and favorites backup (#25)

    /// Mirrors `DataFreshnessBanner.identifier`.
    static let freshnessWarningIdentifier = "data-freshness-warning"

    /// With the clock pinned years after any snapshot (a Debug-only launch
    /// argument, `AppModel.uiTestClock`), Search opens with the out-of-date
    /// warning. It is one element that VoiceOver reads as a warning, and
    /// the screen still passes the audit.
    @MainActor
    func testStaleDataWarningIsReadAsAWarningAndPassesTheAudit() throws {
        let app = launch(arguments: ["-UITestClock", "2031-01-01T00:00:00Z"])
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30), "the catalog did not load")
        let warning = app.descendants(matching: .any)[Self.freshnessWarningIdentifier]
        XCTAssertTrue(warning.waitForExistence(timeout: 10), "no out-of-date warning with the clock in 2031")
        XCTAssertTrue(warning.label.hasPrefix("Warning. This data is out of date. It was last updated "), warning.label)
        // The pinned clock landed: the age is counted in days, not hours.
        XCTAssertTrue(warning.label.contains(" days ago, on "), warning.label)
        try audit(app)
    }

    /// A clock set before the snapshot was built: the age is unknown, and
    /// the app says so rather than calling the data current.
    @MainActor
    func testUnknownDataAgeIsStatedNotShownAsCurrent() throws {
        let app = launch(arguments: ["-UITestClock", "2020-01-01T00:00:00Z"])
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30), "the catalog did not load")
        let warning = app.descendants(matching: .any)[Self.freshnessWarningIdentifier]
        XCTAssertTrue(warning.waitForExistence(timeout: 10), "no warning with the clock in 2020")
        XCTAssertTrue(warning.label.hasPrefix("Warning. This data's age is unknown. "), warning.label)
        XCTAssertFalse(Self.opensWithNo(warning.label), warning.label)
    }

    /// The Favorites screen's backup menu: an icon button VoiceOver names
    /// "Back up or restore favorites", offering Export (unavailable while
    /// there is nothing to export) and Import. The screen itself is audited
    /// by `testFavoritesAndAboutPassTheAudit`.
    @MainActor
    func testFavoritesBackUpMenuIsLabeledForVoiceOver() throws {
        let app = launch()
        app.tabBars.buttons["Favorites"].tap()
        XCTAssertTrue(app.staticTexts["No favorites yet"].waitForExistence(timeout: 30))
        let menu = app.buttons["Back up or restore favorites"]
        XCTAssertTrue(menu.waitForExistence(timeout: 10), "no backup menu button")
        menu.tap()
        let export = app.buttons["Export favorites"]
        XCTAssertTrue(export.waitForExistence(timeout: 10), "the menu has no Export item")
        XCTAssertFalse(export.isEnabled, "Export is offered with nothing to export")
        XCTAssertTrue(app.buttons["Import favorites"].exists, "the menu has no Import item")
    }

    /// The evidence behind allowance 3 in `audit`: each About row the audit
    /// reports as "partially unsupported" grows by at least half again at
    /// the largest accessibility text size. A row set in a fixed font keeps
    /// its height and fails here. Measured 2026-09-18: "Favorites are
    /// stored…" 72 pt at the default size, 132 pt already at Accessibility M.
    @MainActor
    func testAboutRowsTheAuditQuestionsDoScaleWithDynamicType() throws {
        let sizes = ["UICTContentSizeCategoryL", "UICTContentSizeCategoryAccessibilityXXXL"]
        let heights = sizes.map { size -> [String: CGFloat] in
            let app = launch(textSize: size)
            app.tabBars.buttons["About"].tap()
            XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
            var found: [String: CGFloat] = [:]
            for _ in 0..<15 {
                for row in Self.aboutRowsThatScale where found[row.label] == nil {
                    // A predicate, not a subscript: subscripts refuse
                    // strings over 128 characters.
                    let element = app.descendants(matching: row.type)
                        .matching(NSPredicate(format: "label == %@", row.label)).firstMatch
                    if element.exists { found[row.label] = element.frame.height }
                }
                if found.count == Self.aboutRowsThatScale.count { break }
                app.swipeUp()
            }
            app.terminate()
            return found
        }
        XCTAssertEqual(Self.aboutRowsThatScale.count, 4, "the denominator")
        for row in Self.aboutRowsThatScale {
            guard let small = heights[0][row.label], let large = heights[1][row.label] else {
                XCTFail("\"\(row.label)\" not found at both text sizes: \(heights)")
                continue
            }
            XCTAssertGreaterThan(large, small * 1.5, "\"\(row.label)\" did not grow with Dynamic Type (\(small) pt, then \(large) pt)")
        }
    }

    /// The first-run screen, top and bottom, at the default text size.
    @MainActor
    func testFirstRunScreenPassesTheAudit() throws {
        let app = launchFirstRun()
        try audit(app)
        let finish = app.buttons["onboarding-finish"]
        for _ in 0..<6 where !finish.isHittable { app.swipeUp() }
        XCTAssertTrue(finish.isHittable, "Start browsing is out of reach")
        try audit(app)
    }

    /// The first-run screen at the largest text size: it scrolls, nothing
    /// is clipped, every font scales.
    @MainActor
    func testLargestTextSizeFirstRunScreenPassesDynamicTypeAndClippingAudits() throws {
        let app = launchFirstRun(textSize: "UICTContentSizeCategoryAccessibilityXXXL")
        try audit(app, [.dynamicType, .textClipped])
        let finish = app.buttons["onboarding-finish"]
        for _ in 0..<12 where !finish.isHittable { app.swipeUp() }
        XCTAssertTrue(finish.isHittable, "Start browsing is out of reach at the largest text size")
        try audit(app, [.dynamicType, .textClipped])
    }

    @MainActor
    private func launchFirstRun(textSize: String? = nil) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-onboarding.v1.seen", "NO"]
        if let textSize {
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", textSize]
        }
        app.launch()
        XCTAssertTrue(app.staticTexts["onboarding-point-spoilers"].waitForExistence(timeout: 30), "no first-run screen")
        return app
    }

    /// The largest accessibility text size: nothing clipped, every font
    /// scales. Show screen, where the most text is.
    @MainActor
    func testLargestTextSizeShowScreenPassesDynamicTypeAndClippingAudits() throws {
        let app = launch(textSize: "UICTContentSizeCategoryAccessibilityXXXL")
        XCTAssertTrue(openFirstShow(app), "did not reach a show screen")
        try audit(app, [.dynamicType, .textClipped])
    }

    static let largestTextSize = "UICTContentSizeCategoryAccessibilityXXXL"

    /// The largest accessibility text size on the other tabs: Search's
    /// catalog, Favorites and About. Nothing clipped, every font scales.
    @MainActor
    func testLargestTextSizeSearchFavoritesAndAboutPassDynamicTypeAndClippingAudits() throws {
        let app = launch(textSize: Self.largestTextSize)
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30), "the catalog did not load")
        try audit(app, [.dynamicType, .textClipped])

        // Empty or not: a simulator that ran other UI tests may already hold
        // favorites, and both states must pass.
        app.tabBars.buttons["Favorites"].tap()
        XCTAssertTrue(app.navigationBars["Favorites"].waitForExistence(timeout: 30))
        try audit(app, [.dynamicType, .textClipped])

        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
        try audit(app, [.dynamicType, .textClipped])
    }

    /// Search results (a character and its show) at the largest text size.
    @MainActor
    func testLargestTextSizeSearchResultsPassDynamicTypeAndClippingAudits() throws {
        let reference = try BundledDeaths.character(recordedDeath: true)
        let app = launch(textSize: Self.largestTextSize)
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 30))
        search.tap()
        search.typeText(reference.name + "\n")
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "\(reference.name), from ")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30), "no search result for \(reference.name)")
        try audit(app, [.dynamicType, .textClipped])
    }

    /// The character screen at the largest text size, reveal closed.
    @MainActor
    func testLargestTextSizeCharacterScreenPassesDynamicTypeAndClippingAudits() throws {
        let reference = try BundledDeaths.character(recordedDeath: false)
        let app = launch(textSize: Self.largestTextSize)
        openCharacter(reference, app)
        XCTAssertTrue(app.buttons["Reveal"].waitForExistence(timeout: 30))
        try audit(app, [.dynamicType, .textClipped])
    }

    /// VoiceOver hears a show's years, seasons and networks as one stop, in
    /// words: never "en dash" or "middle dot" read out of the punctuation.
    @MainActor
    func testShowFactsAreOneVoiceOverStopInWords() throws {
        let app = launch()
        XCTAssertTrue(openFirstShow(app), "did not reach a show screen")
        let facts = app.descendants(matching: .any)
            .matching(NSPredicate(format: "label CONTAINS 'season' OR label CONTAINS 'Seasons not recorded'")).firstMatch
        XCTAssertTrue(facts.waitForExistence(timeout: 10), "no years-and-seasons element")
        XCTAssertFalse(facts.label.contains("·"), facts.label)
        XCTAssertFalse(facts.label.contains("–"), facts.label)
        XCTAssertTrue(facts.label.hasSuffix("."), facts.label)
    }

    // MARK: Spoiler safety under VoiceOver
    //
    // VoiceOver reads the accessibility tree, not the pixels. A reveal that
    // only hides its answer visually (opacity, blur, a cover view) still
    // lets VoiceOver read it aloud. These tests read the whole tree before
    // the reveal is opened and fail if the answer, or a death-revealing tag,
    // is anywhere in it.

    /// A character with a recorded death, and the show it appears in: the
    /// closed reveal on both screens must keep the answer out of the tree.
    @MainActor
    func testClosedDeathRevealsAreNotInTheAccessibilityTree() throws {
        let reference = try BundledDeaths.character(recordedDeath: true)
        let app = launch()
        openCharacter(reference, app)

        let characterAnswer = try revealAfterCheckingItWasClosed(app, question: "Does \(reference.name) die?", spoilerTerms: reference.spoilerTerms)
        XCTAssertTrue(characterAnswer.hasPrefix("Yes. "), "a recorded death must read as yes: \(characterAnswer)")

        openShow(of: reference, app)
        let showAnswer = try revealAfterCheckingItWasClosed(app, question: "Do any queer characters die?", spoilerTerms: reference.spoilerTerms)
        XCTAssertTrue(showAnswer.contains(reference.name), "the show's answer must name \(reference.name): \(showAnswer)")
    }

    /// A character with no recorded death, in a show where no listed
    /// character has one: both answers read "Not recorded", never "No".
    @MainActor
    func testUnknownDeathsReadAsNotRecordedNeverNo() throws {
        let reference = try BundledDeaths.character(recordedDeath: false)
        let app = launch()
        openCharacter(reference, app)

        let characterAnswer = try revealAfterCheckingItWasClosed(app, question: "Does \(reference.name) die?", spoilerTerms: reference.spoilerTerms)
        XCTAssertTrue(characterAnswer.hasPrefix("Not recorded."), characterAnswer)
        XCTAssertFalse(Self.opensWithNo(characterAnswer), characterAnswer)

        openShow(of: reference, app)
        let showAnswer = try revealAfterCheckingItWasClosed(app, question: "Do any queer characters die?", spoilerTerms: reference.spoilerTerms)
        XCTAssertTrue(showAnswer.hasPrefix("Not recorded."), showAnswer)
        XCTAssertFalse(Self.opensWithNo(showAnswer), showAnswer)
    }

    /// The checks themselves: the sentence splitter keeps what identifies a
    /// death and drops the bare verdicts, and the "No" detector does not
    /// fire on "Not".
    func testTheSpoilerChecksCanFail() {
        XCTAssertEqual(Self.revealingSentences(of: "Yes. Adam Torres dies (2013)."), ["Adam Torres dies (2013)"])
        XCTAssertEqual(
            Self.revealingSentences(of: "Not recorded. This snapshot does not record a death for Alex."),
            ["This snapshot does not record a death for Alex"]
        )
        let leakedTree = ["Characters", "Adam Torres, from Degrassi", "Adam Torres dies (2013)."]
        XCTAssertEqual(Self.leaks(of: "Yes. Adam Torres dies (2013).", in: leakedTree), ["Adam Torres dies (2013)"])
        XCTAssertEqual(Self.leaks(of: "Yes. Adam Torres dies (2013).", in: Array(leakedTree.prefix(2))), [])
        XCTAssertTrue(Self.opensWithNo("No death is recorded for Alex."))
        XCTAssertFalse(Self.opensWithNo("Not recorded. This snapshot does not record a death for Alex."))
    }

    /// Allowance 2's pixel measure: #404040 text on white (the app's
    /// `.subdued`) clears 4.5:1; the system `.secondary` gray (#8A8A8E) on
    /// white does not.
    func testTheRenderedContrastMeasureCanFail() {
        func pixels(_ a: UInt8, _ b: UInt8) -> [UInt8] { [a, a, a, 255, b, b, b, 255] }
        XCTAssertGreaterThan(Self.contrast(ofRGBA: pixels(0x40, 0xFF)), 4.5)
        XCTAssertLessThan(Self.contrast(ofRGBA: pixels(0x8A, 0xFF)), 4.5)
        XCTAssertEqual(Self.contrast(ofRGBA: pixels(0x00, 0xFF)), 21, accuracy: 0.01)
    }

    /// Asserts the reveal under `question` is closed and that nothing
    /// VoiceOver can read gives its answer away, then opens it and returns
    /// the answer VoiceOver reads.
    @MainActor
    private func revealAfterCheckingItWasClosed(_ app: XCUIApplication, question: String, spoilerTerms: [String]) throws -> String {
        XCTAssertTrue(app.staticTexts[question].waitForExistence(timeout: 30), "no \"\(question)\" heading")
        let answer = app.descendants(matching: .any)[Self.answerIdentifier]
        let reveal = app.buttons["Reveal"].firstMatch
        XCTAssertTrue(reveal.waitForExistence(timeout: 10), "the reveal is not closed")
        XCTAssertFalse(answer.exists, "the closed answer is in the accessibility tree")

        let closedTree = try Self.readableText(app)
        XCTAssertGreaterThan(closedTree.count, 5, "the tree read came back nearly empty, so it proves nothing")
        for term in spoilerTerms {
            let hits = closedTree.filter { $0.localizedCaseInsensitiveContains(term) }
            XCTAssertEqual(hits, [], "the death-revealing tag \"\(term)\" is readable before the reveal")
        }

        reveal.tap()
        XCTAssertTrue(answer.waitForExistence(timeout: 10), "the reveal did not open")
        let spoken = answer.label
        XCTAssertFalse(spoken.isEmpty, "the answer has no VoiceOver label")
        XCTAssertFalse(Self.revealingSentences(of: spoken).isEmpty, "nothing to check in \"\(spoken)\"")
        XCTAssertEqual(Self.leaks(of: spoken, in: closedTree), [], "readable before the reveal was opened")
        return spoken
    }

    @MainActor
    private func openCharacter(_ reference: BundledDeaths.Reference, _ app: XCUIApplication) {
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 30))
        search.tap()
        search.typeText(reference.name)
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "\(reference.name), from ")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30), "no search result for \(reference.name)")
        row.tap()
    }

    /// From the character screen, the "Appears in" link to its one show.
    @MainActor
    private func openShow(of reference: BundledDeaths.Reference, _ app: XCUIApplication) {
        let link = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", reference.showTitle)).firstMatch
        if !(link.exists && link.isHittable) { app.swipeUp() }
        XCTAssertTrue(link.waitForExistence(timeout: 10), "no link to \(reference.showTitle)")
        link.tap()
    }

    /// Mirrors `SpoilerReveal.answerIdentifier` (the UI-test target does not
    /// link the app's sources).
    static let answerIdentifier = "spoiler-answer"

    /// Every label, value, title and placeholder in the app's accessibility
    /// tree: what VoiceOver can read on this screen, visible or not.
    @MainActor
    private static func readableText(_ app: XCUIApplication) throws -> [String] {
        var text: [String] = []
        func walk(_ element: XCUIElementSnapshot) {
            let fields = [element.label, element.title, element.placeholderValue ?? "", (element.value as? String) ?? ""]
            text += fields.filter { !$0.isEmpty }
            element.children.forEach(walk)
        }
        walk(try app.snapshot())
        return text
    }

    /// The sentences of an answer that say something about a death, without
    /// the bare verdicts ("Yes", "Not recorded") that also appear elsewhere.
    static func revealingSentences(of answer: String) -> [String] {
        answer
            .components(separatedBy: ". ")
            .map { $0.trimmingCharacters(in: CharacterSet(charactersIn: ". ")) }
            .filter { !$0.isEmpty && $0 != "Yes" && $0 != "Not recorded" }
    }

    /// The answer's sentences that some element in `tree` already says.
    static func leaks(of answer: String, in tree: [String]) -> [String] {
        revealingSentences(of: answer).filter { sentence in tree.contains { $0.contains(sentence) } }
    }

    /// True when `text` opens with the word "No" (not "Not", "None", …).
    static func opensWithNo(_ text: String) -> Bool {
        text.range(of: #"^\s*No\b"#, options: [.regularExpression, .caseInsensitive]) != nil
    }
}

/// Reference characters read from the bundled snapshot the app under test
/// ships, so the tests hold for whatever snapshot `make bundle-snapshot`
/// fetched rather than hard-coding a name.
private enum BundledDeaths {
    struct Reference {
        let name: String
        let showTitle: String
        /// Names of the tags whose presence answers "does she die" (the
        /// cliché slug `dead`, the trope slug `dead-queers`; GuideCore's
        /// `Presentation.deathSpoiler*Slugs`).
        let spoilerTerms: [String]
    }

    static let bundledSnapshot = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent() // QueerTVGuideUITests
        .deletingLastPathComponent() // ios
        .appendingPathComponent("QueerTVGuide/Resources/snapshot.v1.json")

    /// The lowest-id character whose name is unique and is not also a show
    /// title, who appears in exactly one show, and whose death is recorded
    /// (`recordedDeath`) or not. For the not-recorded case, no listed
    /// character in that show has a recorded death either, so the show's
    /// answer is "Not recorded" too.
    static func character(recordedDeath: Bool) throws -> Reference {
        let data = try Data(contentsOf: bundledSnapshot)
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let shows = try XCTUnwrap(root["shows"] as? [[String: Any]])
        let characters = try XCTUnwrap(root["characters"] as? [[String: Any]])

        func died(_ c: [String: Any]) -> Bool { (c["death"] as? [String: Any])?["died"] as? Bool == true }
        func showIDs(_ c: [String: Any]) -> [String] { ((c["shows"] as? [[String: Any]]) ?? []).compactMap { $0["show_id"] as? String } }
        func number(_ c: [String: Any]) -> Int { Int((c["id"] as? String ?? "").split(separator: ":").last ?? "") ?? .max }
        func termNames(_ items: Any?, slug: String) -> [String] {
            ((items as? [[String: Any]]) ?? []).filter { $0["slug"] as? String == slug }.compactMap { $0["name"] as? String }
        }

        let titles = Dictionary(shows.compactMap { s in (s["id"] as? String).map { ($0, s["title"] as? String ?? "") } }, uniquingKeysWith: { a, _ in a })
        let allTitles = Set(titles.values)
        var nameCount: [String: Int] = [:]
        var showsWithADeath: Set<String> = []
        for c in characters {
            nameCount[c["name"] as? String ?? "", default: 0] += 1
            if died(c) { showsWithADeath.formUnion(showIDs(c)) }
        }
        let spoilerTerms = Set(
            characters.flatMap { termNames($0["cliches"], slug: "dead") } + shows.flatMap { termNames($0["tropes"], slug: "dead-queers") }
        )
        XCTAssertFalse(spoilerTerms.isEmpty, "no death-revealing tag in the snapshot to check for")

        let candidate = characters
            .filter { c in
                guard let name = c["name"] as? String, nameCount[name] == 1, !allTitles.contains(name) else { return false }
                let ids = showIDs(c)
                guard ids.count == 1, let title = titles[ids[0]], !title.isEmpty else { return false }
                return recordedDeath ? died(c) : (!died(c) && !showsWithADeath.contains(ids[0]))
            }
            .min { number($0) < number($1) }
        let c = try XCTUnwrap(candidate, "no reference character (recordedDeath: \(recordedDeath)) in the bundled snapshot")
        return Reference(
            name: try XCTUnwrap(c["name"] as? String),
            showTitle: try XCTUnwrap(titles[showIDs(c)[0]]),
            spoilerTerms: spoilerTerms.sorted()
        )
    }
}
