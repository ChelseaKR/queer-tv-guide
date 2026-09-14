import SwiftUI
import GuideCore

struct FavouritesView: View {
    @Environment(AppModel.self) private var model
    @State private var entries: [FavouritesStore.Entry] = []

    var body: some View {
        NavigationStack {
            Group {
                if let snapshot = model.snapshot {
                    if entries.isEmpty {
                        ContentUnavailableView(
                            "No favourites yet",
                            systemImage: "star",
                            description: Text("Tap the star on a show or character to save it here. Favourites stay on this device only.")
                        )
                    } else {
                        List {
                            ForEach(entries) { entry in
                                row(for: entry, snapshot: snapshot)
                            }
                            .onDelete(perform: remove)
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Favourites")
            .toolbar {
                if !entries.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) { EditButton() }
                }
            }
            .onAppear(perform: reload)
        }
    }

    @ViewBuilder
    private func row(for entry: FavouritesStore.Entry, snapshot: Snapshot) -> some View {
        switch entry.kind {
        case .show:
            if let show = snapshot.show(id: entry.id) {
                NavigationLink {
                    ShowDetailView(showID: show.id)
                } label: {
                    ShowRow(show: show)
                }
            } else {
                missingRow(label: "A favourited show is not in this snapshot.")
            }
        case .character:
            if let character = snapshot.character(id: entry.id) {
                NavigationLink {
                    CharacterDetailView(characterID: character.id)
                } label: {
                    CharacterRow(character: character, snapshot: snapshot)
                }
            } else {
                missingRow(label: "A favourited character is not in this snapshot.")
            }
        }
    }

    private func missingRow(label: String) -> some View {
        Text(label)
            .font(.subheadline)
            .foregroundStyle(.secondary)
    }

    private func reload() {
        entries = model.favourites.entries.sorted { $0.addedAt > $1.addedAt }
    }

    private func remove(at offsets: IndexSet) {
        for index in offsets {
            let entry = entries[index]
            model.favourites.remove(entry.kind, id: entry.id)
        }
        reload()
    }
}
