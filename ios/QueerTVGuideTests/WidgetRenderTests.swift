import SwiftUI
import WidgetKit
import XCTest
import GuideCore

/// Draws the "Up Next" widget's views (compiled into this bundle from
/// QueerTVGuideWidgets/UpNextWidgetView.swift) at both sizes, in light and
/// dark, at the default and the largest text size, with real favorites from
/// the bundled snapshot. Each image is attached to the result, so a reviewer
/// can look at every state without adding the widget to a home screen.
///
/// The spoiler check here is on what the widget can show at all: its only
/// input is `UpNext`, whose fields `UpNextTests` pins.
@MainActor
final class WidgetRenderTests: XCTestCase {
    /// iPhone 17 Pro's widget sizes, in points.
    static let sizes: [(WidgetFamily, CGSize, String)] = [
        (.systemSmall, CGSize(width: 170, height: 170), "small"),
        (.systemMedium, CGSize(width: 364, height: 170), "medium"),
    ]

    private func realUpNext() throws -> UpNext {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"))
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: url))
        // Four shows with an upcoming episode, one never matched to TVmaze,
        // and one favorite the data no longer lists: every line the widget
        // can draw.
        let upcoming = snapshot.shows.filter { $0.schedule.nextEpisode?.airdateDay != nil }.prefix(4).map(\.id)
        let unknown = snapshot.shows.first { !$0.schedule.scheduleKnown }.map { [$0.id] } ?? []
        XCTAssertEqual(upcoming.count, 4, "the bundled snapshot lists fewer than 4 upcoming episodes")
        return UpNext(favoriteShowIDs: Array(upcoming) + unknown + ["lwtv:show:not-in-this-data"], snapshot: snapshot)
    }

    private func render(_ entry: UpNextEntry, family: WidgetFamily, size: CGSize, scheme: ColorScheme, type: DynamicTypeSize, name: String) throws {
        let view = UpNextWidgetView(entry: entry, familyOverride: family)
            .padding(16)
            .frame(width: size.width, height: size.height)
            .background(Color(uiColor: .systemBackground))
            .environment(\.colorScheme, scheme)
            .environment(\.dynamicTypeSize, type)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 3
        let image = try XCTUnwrap(renderer.uiImage, "\(name) did not render")
        XCTAssertEqual(image.size, size, name)
        let attachment = XCTAttachment(image: image)
        attachment.name = "widget-\(name)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func testEveryStateRendersAtBothSizesInBothAppearancesAndTextSizes() throws {
        let upNext = try realUpNext()
        let now = upNext.snapshotGeneratedAt.addingTimeInterval(3600)
        let states: [(String, UpNextEntry)] = [
            ("favorites", UpNextEntry(date: now, upNext: upNext)),
            ("stale", UpNextEntry(date: now.addingTimeInterval(5 * 24 * 3600), upNext: upNext)),
            ("empty", UpNextEntry(date: now, upNext: UpNext(snapshotGeneratedAt: upNext.snapshotGeneratedAt, items: [], missingShowCount: 0))),
            ("not-loaded", UpNextEntry(date: now, upNext: nil)),
        ]
        for (state, entry) in states {
            for (family, size, sizeName) in Self.sizes {
                for (scheme, schemeName) in [(ColorScheme.light, "light"), (.dark, "dark")] {
                    for (type, typeName) in [(DynamicTypeSize.large, "default"), (.accessibility5, "ax5")] {
                        try render(entry, family: family, size: size, scheme: scheme, type: type, name: "\(state)-\(sizeName)-\(schemeName)-\(typeName)")
                    }
                }
            }
        }
    }

    /// The gallery's sample is invented, never a real title.
    func testTheGallerySampleIsInvented() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"))
        let titles = Set(try SnapshotDecoder().decode(try Data(contentsOf: url)).shows.map(\.title))
        for item in UpNextWidgetView.sample.items {
            XCTAssertFalse(titles.contains(item.title), "\(item.title) is a real show")
        }
    }
}
