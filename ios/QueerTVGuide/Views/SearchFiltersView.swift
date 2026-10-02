import SwiftUI
import GuideCore

/// Every browse filter on one screen: worth it, where to watch, tropes,
/// trigger warnings and recorded deaths. Changes apply as they are made;
/// the results button says how many shows the choice leaves.
///
/// A scroll view of plain rows, not a `Form`: in a form, Xcode's
/// accessibility audit reported switch labels as not scaling and section
/// headers as low-contrast under the navigation bar, where the same text in
/// a scroll view (as on the show screen) passes.
struct SearchFiltersView: View {
    @Binding var filters: SearchIndex.Filters
    let index: SearchIndex

    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var matchingShows: Int { index.browse(filters: filters).count }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    if !filters.isEmpty {
                        Button("Clear all filters", role: .destructive) { filters = SearchIndex.Filters() }
                            .buttonStyle(.bordered)
                    }

                    FilterGroup(title: "Worth it", footer: "LezWatch.TV's verdict. Shows it has not rated are left out while any of these is on.") {
                        ForEach(WorthIt.allCases, id: \.self) { value in
                            // "No, selected" says nothing on its own.
                            CheckRow(title: value.rawValue, spoken: "Worth it: \(value.rawValue)", isOn: binding(for: value, in: \.worthIt))
                        }
                    }

                    FilterGroup(title: "Where to watch") {
                        CheckRow(title: "Has a where-to-watch link", isOn: $filters.hasWatchLink)
                        NavigationLink {
                            FilterTermPicker(
                                title: "Where to watch",
                                explanation: "Shows with a link to any site you pick.",
                                terms: index.filterOptions.watchHosts.map { .init(id: $0.key, name: $0.key, showCount: $0.showCount) },
                                selection: $filters.watchHosts
                            )
                        } label: {
                            PickerRow(title: "Sites", count: filters.watchHosts.count)
                        }
                    }

                    FilterGroup(title: "Tropes") {
                        NavigationLink {
                            FilterTermPicker(
                                title: "Tropes",
                                explanation: "Shows tagged with any trope you pick. Tropes that give away a death are not listed.",
                                terms: index.filterOptions.tropes.map { .init(id: $0.slug, name: $0.name, showCount: $0.showCount) },
                                selection: $filters.tropes
                            )
                        } label: {
                            PickerRow(title: "Tropes", count: filters.tropes.count)
                        }
                    }

                    if !index.filterOptions.triggerWarnings.isEmpty {
                        FilterGroup(
                            title: "Trigger warnings",
                            footer: "LezWatch.TV rates some shows' trigger warnings \(index.filterOptions.triggerWarnings.map(\.name).joined(separator: ", ")). Shows with no rating listed are always kept."
                        ) {
                            ForEach(index.filterOptions.triggerWarnings) { level in
                                CheckRow(title: "Hide shows rated \(level.name)", isOn: binding(for: level.slug, in: \.hiddenTriggerWarnings))
                            }
                        }
                    }

                    FilterGroup(
                        title: "Deaths",
                        footer: "Shows whose listed queer characters have no recorded death. A show with no listed characters is left out, because that is not the same as nobody dying."
                    ) {
                        CheckRow(title: "No recorded deaths", isOn: $filters.noRecordedDeaths)
                    }

                    // At accessibility text sizes the results button ends the
                    // page: pinned, it covered a quarter of the screen.
                    if dynamicTypeSize.isAccessibilitySize {
                        showResultsButton
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .legibleTopScrollEdge()
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                // An icon, like Filter on Search: the audit reports a text
                // toolbar button as not scaling with Dynamic Type. The system
                // shows its title in the Large Content Viewer, and VoiceOver
                // reads "Done".
                ToolbarItem(placement: .topBarTrailing) {
                    Button { dismiss() } label: {
                        Label("Done", systemImage: "checkmark")
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                if !dynamicTypeSize.isAccessibilitySize {
                    // Opaque, not the translucent `.bar` material: text
                    // scrolling under the translucent bar showed through
                    // at low contrast (the audit measured the trigger-
                    // warning note there).
                    VStack(spacing: 0) {
                        Divider()
                        showResultsButton
                            .padding()
                    }
                    .background(Color(uiColor: .systemBackground))
                }
            }
        }
    }

