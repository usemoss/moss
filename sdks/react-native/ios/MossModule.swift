import ExpoModulesCore
import MossC

public class MossModule: Module {
  public func definition() -> ModuleDefinition {
    Name("Moss")

    Constant("sdkVersion") {
      String(cString: moss_sdk_version())
    }

    AsyncFunction("setModelCacheDir") { (path: String) in
      try MossClientSharedObject.setModelCacheDir(path)
    }

    Class("MossClient", MossClientSharedObject.self) {
      Constructor { (projectId: String, projectKey: String) -> MossClientSharedObject in
        try MossClientSharedObject(projectId: projectId, projectKey: projectKey)
      }

      AsyncFunction("createIndex") { (client: MossClientSharedObject, name: String, docsJson: String, modelId: String?) -> [String: Any] in
        try client.createIndex(name: name, docsJson: docsJson, modelId: modelId)
      }

      AsyncFunction("loadIndex") { (client: MossClientSharedObject, name: String, options: [String: Any]) in
        try client.loadIndex(name: name, options: options)
      }

      AsyncFunction("unloadIndex") { (client: MossClientSharedObject, name: String) in
        try client.unloadIndex(name: name)
      }

      AsyncFunction("query") { (client: MossClientSharedObject, name: String, query: String, options: [String: Any]) -> [String: Any] in
        try client.query(name: name, query: query, options: options)
      }

      AsyncFunction("listIndexes") { (client: MossClientSharedObject) -> [[String: Any]] in
        try client.listIndexes()
      }

      AsyncFunction("getIndex") { (client: MossClientSharedObject, name: String) -> [String: Any] in
        try client.getIndex(name: name)
      }

      AsyncFunction("deleteIndex") { (client: MossClientSharedObject, name: String) -> Bool in
        try client.deleteIndex(name: name)
      }

      AsyncFunction("addDocs") { (client: MossClientSharedObject, name: String, docsJson: String, upsert: Bool) -> [String: Any] in
        try client.addDocs(name: name, docsJson: docsJson, upsert: upsert)
      }

      Function("close") { (client: MossClientSharedObject) in
        client.close()
      }
    }
  }
}
