import AppKit

let application = NSApplication.shared
application.setActivationPolicy(.regular)
application.finishLaunching()

func emit(_ value: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}

final class SettingsForm: NSObject {
    let format = NSPopUpButton(frame: NSRect(x: 180, y: 240, width: 275, height: 28))
    let rate = NSPopUpButton(frame: NSRect(x: 180, y: 195, width: 275, height: 28))
    let channels = NSPopUpButton(frame: NSRect(x: 180, y: 150, width: 275, height: 28))
    let depth = NSPopUpButton(frame: NSRect(x: 180, y: 105, width: 275, height: 28))
    let bitrate = NSPopUpButton(frame: NSRect(x: 180, y: 60, width: 275, height: 28))
    let view = NSView(frame: NSRect(x: 0, y: 0, width: 460, height: 280))
    override init() {
        super.init()
        let controls = [format, rate, channels, depth, bitrate]
        let labels = ["Format", "Sample rate", "Channels", "Bit depth (lossless)", "Bitrate (MP3/AAC)"]
        let entries = [
            ["WAV", "AIFF", "FLAC", "MP3", "M4A · AAC", "M4A · Apple Lossless"],
            ["Keep original", "44100 Hz", "48000 Hz", "96000 Hz", "32000 Hz", "88200 Hz", "192000 Hz"],
            ["Keep original", "Mono · Downmix", "Mono · Left only", "Mono · Right only", "Stereo"],
            ["Keep original¹", "16 bit", "24 bit", "32 bit float"],
            ["256 kbps", "320 kbps", "192 kbps", "128 kbps"]
        ]
        for i in 0..<controls.count {
            let control = controls[i]
            control.addItems(withTitles: entries[i])
            control.setAccessibilityLabel(labels[i])
            view.addSubview(control)
            let label = NSTextField(labelWithString: labels[i])
            label.frame = NSRect(x: 0, y: control.frame.minY + 5, width: 175, height: 20)
            view.addSubview(label)
        }
        let note = NSTextField(wrappingLabelWithString: "¹ Lossy sources use 24 bit when keeping the original bit depth.\nOutput is saved in a Converted folder next to each source.")
        note.font = NSFont.systemFont(ofSize: 11)
        note.textColor = NSColor.secondaryLabelColor
        note.frame = NSRect(x: 0, y: 0, width: 455, height: 44)
        view.addSubview(note)
        format.target = self
        format.action = #selector(formatChanged)
        formatChanged()
    }
    @objc func formatChanged() {
        let lossy = [3,4].contains(format.indexOfSelectedItem)
        depth.isEnabled = !lossy
        bitrate.isEnabled = lossy
        depth.item(at: 3)?.isEnabled = [0,1].contains(format.indexOfSelectedItem)
        depth.autoenablesItems = false
        if [2,5].contains(format.indexOfSelectedItem) && depth.indexOfSelectedItem == 3 {
            depth.selectItem(at: 2)
        }
    }
    func values() -> [String: Any] {
        return ["format": ["wav","aiff","flac","mp3","aac","alac"][format.indexOfSelectedItem],
                "rate": [0,44100,48000,96000,32000,88200,192000][rate.indexOfSelectedItem],
                "channels": ["keep","mono","left","right","stereo"][channels.indexOfSelectedItem],
                "depth": ["keep","16","24","float32"][depth.indexOfSelectedItem],
                "bitrate": [256,320,192,128][bitrate.indexOfSelectedItem]]
    }
}

let alert = NSAlert()
alert.alertStyle = .informational
if let icon = NSImage(named: NSImage.Name("NSTouchBarAudioOutputVolumeHigh")) {
    alert.icon = icon
}
alert.messageText = "Finder Audio Converter"
let settings = CommandLine.arguments.dropFirst().first == "settings"
var form: SettingsForm? = nil
if settings {
    let f = SettingsForm()
    form = f
    alert.informativeText = "Choose settings to apply to all selected files."
    alert.accessoryView = f.view
    alert.addButton(withTitle: "Convert")
    alert.addButton(withTitle: "Cancel")
} else {
    alert.informativeText = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "Done"
    alert.addButton(withTitle: "OK")
}
application.activate(ignoringOtherApps: true)
alert.window.center()
alert.window.makeKeyAndOrderFront(nil)
let response = alert.runModal()
if settings {
    if response == .alertFirstButtonReturn { emit(form!.values()) } else { exit(2) }
}