    private var showResultsButton: some View {
        Button {
            dismiss()
        } label: {
            Text(Self.showResultsTitle(matchingShows))
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .accessibilityIdentifier("filters-show-results")
    }

    static func showResultsTitle(_ count: Int) -> String {
        count == 1 ? "Show 1 show" : "Show \(count.formatted()) shows"
    }

    private func binding<Value: Hashable>(for value: Value, in keyPath: WritableKeyPath<SearchIndex.Filters, Set<Value>>) -> Binding<Bool> {
        Binding(
            get: { filters[keyPath: keyPath].contains(value) },
            set: { on in
                if on { filters[keyPath: keyPath].insert(value) } else { filters[keyPath: keyPath].remove(value) }
            }
        )
    }
}

/// A heading, its rows, and an optional note under them.
private struct FilterGroup<Content: View>: View {
    let title: String
    var footer: String? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
                .padding(.bottom, 4)
            content()
            if let footer {
                Text(footer)
                    .font(.footnote)
                    .foregroundStyle(.subdued)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)
            }
        }
    }
}

/// A row that is on or off: a checkmark and its text, the whole row one
/// button. VoiceOver reads it as selected or not.
struct CheckRow: View {
    let title: String
    /// A count after the title, e.g. how many shows carry a trope.
    var detail: String? = nil
    /// What VoiceOver reads, when the text alone needs its heading.
    var spoken: String? = nil
    @Binding var isOn: Bool

    var body: some View {
        Button {
            isOn.toggle()
        } label: {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(isOn ? AnyShapeStyle(.accessibleAccent) : AnyShapeStyle(.subdued))
                    .accessibilityHidden(true)
                Text(title)
                    .foregroundStyle(Color.primary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                if let detail {
                    Text(detail)
                        .foregroundStyle(.subdued)
                }
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(spoken ?? title)
        .accessibilityInputLabels([title])
        .accessibilityAddTraits(isOn ? .isSelected : [])
    }
}

/// "Sites" and how many are picked, read as one phrase by VoiceOver.
private struct PickerRow: View {
    let title: String
    let count: Int

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let value = count == 0 ? "Any" : "\(count) picked"
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 2))
            : AnyLayout(HStackLayout(spacing: 8))
        HStack(spacing: 8) {
            layout {
                Text(title).foregroundStyle(Color.primary)
                if !dynamicTypeSize.isAccessibilitySize { Spacer(minLength: 8) }
                Text(value).foregroundStyle(.subdued)
            }
            Image(systemName: "chevron.forward")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.subdued)
                .accessibilityHidden(true)
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(count == 0 ? "\(title), any" : "\(title), \(count) picked")
        .accessibilityInputLabels([title])
        .accessibilityAddTraits(.isButton)
    }
}

/// A searchable multiple-choice list of taxonomy terms or sites, each with
/// how many shows carry it.
struct FilterTermPicker: View {
    struct Term: Identifiable, Hashable {
        let id: String
        let name: String
        let showCount: Int
    }

    let title: String
    let explanation: String
    let terms: [Term]
    @Binding var selection: Set<String>

    @State private var query = ""

    private var visible: [Term] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return terms }
        return terms.filter { $0.name.localizedCaseInsensitiveContains(q) }
    }

    var body: some View {
        ScrollView {
            // A plain stack: at most ~120 rows, and a lazy one left rows
            // below the first screen reported by the audit as not scaling.
            VStack(alignment: .leading, spacing: 4) {
                Text(explanation)
                    .font(.footnote)
                    .foregroundStyle(.subdued)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 8)
                ForEach(visible) { term in
                    CheckRow(
                        title: term.name,
                        detail: term.showCount.formatted(),
                        spoken: "\(term.name), \(term.showCount) \(term.showCount == 1 ? "show" : "shows")",
                        isOn: Binding(
                            get: { selection.contains(term.id) },
                            set: { on in if on { selection.insert(term.id) } else { selection.remove(term.id) } }
                        )
                    )
                    .accessibilityIdentifier("filter-term")
                }
                if visible.isEmpty {
                    Text("Nothing listed matches “\(query)”.")
                        .foregroundStyle(.subdued)
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .legibleTopScrollEdge()
        .navigationTitle(title)
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Find in \(title.lowercased())")
        .toolbar {
            if !selection.isEmpty {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { selection.removeAll() } label: {
                        Label("Clear", systemImage: "xmark.circle")
                    }
                }
            }
        }
    }
}

extension View {
    /// The top-edge twin of `legibleScrollEdges()` (AccessibleStyle.swift):
    /// iOS 26 fades content scrolling under a navigation bar, and the audit
    /// measured a heading in that band as low-contrast.
    @ViewBuilder
    func legibleTopScrollEdge() -> some View {
        if #available(iOS 26.0, *) {
            scrollEdgeEffectStyle(.hard, for: .top)
        } else {
            self
        }
    }
}
