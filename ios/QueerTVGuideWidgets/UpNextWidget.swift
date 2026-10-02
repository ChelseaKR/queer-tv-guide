import GuideCore
import SwiftUI
import WidgetKit

/// The home-screen widget: the next episode of each favorite show.
///
/// It reads one file the app writes into the shared App Group container
/// (`UpNext`), and nothing else: no network request, no snapshot, no death
/// data. Everything it says comes from `UpNextPresentation`, which the
/// GuideCore tests hold to the app's own rules (an unknown schedule is never
/// "nothing upcoming", a passed date is never shown as upcoming, and old
/// data says it is old).
@main
struct QueerTVGuideWidgets: WidgetBundle {
    var body: some Widget {
        UpNextWidget()
    }
}

struct UpNextWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: UpNext.widgetKind, provider: UpNextProvider()) { entry in
            UpNextWidgetView(entry: entry)
        }
        .configurationDisplayName("Up Next")
        .description("The next episode of each show you starred. Spoiler-free.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct UpNextProvider: TimelineProvider {
    private func read() -> UpNext? {
        guard let directory = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: UpNext.appGroupIdentifier) else { return nil }
        return UpNextStore(directory: directory).read()
    }

    func placeholder(in context: Context) -> UpNextEntry {
        UpNextEntry(date: Date(), upNext: UpNextWidgetView.sample)
    }

    func getSnapshot(in context: Context, completion: @escaping (UpNextEntry) -> Void) {
        // The widget gallery shows invented titles until the app has written
        // a file with real ones.
        let upNext = read() ?? (context.isPreview ? UpNextWidgetView.sample : nil)
        completion(UpNextEntry(date: Date(), upNext: upNext))
    }

    /// One entry now and one at each of the next seven UTC midnights, when a
    /// listed date can pass and the data can age past its freshness promise.
    /// The app asks for a new timeline whenever it writes a new file.
    func getTimeline(in context: Context, completion: @escaping (Timeline<UpNextEntry>) -> Void) {
        let upNext = read()
        let now = Date()
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let midnight = utc.startOfDay(for: now)
        let dates = [now] + (1...7).compactMap { utc.date(byAdding: .day, value: $0, to: midnight) }
        completion(Timeline(entries: dates.map { UpNextEntry(date: $0, upNext: upNext) }, policy: .atEnd))
    }
}
