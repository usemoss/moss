// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Moss",
    platforms: [.iOS(.v15)],
    products: [
        .library(name: "Moss", targets: ["Moss"]),
    ],
    targets: [
        .binaryTarget(
            name: "MossC",
            url: "https://github.com/usemoss/moss/releases/download/v0.7.0/Moss.xcframework.zip",
            checksum: "b8446db36039320cd1d073acb9e606d2dc7d8294253b45324b276fc50290bf61"
        ),
        .target(
            name: "MossRuntimeBridge",
            dependencies: ["MossC"],
            path: "sdks/swift/Sources/MossRuntimeBridge",
            publicHeadersPath: "include"
        ),
        .target(
            name: "Moss",
            dependencies: ["MossC", "MossRuntimeBridge"],
            path: "sdks/swift/Sources/Moss"
        ),
    ]
)
