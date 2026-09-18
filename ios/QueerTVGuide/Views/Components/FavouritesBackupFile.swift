import SwiftUI
import GuideCore

/// The favourites backup as something the share sheet can hand on: a JSON
/// file named `favourites-backup.json`, built only when the user picks a
/// destination. The app never sends it anywhere itself.
struct FavouritesBackupFile: Transferable {
    let entries: [FavouritesStore.Entry]

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .json) { file in
            try FavouritesBackup.export(file.entries)
        }
        .suggestedFileName(FavouritesBackup.suggestedFileName)
    }
}
