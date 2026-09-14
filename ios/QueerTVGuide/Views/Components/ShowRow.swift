import SwiftUI
import GuideCore

struct ShowRow: View {
    let show: Show

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(show.title)
                .font(.headline)
            HStack(spacing: 8) {
                Text(Presentation.worthIt(show.ratings.worthIt))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if !show.networks.isEmpty {
                    Text("· \(show.networks.map(\.name).joined(separator: ", "))")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(show.title). Worth it: \(Presentation.worthIt(show.ratings.worthIt)).")
    }
}

struct CharacterRow: View {
    let character: Character
    let snapshot: Snapshot

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
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(showTitles.isEmpty ? character.name : "\(character.name), from \(showTitles)")
    }
}
