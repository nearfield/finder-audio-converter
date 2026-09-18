import AppKit
let name = NSImage.Name("NSTouchBarAudioOutputVolumeHigh")
guard let symbol = NSImage(named: name) else { fatalError("System Audio Output image not found") }
let folder = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
for size in [16,32,64,128,256,512,1024] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes:nil, pixelsWide:size, pixelsHigh:size, bitsPerSample:8, samplesPerPixel:4, hasAlpha:true, isPlanar:false, colorSpaceName:.deviceRGB, bytesPerRow:0, bitsPerPixel:0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep:bitmap)
    let dimension = CGFloat(size)
    let scale = min(dimension / symbol.size.width, dimension / symbol.size.height) * 0.8
    let rect = NSRect(x:(dimension-symbol.size.width*scale)/2, y:(dimension-symbol.size.height*scale)/2, width:symbol.size.width*scale, height:symbol.size.height*scale)
    symbol.draw(in:rect)
    NSColor.black.setFill()
    NSRect(x:0,y:0,width:dimension,height:dimension).fill(using:.sourceAtop)
    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using:.png,properties:[:])!.write(to:folder.appendingPathComponent("\(size).png"))
}
print("Exported stock system image:", name)
