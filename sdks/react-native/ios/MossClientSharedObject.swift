import ExpoModulesCore
import Foundation
import MossC
import UIKit

/**
 * SharedObject wrapping a native MossClient handle.
 * Methods return dictionaries / arrays that map cleanly across the JSI bridge.
 */
public final class MossClientSharedObject: SharedObject {
  private var handle: OpaquePointer?
  private var closed = false
  private let lock = NSLock()

  public init(projectId: String, projectKey: String) throws {
    try Self.ensureModelCacheDir()
    let deviceId = Self.stableDeviceId()
    var raw: OpaquePointer?
    let status = projectId.withCString { pid in
      projectKey.withCString { pkey in
        deviceId.withCString { did in
          moss_client_new_with_device_id(pid, pkey, did, &raw)
        }
      }
    }
    try Self.throwIfErr(status)
    guard let raw else {
      throw Self.mossError(code: -7)
    }
    self.handle = raw
    super.init()
  }

  deinit {
    close()
  }

  public func close() {
    lock.lock()
    defer { lock.unlock() }
    guard !closed else { return }
    closed = true
    if let handle {
      moss_client_free(handle)
    }
    handle = nil
  }

  public func createIndex(name: String, docsJson: String, modelId: String?) throws -> [String: Any] {
    let h = try borrow()
    var out: UnsafeMutablePointer<CChar>?
    let status = name.withCString { cname in
      docsJson.withCString { cdocs in
        withOptionalCString(modelId) { cmodel in
          moss_client_create_index_from_json(h, cname, cdocs, cmodel, &out)
        }
      }
    }
    try Self.throwIfErr(status)
    guard let out else {
      throw Self.mossError(code: -7)
    }
    defer { moss_free_string(out) }
    return try Self.decodeJsonObject(String(cString: out))
  }

  public func loadIndex(name: String, options: [String: Any]) throws {
    let h = try borrow()
    let autoRefresh = (options["autoRefresh"] as? Bool) ?? false
    let interval = UInt64((options["pollingIntervalSeconds"] as? Double) ?? 600)
    let cachePath = options["cachePath"] as? String

    let status = name.withCString { cname in
      withOptionalCString(cachePath) { cache in
        var nativeOpts = MossLoadIndexOptions(
          auto_refresh: autoRefresh,
          polling_interval_secs: interval,
          cache_path: cache
        )
        var info: UnsafeMutablePointer<MossIndexInfo>?
        let r = moss_client_load_index(h, cname, &nativeOpts, &info)
        if let info { moss_free_index_info(info) }
        return r
      }
    }
    try Self.throwIfErr(status)
  }

  public func unloadIndex(name: String) throws {
    let h = try borrow()
    let status = name.withCString { cname in moss_client_unload_index(h, cname) }
    try Self.throwIfErr(status)
  }

  public func query(name: String, query: String, options: [String: Any]) throws -> [String: Any] {
    let h = try borrow()
    let topK = max(0, Int((options["topK"] as? Double) ?? 5))
    let alpha = Float((options["alpha"] as? Double) ?? 0.8)
    let filterJson = options["filterJson"] as? String

    return try name.withCString { iname in
      try query.withCString { q in
        try withOptionalCString(filterJson) { filter in
          var nativeOpts = MossQueryOptions(
            top_k: UInt(topK),
            alpha: alpha,
            filter_json: filter,
            embedding: nil,
            embedding_dim: 0
          )
          var result: UnsafeMutablePointer<MossSearchResult>?
          let status = moss_client_query(h, iname, q, &nativeOpts, &result)
          try Self.throwIfErr(status)
          guard let result else {
            throw Self.mossError(code: -7)
          }
          defer { moss_free_search_result(result) }
          return Self.parseSearchResult(result.pointee)
        }
      }
    }
  }

  public func listIndexes() throws -> [[String: Any]] {
    let h = try borrow()
    var infos: UnsafeMutablePointer<MossIndexInfo>?
    var count: UInt = 0
    let status = moss_client_list_indexes(h, &infos, &count)
    try Self.throwIfErr(status)
    guard let infos else { return [] }
    defer { moss_free_index_info_list(infos, count) }
    var out: [[String: Any]] = []
    out.reserveCapacity(Int(count))
    for i in 0..<Int(count) {
      out.append(Self.parseIndexInfo(infos.advanced(by: i).pointee))
    }
    return out
  }

  public func getIndex(name: String) throws -> [String: Any] {
    let h = try borrow()
    return try name.withCString { cname in
      var info: UnsafeMutablePointer<MossIndexInfo>?
      let status = moss_client_get_index(h, cname, &info)
      try Self.throwIfErr(status)
      guard let info else {
        throw Self.mossError(code: -7)
      }
      defer { moss_free_index_info(info) }
      return Self.parseIndexInfo(info.pointee)
    }
  }

  public func deleteIndex(name: String) throws -> Bool {
    let h = try borrow()
    return try name.withCString { cname in
      var deleted = false
      let status = moss_client_delete_index(h, cname, &deleted)
      try Self.throwIfErr(status)
      return deleted
    }
  }

