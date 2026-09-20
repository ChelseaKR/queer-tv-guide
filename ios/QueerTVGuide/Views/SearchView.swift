import SwiftUI
import GuideCore

struct SearchView: View {
    @Environment(AppModel.self) private var model
    @State private var query = ""
    @State private var filters = SearchIndex.Filters()

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Search")
                .searchable(text: $query, prompt: "Shows or characters")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) { filterMenu }
                }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch model.loadState {
        case .loading:
            ProgressView("Loading catalogue…")
                .accessibilityLabel("Loading catalogue")
        case .failed(let message):
            EmptyState(title: "Couldn't load the catalogue", systemImage: "exclamationmark.triangle", message: message)
        case .loaded:
            if let index = model.searchIndex, let snapshot = model.snapshot {
                resultsList(index: index, snapshot: snapshot)
            }
        }
    }

    @ViewBuilder
    private func resultsList(index: SearchIndex, snapshot: Snapshot) -> some View {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        let searchResults: SearchIndex.SearchResults = trimmed.isEmpty
            ? SearchIndex.SearchResults(hits: index.browse(filters: filters).map { .show($0) }, totalCount: 0)
            : index.search(trimmed, filters: filters)

        List {
            if searchResults.hits.isEmpty {
                Section {
                    EmptyState(
                        title: trimmed.isEmpty ? "Browse or search" : "No matches",
                        systemImage: "magnifyingglass",
                        message: trimmed.isEmpty ? "Search for a show or character, or turn on a filter to browse." : "Nothing in this snapshot matches \u{201c}\(trimmed)\u{201d}."
                    )
                }
                .listRowSeparator(.hidden)
            } else {
                if searchResults.isCapped {
                    Section {
                        Text("Showing the first \(searchResults.hits.count) of \(searchResults.totalCount) matches. Type more to narrow them.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .accessibilityLabel("Showing the first \(searchResults.hits.count) of \(searchResults.totalCount) matches")
                    }
                }
                Section {
                    ForEach(searchResults.hits) { hit in
                        hitRow(hit, snapshot: snapshot)
                    }
                }
            }
            Section {
                DataStatusFooter(generatedAt: snapshot.generatedAt, refreshError: model.lastRefreshError)
            }
        }
        .listStyle(.plain)
        .refreshable { await model.refresh() }
    }

    @ViewBuilder
    private func hitRow(_ hit: SearchIndex.Hit, snapshot: Snapshot) -> some View {
        switch hit {
        case .show(let show):
            NavigationLink {
                ShowDetailView(showID: show.id)
            } label: {
                ShowRow(show: show)
            }
        case .character(let character):
            NavigationLink {
                CharacterDetailView(characterID: character.id)
            } label: {
                CharacterRow(character: character, snapshot: snapshot)
            }
        }
    }

    private var filterMenu: some View {
        Menu {
            Section("Worth it") {
                ForEach(WorthIt.allCases, id: \.self) { value in
                    Toggle(value.rawValue, isOn: Binding(
                        get: { filters.worthIt.contains(value) },
                        set: { on in
                            if on { filters.worthIt.insert(value) } else { filters.worthIt.remove(value) }
                        }
                    ))
                }
            }
            Toggle("No recorded deaths", isOn: $filters.noRecordedDeaths)
            Toggle("Has a where-to-watch link", isOn: $filters.hasWatchLink)
            if !filters.isEmpty {
                Button("Clear filters", role: .destructive) { filters = SearchIndex.Filters() }
            }
        } label: {
            Label("Filter", systemImage: filters.isEmpty ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
        }
        .accessibilityLabel(filters.isEmpty ? "Filter" : "Filter (active)")
    }
}
