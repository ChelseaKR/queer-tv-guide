import SwiftUI
import GuideCore

struct CharacterDetailView: View {
    let characterID: Character.ID

    @Environment(AppModel.self) private var model
    @Environment(\.openURL) private var openURL

    var body: some View {
        Group {
            if let snapshot = model.snapshot, let character = snapshot.character(id: characterID) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        header(character)
                        identity(character)
                        doesSheDie(character)
                        shows(character, snapshot: snapshot)
                        DataStatusFooter(generatedAt: snapshot.generatedAt, refreshError: model.lastRefreshError)
                    }
                    .padding()
                }
                .navigationTitle(character.name)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        FavouriteButton(kind: .character, id: character.id)
                    }
                }
            } else {
                EmptyState(title: "Character not found", systemImage: "questionmark.square.dashed")
            }
        }
    }

    private func header(_ character: Character) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(character.name)
                .font(.largeTitle.bold())
            if !character.actors.isEmpty {
                Text("Played by " + character.actors.compactMap(\.name).joined(separator: ", "))
                    .font(.subheadline)
                    .foregroundStyle(.subdued)
            }
            // LezWatch.TV's terms: link back (Attribution).
            LezWatchSourceLink(name: character.name, url: character.sourceURL)
        }
    }

    private func identity(_ character: Character) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let gender = character.gender {
                LabeledContent("Gender", value: gender.name)
            }
            if let sexuality = character.sexuality {
                LabeledContent("Sexuality", value: sexuality.name)
            }
            if let romantic = character.romantic {
                LabeledContent("Romantic orientation", value: romantic.name)
            }
            // "Dead Queers" would answer the question the reveal below
            // exists to keep closed; the reveal states the death instead.
            let cliches = Presentation.withoutSpoilers(character.cliches, Presentation.deathSpoilerClicheSlugs)
            if !cliches.isEmpty {
                LabeledContent("Tropes", value: cliches.map(\.name).joined(separator: ", "))
            }
        }
        .accessibilityElement(children: .combine)
    }

    /// The reveal itself: hidden until the user taps, per DECISIONS and the
    /// brief — "does she die" is a clear, respectful, spoiler-gated answer,
    /// never a fact the source doesn't actually assert (schema/README: no
    /// recorded death is never "she lives").
    private func doesSheDie(_ character: Character) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            // Named, not "she": LezWatch covers trans men and non-binary
            // characters too.
            Text("Does \(character.name) die?")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            SpoilerReveal(
                prompt: "Reveal",
                revealedHint: "Reveals whether a death is recorded for \(character.name) in this snapshot."
            ) {
                Text(Presentation.death(character.death, name: character.name))
                    .font(.body)
                    .accessibilityLabel(Presentation.death(character.death, name: character.name))
            }
        }
    }

    private func shows(_ character: Character, snapshot: Snapshot) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Appears in")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            ForEach(character.shows, id: \.showID) { link in
                if let show = snapshot.show(id: link.showID) {
                    NavigationLink {
                        ShowDetailView(showID: show.id)
                    } label: {
                        VStack(alignment: .leading) {
                            Text(show.title)
                            if let role = link.role {
                                Text(role.capitalized)
                                    .font(.caption)
                                    .foregroundStyle(.subdued)
                            }
                        }
                    }
                }
            }
        }
    }
}
