import Foundation
import CoreSpotlight
import GuideCore

/// Indexes shows and characters for Spotlight search. All indexing is
/// on-device: no data leaves the phone, no network request is made.
enum SpotlightIndexer {
    private static let domainIdentifier = "com.chelseakr.queertvguide"

    /// Indexes all shows and characters from the snapshot. Called once
    /// when the snapshot loads, and again after each refresh.
    static func index(snapshot: Snapshot) {
        var items: [CSSearchableItem] = []

        for show in snapshot.shows {
            let attributeSet = CSSearchableItemAttributeSet(contentType: .movie)
            attributeSet.title = show.title
            attributeSet.contentDescription = Presentation.years(show.years) + " · " + Presentation.seasons(show.seasons)
            if !show.networks.isEmpty {
                attributeSet.displayName = show.networks.map(\.name).joined(separator: ", ")
            }
            attributeSet.keywords = [show.title] + show.networks.map(\.name)
            attributeSet.contentURL = show.sourceURL

            let item = CSSearchableItem(
                uniqueIdentifier: "show-\(show.id)",
                domainIdentifier: domainIdentifier,
                attributeSet: attributeSet
            )
            items.append(item)
        }

        for character in snapshot.characters {
            let showTitles = character.shows.compactMap { snapshot.show(id: $0.showID)?.title }.joined(separator: ", ")
            let attributeSet = CSSearchableItemAttributeSet(contentType: .person)
            attributeSet.title = character.name
            if !showTitles.isEmpty {
                attributeSet.contentDescription = "From \(showTitles)"
                attributeSet.displayName = showTitles
            }
            attributeSet.keywords = [character.name] + showTitles.components(separatedBy: ", ")

            let item = CSSearchableItem(
                uniqueIdentifier: "character-\(character.id)",
                domainIdentifier: domainIdentifier,
                attributeSet: attributeSet
            )
            items.append(item)
        }

        CSSearchableIndex.default().indexSearchableItems(items)
    }

    /// Removes all indexed items. Called when the app is deleted or
    /// when a refresh produces a completely different snapshot.
    static func clearIndex() {
        CSSearchableIndex.default().deleteSearchableItems(withDomainIdentifiers: [domainIdentifier])
    }
}
