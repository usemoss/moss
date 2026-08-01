// Minimal `vscode` module stub so the REAL extension-host supervisor
// (src/moss/client.ts `MossSessionManager`) can be exercised in a plain Node
// test process. Only the surface the supervisor path touches is implemented:
//   * workspace.getConfiguration("moss").get(...) — used by findNodeBinary
//     (returns undefined so it falls through to process.execPath) and by
//     workspaceSessionName;
//   * workspace.workspaceFolders / workspace.name — used by
//     workspaceSessionName.
// No production code is changed; this only substitutes the editor host at
// bundle time.

const configuration = {
  get(_key, defaultValue) {
    return defaultValue;
  },
};

export const workspace = {
  workspaceFolders: undefined,
  name: undefined,
  getConfiguration() {
    return configuration;
  },
  update() {
    return Promise.resolve();
  },
};

export const window = {
  showInputBox() {
    return Promise.resolve(undefined);
  },
};

export const ConfigurationTarget = { Global: 1, Workspace: 2, WorkspaceFolder: 3 };

export default { workspace, window, ConfigurationTarget };
