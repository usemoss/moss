import Foundation

struct UserSettings: Codable, Equatable {
    var indexDocuments: Bool = true
    var indexDesktop: Bool = true
    var indexDownloads: Bool = true
    var indexICloudDrive: Bool = true
    var launchAtLogin: Bool = false
    var mossCloudSync: Bool = false

    private static let storageKey = "moss.pikachu.userSettings"

    static func load() -> UserSettings {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let settings = try? JSONDecoder().decode(UserSettings.self, from: data) else {
            return UserSettings()
        }
        return settings
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }
}
