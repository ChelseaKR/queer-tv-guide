// swift-tools-version: 5.10
// GuideCore: the app's data layer. Foundation only. Builds and tests on macOS
// (`swift test`) and iOS. No third-party dependencies — that is the product.
import PackageDescription

let package = Package(
    name: "GuideCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "GuideCore", type: .static, targets: ["GuideCore"]),
    ],
    targets: [
        .target(
            name: "GuideCore",
            path: "Sources/GuideCore"
        ),
        .testTarget(
            name: "GuideCoreTests",
            dependencies: ["GuideCore"],
            path: "Tests/GuideCoreTests"
        ),
    ]
)
