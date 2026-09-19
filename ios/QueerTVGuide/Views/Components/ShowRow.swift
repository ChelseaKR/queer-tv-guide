import SwiftUI
import GuideCore

struct ShowRow: View {
    let show: Show
    /// An extra line under the row, e.g. the next episode on Favorites.
    var detail: String? = nil

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    /// `.accessibilityElement(children: .combine)` plus an explicit
    /// `.accessibilityLabel` means the explicit label wins outright — none
    /// of the children's own text is appended. Earlier this label named
    /// only the title and worth-it verdict, so a sighted user saw the
    /// network (e.g. "· Example Network") but VoiceOver never heard it.
    /// This must restate everything the row shows, not just what's easy.
    private var accessibilitySummary: String {
        var summary = "\(show.title). Worth it: \(Presentation.worthIt(show.ratings.worthIt))."
        if !show.networks.isEmpty {
            summary += " \(show.networks.map(\.name).joined(separator: ", "))."
        }
        if let detail {
            summary += " \(detail)"
        }
        return summary
    }

    private var networks: String? {
        show.networks.isEmpty ? nil : show.networks.map(\.name).joined(separator: ", ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(show.title)
                .font(.headline)
            // At accessibility text sizes the verdict and network stack
            // instead of sharing a line, and the network is never truncated.
            if dynamicTypeSize.isAccessibilitySize {
                Text(Presentation.worthIt(show.ratings.worthIt))
                    .font(.subheadline)
                    .foregroundStyle(.subdued)
                if let networks {
                    Text(networks)
                        .font(.subheadline)
                        .foregroundStyle(.subdued)
                }
            } else {
                HStack(spacing: 8) {
                    Text(Presentation.worthIt(show.ratings.worthIt))
                        .font(.subheadline)
                        .foregroundStyle(.subdued)
                    if let networks {
                        Text("· \(networks)")
                            .font(.subheadline)
                            .foregroundStyle(.subdued)
                            .lineLimit(1)
                    }
                }
            }
            if let detail {
                Text(detail)
                    .font(.subheadline)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilitySummary)
    }
}

struct CharacterRow: View {
    let character: Character
    let snapshot: Snapshot

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var showTitles: String {
        character.shows.compactMap { snapshot.show(id: $0.showID)?.title }.joined(separator: ", ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(character.name)
                .font(.headline)
            if !showTitles.isEmpty {
                Text(showTitles)
                    .font(.subheadline)
                    .foregroundStyle(.subdued)
                    .lineLimit(dynamicTypeSize.isAccessibilitySize ? nil : 1)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(showTitles.isEmpty ? character.name : "\(character.name), from \(showTitles)")
    }
}
