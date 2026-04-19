import Foundation
import ScreenCaptureKit
import CoreGraphics
import ImageIO

guard CommandLine.arguments.count >= 2 else {
    fputs("Usage: capture-helper <output.png>\n", stderr)
    exit(1)
}

let outputPath = CommandLine.arguments[1]

let sema = DispatchSemaphore(value: 0)
var captured: CGImage? = nil
var captureError: String? = nil

Task {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            captureError = "no display found"
            sema.signal()
            return
        }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.width = display.width
        config.height = display.height
        config.pixelFormat = kCVPixelFormatType_32BGRA
        config.showsCursor = false

        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        captured = image
    } catch {
        captureError = error.localizedDescription
    }
    sema.signal()
}

sema.wait()

if let err = captureError {
    fputs("capture-helper error: \(err)\n", stderr)
    exit(1)
}

guard let image = captured else {
    fputs("capture-helper: no image\n", stderr)
    exit(1)
}

let url = URL(fileURLWithPath: outputPath) as CFURL
guard let dest = CGImageDestinationCreateWithURL(url, "public.png" as CFString, 1, nil) else {
    fputs("capture-helper: could not create destination\n", stderr)
    exit(1)
}
CGImageDestinationAddImage(dest, image, nil)
guard CGImageDestinationFinalize(dest) else {
    fputs("capture-helper: could not write file\n", stderr)
    exit(1)
}
exit(0)