  public func addDocs(name: String, docsJson: String, upsert: Bool) throws -> [String: Any] {
    let h = try borrow()
    var out: UnsafeMutablePointer<CChar>?
    let status = name.withCString { cname in
      docsJson.withCString { cdocs in
        moss_client_add_docs_from_json(h, cname, cdocs, upsert, &out)
      }
    }
    try Self.throwIfErr(status)
    guard let out else {
      throw Self.mossError(code: -7)
    }
    defer { moss_free_string(out) }
    return try Self.decodeJsonObject(String(cString: out))
  }

  // MARK: - Internals

  private func borrow() throws -> OpaquePointer {
    lock.lock()
    defer { lock.unlock() }
    guard !closed, let handle else {
      throw Self.mossError(code: -1, message: "MossClient already closed")
    }
    return handle
  }

  private static let cacheDirLock = NSLock()
  private static var cacheDirConfigured = false

  static func setModelCacheDir(_ path: String) throws {
    cacheDirLock.lock()
    defer { cacheDirLock.unlock() }
    let status = path.withCString { moss_set_model_cache_dir($0) }
    try throwIfErr(status)
    cacheDirConfigured = true
  }

  private static func ensureModelCacheDir() throws {
    cacheDirLock.lock()
    defer { cacheDirLock.unlock() }
    if cacheDirConfigured { return }
    guard let cacheRoot = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else {
      throw mossError(code: -7, message: "could not locate Library/Caches for model cache")
    }
    let dir = cacheRoot.appendingPathComponent("moss-models", isDirectory: true)
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    let status = dir.path.withCString { moss_set_model_cache_dir($0) }
    try throwIfErr(status)
    cacheDirConfigured = true
  }

  private static func stableDeviceId() -> String {
    if let idfv = UIDevice.current.identifierForVendor?.uuidString {
      return idfv
    }
    return UUID().uuidString
  }

  private static func throwIfErr(_ status: Int32) throws {
    if status != 0 {
      throw mossError(code: status)
    }
  }

  private static func mossError(code: Int32, message: String? = nil) -> NSError {
    let msg: String
    if let message {
      msg = message
    } else if let ptr = moss_last_error() {
      msg = String(cString: ptr)
    } else {
      msg = "moss native error code \(code)"
    }
    return NSError(
      domain: "dev.moss",
      code: Int(code),
      userInfo: [NSLocalizedDescriptionKey: msg]
    )
  }

  private static func decodeJsonObject(_ json: String) throws -> [String: Any] {
    guard let data = json.data(using: .utf8),
          let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
      throw mossError(code: -7, message: "failed to decode Moss JSON response")
    }
    return [
      "jobId": obj["jobId"] as? String ?? "",
      "indexName": obj["indexName"] as? String ?? "",
      "docCount": obj["docCount"] as? Int ?? 0,
    ]
  }

  private static func parseIndexInfo(_ info: MossIndexInfo) -> [String: Any] {
    [
      "id": cstr(info.id),
      "name": cstr(info.name),
      "status": cstr(info.status),
      "docCount": Int(info.doc_count),
      "model": [
        "id": cstr(info.model.id),
        "version": cstrOpt(info.model.version) as Any,
      ],
      "version": cstrOpt(info.version) as Any,
      "createdAt": cstrOpt(info.created_at) as Any,
      "updatedAt": cstrOpt(info.updated_at) as Any,
    ]
  }

  private static func parseSearchResult(_ result: MossSearchResult) -> [String: Any] {
    let count = Int(result.doc_count)
    var docs: [[String: Any]] = []
    docs.reserveCapacity(count)
    if let buf = result.docs {
      for i in 0..<count {
        let d = buf.advanced(by: i).pointee
        var row: [String: Any] = [
          "id": cstr(d.id),
          "text": cstr(d.text),
          "score": d.score,
        ]
        if let metadata = parseMetadata(d.metadata, count: d.metadata_count) {
          row["metadata"] = metadata
        }
        if let payload = d.payload {
          row["payload"] = String(cString: payload)
        }
        docs.append(row)
      }
    }
    return [
      "docs": docs,
      "query": cstr(result.query),
      "timeMs": result.time_taken_ms,
    ]
  }

  private static func parseMetadata(
    _ entries: UnsafeMutablePointer<MossMetadataEntry>?,
    count: UInt
  ) -> [String: String]? {
    guard let entries, count > 0 else { return nil }
    var out: [String: String] = [:]
    for i in 0..<Int(count) {
      let e = entries.advanced(by: i).pointee
      guard let keyPtr = e.key else { continue }
      out[String(cString: keyPtr)] = cstr(e.value)
    }
    return out.isEmpty ? nil : out
  }
}

@inline(__always)
func withOptionalCString<R>(_ value: String?, _ body: (UnsafePointer<CChar>?) throws -> R) rethrows -> R {
  if let value {
    return try value.withCString { try body($0) }
  }
  return try body(nil)
}

@inline(__always)
func cstr(_ ptr: UnsafeMutablePointer<CChar>?) -> String {
  ptr.flatMap { String(cString: $0) } ?? ""
}

@inline(__always)
func cstrOpt(_ ptr: UnsafeMutablePointer<CChar>?) -> String? {
  ptr.flatMap { String(cString: $0) }
}
