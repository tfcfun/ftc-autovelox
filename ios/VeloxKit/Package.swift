// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "VeloxKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "VeloxKit", targets: ["VeloxKit"])],
    targets: [
        .target(name: "VeloxKit"),
        .testTarget(
            name: "VeloxKitTests",
            dependencies: ["VeloxKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
