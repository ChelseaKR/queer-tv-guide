import SwiftUI
import GuideCore

/// "A failed refresh keeps the last good one and shows its generated_at
/// date" — this is where that shows up on every screen that reads the
/// snapshot, with how long ago that was. When the data is past its 48-hour
/// SLA, or its age cannot be known, the first line says so at full
/// contrast (DG-04, #25): it is never left to the date alone.
struct DataStatusFooter: View {
    @Environment(AppModel.self) private var model
    let snapshot: Snapshot

    var body: some View {
        let freshness = model.freshness(of: snapshot)
        VStack(alignment: .leading, spacing: 2) {
            if let warning = Presentation.freshnessWarning(generatedAt: snapshot.generatedAt, freshness: freshness) {
                Text("\(warning.title).")
                    .font(.caption.weight(.semibold))
            }
            Text(Presentation.dataAsOf(snapshot.generatedAt, freshness: freshness))
                .font(.caption)
                .foregroundStyle(.subdued)
            if let refreshError = model.lastRefreshError {
                Text("Refresh failed: \(refreshError)")
                    .font(.caption)
                    .foregroundStyle(.subdued)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
