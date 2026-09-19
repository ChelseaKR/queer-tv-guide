import SwiftUI
import GuideCore

struct SearchView: View {
    @Environment(AppModel.self) private var model
    @State private var query = ""
    @State private var filters = SearchIndex.Filters()
    @State private var showingFilters = false
    /// The hits for `results.key`, worked out off the main thread so typing
    /// never waits on a pass over ~9,600 shows and characters.
    @State private var results = Results()

    /// What the hits depend on. A change starts a new pass and cancels the
    /// one before it.
    struct Key: Equatable {
        var query: String
        var filters: SearchIndex.Filters
        var generatedAt: Date?
    }

    struct Results {
        var key: Key?
        var hits: [SearchIndex.Hit] = []
    }

    private var trimmedQuery: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var key: Key { Key(query: trimmedQuery, filters: filters, generatedAt: model.snapshot?.generatedAt) }

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Search")
                .searchable(text: $query, prompt: "Shows, characters, actors")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) { filterButton }
                }
                .sheet(isPresented: $showingFilters) {
                    if let index = model.searchIndex {
                        SearchFiltersView(filters: $filters, index: index)
                    }
                }
                .task(id: key) { await updateResults(for: key) }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch model.loadState {
        case .loading:
            ProgressView("Loading catalog…")
                .accessibilityLabel("Loading catalog")
        case .failed(let message):
            EmptyState(title: "Couldn't load the catalog", systemImage: "exclamationmark.triangle", message: message)
        case .loaded:
            if let snapshot = model.snapshot {
                resultsList(snapshot: snapshot)
            }
        }
    }

    private func updateResults(for key: Key) async {
        guard let index = model.searchIndex else { return }
        let hits = await Task.detached(priority: .userInitiated) {
            key.query.isEmpty
                ? index.browse(filters: key.filters).map { SearchIndex.Hit.show($0) }
                : index.search(key.query, filters: key.filters)
        }.value
        guard !Task.isCancelled else { return }
        results = Results(key: key, hits: hits)
    }

    @ViewBuilder
    private func resultsList(snapshot: Snapshot) -> some View {
        let hits = results.hits
        let settled = results.key == key
        List {
            // DG-04: data past its SLA, or of unknown age, says so above
            // everything it could be wrong about.
            if let warning = model.freshnessWarning(for: snapshot) {
                Section {
                    DataFreshnessBanner(warning: warning)
                }
            }
            if !filters.isEmpty {
                Section {
                    activeFiltersRow(count: settled ? hits.count : nil)
                }
            }
            if settled, hits.isEmpty {
                Section {
                    emptyState
                }
                .listRowSeparator(.hidden)
            } else {
                Section {
                    ForEach(hits) { hit in
                        hitRow(hit, snapshot: snapshot)
                    }
                }
            }
            Section {
                DataStatusFooter(snapshot: snapshot)
            }
        }
        .listStyle(.plain)
        .refreshable { await model.refresh() }
    }

    /// Above the results while any filter is on: how many there are, and a
    /// way to change or clear the filters without hunting for the button.
    private func activeFiltersRow(count: Int?) -> some View {
        HStack(spacing: 12) {
            Button {
                showingFilters = true
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text(Self.filterSummary(filters.activeCount))
                        .font(.subheadline.weight(.semibold))
                    if let count {
                        Text(trimmedQuery.isEmpty ? Self.showCount(count) : Self.matchCount(count))
                            .font(.subheadline)
                            .foregroundStyle(.subdued)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
            }
            // Two buttons in one list row: without their own styles, a tap
            // anywhere in the row would fire both.
            .buttonStyle(.borderless)
            .accessibilityHint("Opens the filters")
            Button("Clear") { filters = SearchIndex.Filters() }
                .buttonStyle(.bordered)
                .accessibilityLabel("Clear filters")
                .accessibilityInputLabels(["Clear", "Clear filters"])
        }
    }

    @ViewBuilder
    private var emptyState: some View {
        let q = trimmedQuery
        if q.isEmpty {
            EmptyState(
                title: "No shows match these filters",
                systemImage: "line.3.horizontal.decrease.circle",
                message: "Turn a filter off to see more."
            )
            Button("Clear filters") { filters = SearchIndex.Filters() }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
        } else if !filters.isEmpty {
            EmptyState(
                title: "No matches with these filters",
                systemImage: "magnifyingglass",
                message: "Nothing matches “\(q)” with \(Self.filterSummary(filters.activeCount).lowercased())."
            )
            Button("Search without filters") { filters = SearchIndex.Filters() }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
        } else {
            EmptyState(
                title: "No matches",
                systemImage: "magnifyingglass",
                message: "Nothing in this snapshot matches “\(q)”. Try part of a title, a character's name, an actor or a network."
            )
        }
    }

    static func filterSummary(_ active: Int) -> String {
        active == 1 ? "1 filter on" : "\(active) filters on"
    }

    static func showCount(_ count: Int) -> String {
        count == 1 ? "1 show" : "\(count.formatted()) shows"
    }

    /// Search returns at most 50 hits, so a full page says "top 50".
    static func matchCount(_ count: Int) -> String {
        switch count {
        case 1: return "1 match"
        case 50...: return "Top \(count) matches"
        default: return "\(count) matches"
        }
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

    private var filterButton: some View {
        Button {
            showingFilters = true
        } label: {
            Label("Filter", systemImage: filters.isEmpty ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
        }
        .disabled(model.searchIndex == nil)
        .accessibilityLabel(filters.isEmpty ? "Filter" : "Filter (\(Self.filterSummary(filters.activeCount)))")
    }
}
