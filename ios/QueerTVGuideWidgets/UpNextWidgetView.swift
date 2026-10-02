import GuideCore
import SwiftUI
import UIKit
import WidgetKit

// The widget's views, apart from its `@main` bundle so the app's unit tests
// can compile and render them (WidgetRenderTests).

struct UpNextEntry: TimelineEntry {
    let date: Date
    /// `nil` until the app has written its first file.
    let upNext: UpNext?
}

struct UpNextWidgetView: View {
    let entry: UpNextEntry
    /// Set only by the render tests, which have no widget host to supply it.
    var familyOverride: WidgetFamily? = nil

    @Environment(\.widgetFamily) private var environmentFamily

    private var family: WidgetFamily { familyOverride ?? environmentFamily }

    /// How many shows fit: one on the small widget, three on the medium.
    private var capacity: Int { family == .systemSmall ? 1 : 3 }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            header
            if let upNext = entry.upNext {
                if upNext.items.isEmpty && upNext.missingShowCount == 0 {
                    message(UpNextPresentation.noFavoriteShows)
                } else {
                    rows(upNext)
                }
                Spacer(minLength: 0)
                footer(upNext)
            } else {
                message(UpNextPresentation.notLoaded)
                Spacer(minLength: 0)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        // A widget is a fixed canvas: past this size its titles truncate to
        // a few letters. The whole list, at any text size, is one tap away
        // in the app.
        .dynamicTypeSize(...DynamicTypeSize.xxLarge)
        .containerBackground(.background, for: .widget)
    }

    private var header: some View {
        Label(UpNextPresentation.title, systemImage: "star.fill")
            .font(.caption.weight(.semibold))
            .foregroundStyle(WidgetColors.accent)
            .accessibilityAddTraits(.isHeader)
    }

    private func message(_ text: String) -> some View {
        Text(text)
            .font(.footnote)
            .foregroundStyle(WidgetColors.subdued)
            .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder
    private func rows(_ upNext: UpNext) -> some View {
        let ordered = upNext.ordered(today: entry.date)
        ForEach(ordered.prefix(capacity)) { item in
            row(item)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(UpNextPresentation.spoken(item, today: entry.date))
        }
        if let more = UpNextPresentation.more(ordered.count - capacity, missing: upNext.missingShowCount) {
            Text(more)
                .font(.caption2)
                .foregroundStyle(WidgetColors.subdued)
        }
    }

    /// Small: the title over its episode line. Medium: one line each, the
    /// title giving way first.
    @ViewBuilder
    private func row(_ item: UpNext.Item) -> some View {
        let line = Text(UpNextPresentation.line(item, today: entry.date))
            .font(.caption)
            .foregroundStyle(WidgetColors.subdued)
        if family == .systemSmall {
            VStack(alignment: .leading, spacing: 1) {
                Text(item.title)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(2)
                line.lineLimit(2)
            }
        } else {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(item.title)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Spacer(minLength: 4)
                line
                    .lineLimit(1)
                    .layoutPriority(1)
            }
        }
    }

    /// The data's date, always, and TVmaze's credit whenever a schedule is
    /// shown: stacked on the small widget, one line on the medium.
    private func footer(_ upNext: UpNext) -> some View {
        let age = UpNextPresentation.dataAge(upNext.snapshotGeneratedAt, now: entry.date)
        let stale = UpNextPresentation.freshness(of: upNext.snapshotGeneratedAt, now: entry.date) != .current
        let credit = upNext.items.isEmpty ? nil : UpNextPresentation.tvmazeCredit
        let layout = family == .systemSmall
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 0))
            : AnyLayout(HStackLayout(spacing: 4))
        return layout {
            Text(age)
                .fontWeight(stale ? .semibold : .regular)
            if let credit {
                if family != .systemSmall {
                    Text("·").accessibilityHidden(true)
                }
                Text(credit)
            }
        }
        .font(.caption2)
        .foregroundStyle(WidgetColors.subdued)
        .lineLimit(1)
        .minimumScaleFactor(0.8)
        .accessibilityElement(children: .combine)
    }

    /// Invented titles for the widget gallery, never real data.
    static let sample = UpNext(
        snapshotGeneratedAt: Date(),
        items: [
            UpNext.Item(showID: "sample:1", title: "Your favorite show", status: .dated, season: 2, number: 3,
                        airdate: sampleAirdate),
            UpNext.Item(showID: "sample:2", title: "Another favorite", status: .noneListed),
        ],
        missingShowCount: 0
    )

    private static var sampleAirdate: String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        return f.string(from: Date().addingTimeInterval(3 * 24 * 60 * 60))
    }
}

/// The app's contrast-checked colors (`AccessibleStyle.swift`, where the
/// measurements are), repeated here because the widget is its own module.
enum WidgetColors {
    static let accent = Color(uiColor: UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(red: 0.45, green: 0.72, blue: 1.0, alpha: 1)
            : UIColor(red: 0.0, green: 0.34, blue: 0.70, alpha: 1)
    })

    static let subdued = Color(uiColor: UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(white: 0.78, alpha: 1)
            : UIColor(white: 0.25, alpha: 1)
    })
}
