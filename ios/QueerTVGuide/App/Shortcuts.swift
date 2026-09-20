import AppIntents
import GuideCore

/// Siri can answer: "When is [show name] next episode?"
struct NextEpisodeIntent: AppIntent {
    static var title: LocalizedStringResource = "When Is Next Episode"
    static var description = IntentDescription("Tells you when a show's next episode airs.")

    @Parameter(title: "Show")
    var show: ShowEntity

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        guard let snapshot = await AppModel.shared.snapshot else {
            return .result(value: "No data loaded yet.", dialog: "The app hasn't loaded its data yet. Open Queer Frame first.")
        }
        guard let showByID = snapshot.show(id: show.id) else {
            return .result(value: "Show not found.", dialog: "I couldn't find that show.")
        }
        let answer = Presentation.nextEpisode(showByID.schedule)
        return .result(value: answer, dialog: "\(showByID.title): \(answer)")
    }
}

/// Siri can answer: "What queer shows are airing this week?"
struct QueerShowsThisWeekIntent: AppIntent {
    static var title: LocalizedStringResource = "Queer Shows This Week"
    static var description = IntentDescription("Lists queer shows with upcoming episodes this week.")

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        guard let snapshot = await AppModel.shared.snapshot else {
            return .result(value: "No data loaded yet.", dialog: "The app hasn't loaded its data yet. Open Queer Frame first.")
        }
        let showsWithUpcoming = snapshot.shows.filter { show in
            if let schedule = show.schedule.next, Calendar.current.isDate(schedule, equalTo: Date(), toGranularity: .weekOfYear) {
                return true
            }
            return false
        }
        if showsWithUpcoming.isEmpty {
            return .result(value: "No shows airing this week.", dialog: "No queer shows have episodes scheduled this week.")
        }
        let titles = showsWithUpcoming.prefix(5).map(\.title).joined(separator: ", ")
        let count = showsWithUpcoming.count
        let suffix = count > 5 ? " and \(count - 5) more" : ""
        return .result(value: titles + suffix, dialog: "This week: \(titles)\(suffix)")
    }
}

/// Siri can answer: "Search for shows with [actor name]"
struct SearchShowsByActorIntent: AppIntent {
    static var title: LocalizedStringResource = "Search Shows By Actor"
    static var description = IntentDescription("Finds queer shows featuring a specific actor.")

    @Parameter(title: "Actor Name")
    var actorName: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        guard let snapshot = await AppModel.shared.snapshot else {
            return .result(value: "No data loaded yet.", dialog: "The app hasn't loaded its data yet. Open Queer Frame first.")
        }
        let matchingShows = snapshot.characters.filter { character in
            character.actors.lowercased().contains(actorName.lowercased())
        }.compactMap { character in
            character.shows.compactMap { snapshot.show(id: $0.showID) }.first
        }
        if matchingShows.isEmpty {
            return .result(value: "No shows found.", dialog: "I couldn't find any shows with \(actorName).")
        }
        let titles = matchingShows.prefix(5).map(\.title).joined(separator: ", ")
        return .result(value: titles, dialog: "\(actorName) appears in: \(titles)")
    }
}

// MARK: - Entity

struct ShowEntity: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Show")
    static var defaultQuery = ShowQuery()

    var id: Show.ID
    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "Show \(id)")
    }
}

struct ShowQuery: EntityQuery {
    func entities(for identifiers: [Show.ID]) async throws -> [ShowEntity] {
        guard let snapshot = await AppModel.shared.snapshot else { return [] }
        return identifiers.compactMap { id in
            snapshot.show(id: id) != nil ? ShowEntity(id: id) : nil
        }
    }

    func suggestedEntities() async throws -> [ShowEntity] {
        guard let snapshot = await AppModel.shared.snapshot else { return [] }
        return snapshot.shows.prefix(20).map { ShowEntity(id: $0.id) }
    }
}

// MARK: - App Shortcuts

class QueerTVGuideShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: NextEpisodeIntent(),
            phrases: [
                "When is \(.applicationName) \(.show) next episode",
                "When does \(.show) air next",
                "Next episode of \(.show)"
            ],
            shortTitle: "Next Episode",
            systemImageName: "tv"
        )
        AppShortcut(
            intent: QueerShowsThisWeekIntent(),
            phrases: [
                "What \(.applicationName) shows are airing this week",
                "Queer shows this week",
                "What's airing this week on \(.applicationName)"
            ],
            shortTitle: "Shows This Week",
            systemImageName: "calendar"
        )
        AppShortcut(
            intent: SearchShowsByActorIntent(),
            phrases: [
                "Search \(.applicationName) for \(.actorName)",
                "What \(.applicationName) shows has \(.actorName) been in",
                "Find \(.applicationName) shows with \(.actorName)"
            ],
            shortTitle: "Search By Actor",
            systemImageName: "magnifyingglass"
        )
    }
}
