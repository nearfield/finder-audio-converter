import AppKit

// Merge only this project's service entries; preserve other Services settings.
let args = CommandLine.arguments
if args.count != 4 { fputs("Usage: ServicePreferences enable|remove DOMAIN SERVICE_KEYS_JSON\n", stderr); exit(1) }
let mode = args[1], domain = args[2]
let keys = try JSONDecoder().decode([String].self, from: Data(contentsOf: URL(fileURLWithPath: args[3])))
guard ["enable", "remove"].contains(mode), let defaults = UserDefaults(suiteName: domain) else { exit(1) }
var status = defaults.dictionary(forKey: "NSServicesStatus") ?? [:]
for key in keys {
    if mode == "remove" { status.removeValue(forKey: key); continue }
    var entry = status[key] as? [String: Any] ?? [:]
    var modes = entry["presentation_modes"] as? [String: Any] ?? [:]
    modes["ContextMenu"] = true
    modes["FinderPreview"] = true
    modes["ServicesMenu"] = true
    modes["TouchBar"] = false
    entry["presentation_modes"] = modes
    status[key] = entry
}
defaults.set(status, forKey: "NSServicesStatus")
guard defaults.synchronize() else { fputs("Could not save service preferences.\n", stderr); exit(1) }
if domain == "pbs" { NSUpdateDynamicServices() }
print("Service preferences updated.")
