import SwiftUI
import GuideCore

/// The warning at the top of a list when the snapshot is older than its
/// 48-hour SLA, or its age cannot be known (DG-04, #25). Plain words, in
/// the body colour at full contrast, above the content it affects: data
/// past its SLA is never shown as current.
///
/// One VoiceOver element whose label opens with "Warning", so the whole
/// message is read together and its first word says what it is.
struct DataFreshnessBanner: View {
    /// For UI tests. Not spoken by VoiceOver.
    static let identifier = "data-freshness-warning"

    let warning: Presentation.FreshnessWarning

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.body)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(warning.title)
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
                Text(warning.detail)
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(warning.spoken)
        .accessibilityIdentifier(Self.identifier)
    }
}
