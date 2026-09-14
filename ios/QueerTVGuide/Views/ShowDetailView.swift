import SwiftUI
import GuideCore

struct ShowDetailView: View {
    let showID: Show.ID

    @Environment(AppModel.self) private var model
    @Environment(\.openURL) private var openURL

    var body: some View {
        Group {
            if let snapshot = model.snapshot, let show = snapshot.show(id: showID) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        header(show)
                        ratings(show)
                        schedule(show)
                        tropesAndTriggers(show)
                        characters(show, snapshot: snapshot)
                        whereToWatch(show)
                        plot(show)
                        attributionFooter(snapshot: snapshot)
                    }
                    .padding()
                }
                .navigationTitle(show.title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        FavouriteButton(kind: .show, id: show.id)
                    }
                }
            } else {
                ContentUnavailableView("Show not found", systemImage: "questionmark.square.dashed")
            }
        }
    }

    private func header(_ show: Show) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(show.title)
                .font(.largeTitle.bold())
            Text(Presentation.years(show.years) + " · " + Presentation.seasons(show.seasons))
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if !show.networks.isEmpty {
                Text(show.networks.map(\.name).joined(separator: ", "))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func ratings(_ show: Show) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ratings")
                .font(.headline)
            LabeledContent("Worth it", value: Presentation.worthIt(show.ratings.worthIt))
            LabeledContent("Quality", value: Presentation.ratingValue(show.ratings.quality))
            LabeledContent("Realness", value: Presentation.ratingValue(show.ratings.realness))
            LabeledContent("Screentime", value: Presentation.ratingValue(show.ratings.screentime))
            if let details = show.ratings.worthItDetails, !details.isEmpty {
                Text(details)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func schedule(_ show: Show) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Next episode")
                .font(.headline)
            Text(Presentation.nextEpisode(show.schedule))
                .font(.body)
        }
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func tropesAndTriggers(_ show: Show) -> some View {
        if !show.tropes.isEmpty || !show.triggers.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                if !show.tropes.isEmpty {
                    Text("Tropes").font(.headline)
                    Text(Presentation.terms(show.tropes, empty: Presentation.noTropes))
                }
                if !show.triggers.isEmpty {
                    Text("Trigger warnings").font(.headline)
                    Text(Presentation.terms(show.triggers, empty: Presentation.noTriggers))
                }
            }
        }
    }

    private func characters(_ show: Show, snapshot: Snapshot) -> some View {
        let cast = snapshot.characters(inShow: show.id)
        return VStack(alignment: .leading, spacing: 8) {
            Text("Characters")
                .font(.headline)
            if cast.isEmpty {
                Text(Presentation.noCharacters)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(cast) { character in
                    NavigationLink {
                        CharacterDetailView(characterID: character.id)
                    } label: {
                        CharacterRow(character: character, snapshot: snapshot)
                    }
                }
            }
        }
    }

    private func whereToWatch(_ show: Show) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Where to watch")
                .font(.headline)
            if show.watchLinks.isEmpty {
                Text(Presentation.noWatchLinks)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(show.watchLinks) { link in
                    // Link out only — this never plays or embeds video
                    // (App Review 5.2.3): openURL hands off to Safari.
                    Button {
                        openURL(link.url)
                    } label: {
                        Label(link.host, systemImage: "arrow.up.forward.square")
                    }
                    .accessibilityHint("Opens \(link.host) in Safari")
                }
            }
        }
    }

    @ViewBuilder
    private func plot(_ show: Show) -> some View {
        if let plot = show.notes.plot, !plot.isEmpty {
            DisclosureGroup("Plot notes (may contain spoilers)") {
                Text(plot)
                    .font(.callout)
            }
        }
    }

    private func attributionFooter(snapshot: Snapshot) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            ForEach(snapshot.attribution) { item in
                Button {
                    openURL(item.url)
                } label: {
                    Text(item.text)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.leading)
                }
            }
            DataStatusFooter(generatedAt: snapshot.generatedAt, refreshError: model.lastRefreshError)
        }
    }
}
