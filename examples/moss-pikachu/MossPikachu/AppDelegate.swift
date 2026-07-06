import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var floatingPetController: FloatingPetWindowController?
    private var searchOverlayController: SearchOverlayController?
    private var settingsWindowController: SettingsWindowController?
    private var bootstrapWindowController: IndexingBootstrapWindowController?
    private var credentialsWindowController: CredentialsSetupWindowController?
    private let hotKeyManager = HotKeyManager()
    private let searchService = SearchService()
    private let petStateController = PetStateController()
    private let searchPresentation = SearchOverlayPresentation()

    var debugMode: Bool {
        ProcessInfo.processInfo.arguments.contains("--debug")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if debugMode {
            AppLogger.shared.isDebugEnabled = true
            AppLogger.shared.log("Moss Pikachu starting in debug mode")
        }

        setupSearchOverlay()
        setupSettingsWindow()
        setupFloatingPet()
        setupHotKey()

        guard MossBridge.hasCredentials() else {
            showCredentialsWindow()
            return
        }

        Task {
            await runInitializeFlow()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        searchService.shutdown()
        hotKeyManager.unregister()
    }

    private func runInitializeFlow() async {
        let needsBootstrap = searchService.requiresBootstrapIndex
        if needsBootstrap {
            showBootstrapWindow()
        }

        do {
            try await searchService.initialize()
            if debugMode {
                AppLogger.shared.log("SearchService initialized")
            }

            if needsBootstrap {
                hideBootstrapWindow()
            }
        } catch {
            hideBootstrapWindow()
            let message = friendlyInitError(error)
            searchService.markInitializationFailed(message)
            if debugMode {
                AppLogger.shared.log("SearchService init failed: \(message)")
            }
            NotificationManager.shared.showError(message)
        }
    }

    private func friendlyInitError(_ error: Error) -> String {
        let text = error.localizedDescription.lowercased()
        if text.contains("credential") || text.contains("missing") {
            return "Moss API credentials missing or invalid. Add them in Moss Pikachu Settings or the setup window."
        }
        if text.contains("python") || text.contains("moss python") || text.contains("venv") {
            return error.localizedDescription
        }
        if text.contains("usage_limit") || text.contains("429") {
            return "Moss API quota exceeded. Check your Moss project limits."
        }
        return error.localizedDescription
    }

    // MARK: - Setup

    private func showCredentialsWindow() {
        guard credentialsWindowController == nil else {
            credentialsWindowController?.show()
            return
        }
        credentialsWindowController = CredentialsSetupWindowController()
        credentialsWindowController?.onCredentialsSaved = { [weak self] in
            guard let self else { return }
            self.credentialsWindowController = nil
            Task { await self.runInitializeFlow() }
        }
        credentialsWindowController?.show()
    }

    private func showBootstrapWindow() {
        guard bootstrapWindowController == nil else {
            bootstrapWindowController?.show()
            return
        }
        bootstrapWindowController = IndexingBootstrapWindowController(searchService: searchService)
        bootstrapWindowController?.show()
    }

    private func hideBootstrapWindow() {
        bootstrapWindowController?.close()
        bootstrapWindowController = nil
    }

    private func setupFloatingPet() {
        guard floatingPetController == nil else {
            floatingPetController?.show()
            return
        }
        floatingPetController = FloatingPetWindowController(petStateController: petStateController)
        floatingPetController?.onPetClicked = { [weak self] in
            self?.openSearch()
        }
        floatingPetController?.onShowSettings = { [weak self] in
            self?.showSettings()
        }
        floatingPetController?.onQuit = { [weak self] in
            self?.quitApp()
        }
        floatingPetController?.show()
    }

    private func setupSearchOverlay() {
        searchOverlayController = SearchOverlayController(
            searchService: searchService,
            presentation: searchPresentation,
            anchorProvider: { [weak self] in
                self?.floatingPetController?.screenFrame
            }
        )
        searchOverlayController?.onPetStateChanged = { [weak self] state in
            self?.petStateController.state = state
        }
    }

    private func setupHotKey() {
        hotKeyManager.onHotKeyPressed = { [weak self] in
            Task { @MainActor in
                self?.toggleSearch()
            }
        }
        hotKeyManager.register()
    }

    private func setupSettingsWindow() {
        settingsWindowController = SettingsWindowController(searchService: searchService)
    }

    // MARK: - Actions

    private func searchBlockedMessage() -> String {
        if !MossBridge.hasCredentials() {
            return "Add Moss API credentials in Settings to start searching."
        }
        if let error = searchService.initializationError, !error.isEmpty {
            return error
        }
        if searchService.isInitializing {
            return searchService.statusMessage.isEmpty
                ? "Starting Moss session…"
                : searchService.statusMessage
        }
        return "Moss Pikachu is not ready yet. Open Settings and tap Retry Initialize."
    }

    private func openSearch() {
        guard MossBridge.hasCredentials() else {
            showCredentialsWindow()
            return
        }
        guard searchService.isReady else {
            if searchService.requiresBootstrapIndex || searchService.isInitializing {
                showBootstrapWindow()
            } else {
                NotificationManager.shared.showError(searchBlockedMessage())
            }
            return
        }
        if searchOverlayController?.isSearchVisible == true {
            searchOverlayController?.focusSearchField()
        } else {
            searchOverlayController?.show()
        }
    }

    @objc private func showSettings() {
        settingsWindowController?.show()
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    private func toggleSearch() {
        guard MossBridge.hasCredentials() else {
            showCredentialsWindow()
            return
        }
        guard searchService.isReady else {
            if searchService.requiresBootstrapIndex || searchService.isInitializing {
                showBootstrapWindow()
            } else {
                NotificationManager.shared.showError(searchBlockedMessage())
            }
            return
        }
        searchOverlayController?.toggle()
    }
}
