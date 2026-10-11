import SwiftUI
import GuideCore

/// "A failed refresh keeps the last good one and shows its generated_at
/// date" — this is where that shows up on every screen that reads the
/// snapshot, with how long ago that was. When the data is past its 48-hour
/// SLA, or its age cannot be known, the first line says so at full
/// contrast (DG-04, #25): it is never left to the date alone.
///
/// A failed look for new data says which kind of failure it was (offline,
/// the server unreachable, or a file that failed its checks) and that the
/// data on screen is kept, with a Try again button: the same single GET as
/// pull to refresh, for anyone who does not use the gesture.
struct DataStatusFooter: View {
    /// For UI tests. Not spoken by VoiceOver.
    static let problemIdentifier = "data-refresh-problem"

    @Environment(AppModel.self) private var model
    let snapshot: Snapshot

    var body: some View {
        let freshness = model.freshness(of: snapshot)
        VStack(alignment: .leading, spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                if let warning = Presentation.freshnessWarning(generatedAt: snapshot.generatedAt, freshness: freshness) {
                    Text("\(warning.title).")
                        .font(.caption.weight(.semibold))
                }
                Text(Presentation.dataAsOf(snapshot.generatedAt, freshness: freshness))
                    .font(.caption)
                    .foregroundStyle(.subdued)
            }
            .accessibilityElement(children: .combine)
            if let problem = model.lastRefreshProblem {
                Text(problem.message)
                    .font(.caption)
                    .foregroundStyle(.subdued)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier(Self.problemIdentifier)
                Button {
                    Task { await model.requestedRefresh() }
                } label: {
                    if model.isRefreshing {
                        ProgressView()
                            .accessibilityLabel("Checking for new data")
                    } else {
                        Text("Try again")
                    }
                }
                .font(.subheadline.weight(.semibold))
                .buttonStyle(.bordered)
                .disabled(model.isRefreshing)
                .accessibilityHint("Checks once for a newer data file")
            }
        }
    }
}
