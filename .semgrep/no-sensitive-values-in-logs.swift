import Foundation

func demo(authToken: String, count: Int, userEmail: String) {
    // ruleid: no-sensitive-values-in-logs-swift
    print(authToken)
    // ruleid: no-sensitive-values-in-logs-swift
    NSLog("%@", userEmail)
    // ok: no-sensitive-values-in-logs-swift
    print(count)
    var offenders: [String] = []
    // ok: no-sensitive-values-in-logs-swift
    offenders.append("\(authToken)")
    let logger = Logger()
    // ruleid: no-sensitive-values-in-logs-swift
    logger.error(authToken)
}

struct Logger {
    func error(_ message: String) {}
}
