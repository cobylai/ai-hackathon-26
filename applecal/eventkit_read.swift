// Read-only EventKit reader for Flux. Prints JSON: {"status": "...", "calendars": [...], "events": [...]}.
// usage: flux-eventkit <start-epoch> <end-epoch> [--list]
// predicateForEvents returns every OCCURRENCE of a repeating event inside the window (EventKit expands them).
// This program never writes: no save/remove calls exist here.
import Foundation
import EventKit

let args = CommandLine.arguments
guard args.count >= 3, let lo = Double(args[1]), let hi = Double(args[2]) else {
    FileHandle.standardError.write("usage: flux-eventkit <start-epoch> <end-epoch>\n".data(using: .utf8)!)
    exit(2)
}
let store = EKEventStore()
let sem = DispatchSemaphore(value: 0)
var granted = false
if #available(macOS 14.0, *) {
    store.requestFullAccessToEvents { ok, _ in granted = ok; sem.signal() }
} else {
    store.requestAccess(to: .event) { ok, _ in granted = ok; sem.signal() }
}
_ = sem.wait(timeout: .now() + 120)
func emit(_ o: [String: Any]) {
    let d = try! JSONSerialization.data(withJSONObject: o, options: [])
    print(String(data: d, encoding: .utf8)!)
}
if !granted { emit(["status": "denied", "calendars": [], "events": []]); exit(0) }

func kind(_ t: EKCalendarType) -> String {
    switch t {
    case .local: return "local"
    case .calDAV: return "caldav"
    case .exchange: return "exchange"
    case .subscription: return "subscription"
    case .birthday: return "birthday"
    @unknown default: return "other"
    }
}
let cals = store.calendars(for: .event)
let calInfo = cals.map { ["name": $0.title, "type": kind($0.type)] }
let pred = store.predicateForEvents(withStart: Date(timeIntervalSince1970: lo),
                                    end: Date(timeIntervalSince1970: hi), calendars: cals)
var out: [[String: Any]] = []
for e in store.events(matching: pred) {
    out.append(["calendar": e.calendar.title, "type": kind(e.calendar.type),
                "title": e.title ?? "", "location": e.location ?? "",
                "start": e.startDate.timeIntervalSince1970, "end": e.endDate.timeIntervalSince1970,
                "all_day": e.isAllDay])
}
emit(["status": "ok", "calendars": calInfo, "events": out])
