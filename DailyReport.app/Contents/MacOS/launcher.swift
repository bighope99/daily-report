import Foundation

let bundleURL = Bundle.main.bundleURL
let projectRoot = bundleURL.deletingLastPathComponent().path

var env = ProcessInfo.processInfo.environment
if env["HOME"] == nil { env["HOME"] = NSHomeDirectory() }

for prefix in ["/opt/homebrew", "/usr/local"] {
    if FileManager.default.fileExists(atPath: "\(prefix)/bin") {
        env["PATH"] = "\(prefix)/bin:" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        break
    }
}

let pyver = { () -> String in
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
    p.arguments = ["-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"]
    let pipe = Pipe()
    p.standardOutput = pipe
    try? p.run(); p.waitUntilExit()
    return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
        .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
}()

if !pyver.isEmpty {
    let base = (env["HOME"] ?? NSHomeDirectory()) + "/Library/Python/\(pyver)"
    env["PYTHONUSERBASE"] = base
    let sp = "\(base)/lib/python/site-packages"
    env["PYTHONPATH"] = env["PYTHONPATH"].map { "\(sp):\($0)" } ?? sp
}

let process = Process()
process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
process.arguments = ["\(projectRoot)/hybrid_logger.py"]
process.environment = env
do {
    try process.run()
    process.waitUntilExit()
    exit(process.terminationStatus)
} catch {
    fputs("DailyReport launcher error: \(error)\n", stderr)
    exit(1)
}
