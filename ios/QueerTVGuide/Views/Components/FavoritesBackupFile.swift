import SwiftUI
import GuideCore

/// The favorites backup as something the share sheet can hand on: a JSON
/// file named `favourites-backup.json`, built only when the user picks a
/// destination. The app never sends it anywhere itself.
struct FavoritesBackupFile: Transferable {
    let entries: [FavoritesStore.Entry]

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .json) { file in
            try FavoritesBackup.export(file.entries)
        }
        .suggestedFileName(FavoritesBackup.suggestedFileName)
    }
}
