import SwiftUI
import GuideCore

struct FavouritesView: View {
    @Environment(AppModel.self) private var model
    @State private var entries: [FavouritesStore.Entry] = []
    @State private var showingReminderPrimer = false
    @State private var importing = false
    @State private var importOutcome: ImportOutcome?

    /// What an import did, or why it did nothing, for the alert.
    struct ImportOutcome {
        let title: String
        let message: String
    }

    var body: some View {
        NavigationStack {
            Group {
                if let snapshot = model.snapshot {
                    if entries.isEmpty {
                        EmptyState(
                            title: "No favourites yet",
                            systemImage: "star",
                            message: "Tap the star on a show or character to save it here. Favourites stay on this device. To move them to another one, use the … menu at the top of this screen to export a backup file, then import it there."
                        )
                    } else {
                        List {
                            // DG-04: next-episode dates below come from the
                            // snapshot; say so if it is past its SLA.
                            if let warning = model.freshnessWarning(for: snapshot) {
                                Section {
                                    DataFreshnessBanner(warning: warning)
                                }
                            }
                            Section {
                                ForEach(entries) { entry in
                                    row(for: entry, snapshot: snapshot)
                                }
                                .onDelete(perform: remove)
                            } footer: {
                                // Show rows carry TVmaze next-episode data;
                                // credit it here (CC BY-SA 4.0).
                                if entries.contains(where: { $0.kind == .show }),
                                   let credit = Attribution.tvmazeCredit(in: snapshot) {
                                    TVmazeCreditView(credit: credit)
                                }
                            }
                            // Off, and absent, unless the owner turns the
                            // feature on (FeatureFlags).
                            if FeatureFlags.episodeReminders, entries.contains(where: { $0.kind == .show }) {
                                RemindersSection(showingPrimer: $showingReminderPrimer)
                            }
                        }
                        // Pull for the latest next-episode dates: the same
                        // one GET as Search, nothing else.
                        .refreshable { await model.refresh() }
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Favourites")
            .toolbar {
                if model.snapshot != nil {
                    ToolbarItem(placement: .topBarLeading) { backupMenu }
                }
                if !entries.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) { EditButton() }
                }
            }
            .onAppear(perform: reload)
            // The explanation before the system's permission prompt. Only
            // "Turn on reminders" there asks iOS for permission.
            .sheet(isPresented: $showingReminderPrimer) {
                ReminderPrimingView { accepted in
                    showingReminderPrimer = false
                    guard accepted else { return }
                    Task { _ = await ReminderScheduler.enable(model) }
                }
            }
            .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { result in
                importBackup(result)
            }
            .alert(
                importOutcome?.title ?? "",
                isPresented: Binding(get: { importOutcome != nil }, set: { if !$0 { importOutcome = nil } }),
                presenting: importOutcome
            ) { _ in
                Button("OK", role: .cancel) {}
            } message: { outcome in
                Text(outcome.message)
            }
        }
    }

    /// Backup without a server or an account (DG-10, #25): export hands a
    /// JSON file to the share sheet, and the user chooses where it goes;
    /// import reads a file the user picks. Nothing is sent by the app.
    private var backupMenu: some View {
        Menu {
            ShareLink(
                item: FavouritesBackupFile(entries: entries),
                preview: SharePreview("Favourites backup")
            ) {
                Label("Export favourites", systemImage: "square.and.arrow.up")
            }
            .disabled(entries.isEmpty)
            .accessibilityHint(entries.isEmpty ? "No favourites to export yet" : "Saves your favourites to a file you choose where to keep")
            Button {
                importing = true
            } label: {
                Label("Import favourites", systemImage: "square.and.arrow.down")
            }
            .accessibilityHint("Adds favourites from a backup file")
        } label: {
            // An icon, like Filter on Search: the audit reports a text
            // toolbar label as not scaling with Dynamic Type. The system
            // shows the title in the Large Content Viewer at the largest
            // sizes, and VoiceOver reads it.
            Label("Back up or restore favourites", systemImage: "ellipsis.circle")
        }
    }

    private func importBackup(_ result: Result<URL, Error>) {
        let failed = "Couldn't import favourites"
        switch result {
        case .failure(let error):
            importOutcome = ImportOutcome(title: failed, message: error.localizedDescription)
        case .success(let url):
            // A file picked in Files is outside the sandbox until this
            // grant; read it once and let the grant go.
            let granted = url.startAccessingSecurityScopedResource()
            defer { if granted { url.stopAccessingSecurityScopedResource() } }
            do {
                // Mapped, so an oversized file is refused by size in
                // FavouritesBackup.parse without being read into memory.
                let data = try Data(contentsOf: url, options: .mappedIfSafe)
                let summary = try model.importFavourites(from: data)
                importOutcome = ImportOutcome(title: "Favourites imported", message: summary)
                reload()
            } catch {
                importOutcome = ImportOutcome(title: failed, message: error.localizedDescription)
            }
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
                    // "When's the next episode" for everything followed,
                    // at a glance.
                    ShowRow(show: show, detail: Presentation.nextEpisode(show.schedule))
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
            .foregroundStyle(.subdued)
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
