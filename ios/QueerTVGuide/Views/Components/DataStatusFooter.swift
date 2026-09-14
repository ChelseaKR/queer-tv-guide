import SwiftUI
import GuideCore

/// "A failed refresh keeps the last good one and shows its generated_at
/// date" — this is where that shows up on every screen that reads the
/// snapshot.
struct DataStatusFooter: View {
    let generatedAt: Date
    let refreshError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(Presentation.generatedAt(generatedAt))
                .font(.caption)
                .foregroundStyle(.secondary)
            if let refreshError {
                Text("Refresh failed: \(refreshError)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
