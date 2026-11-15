// Draws Flux's art locally (no downloaded assets):
//   swift app/dmg/art.swift <outdir>
// -> <outdir>/Flux.iconset/*.png (for iconutil), background.png (660x400), background@2x.png (1320x800)
import AppKit

let out = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ".")

func png(_ size: NSSize, scale: CGFloat, _ draw: (CGRect) -> Void) -> Data {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width * scale), pixelsHigh: Int(size.height * scale),
                               bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    rep.size = size
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    draw(CGRect(origin: .zero, size: size))
    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using: .png, properties: [:])!
}

// ---- App icon: the menu-bar "waveform" symbol in black on a light grey macOS tile ----
func drawIcon(_ r: CGRect) {
    let s = r.width, inset = s * 0.1, tile = r.insetBy(dx: inset, dy: inset)   // Apple's 824/1024 grid
    let path = NSBezierPath(roundedRect: tile, xRadius: tile.width * 0.225, yRadius: tile.width * 0.225)
    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.22)
    shadow.shadowOffset = NSSize(width: 0, height: -s * 0.01)
    shadow.shadowBlurRadius = s * 0.025
    shadow.set()
    NSColor(white: 0.965, alpha: 1).setFill()
    path.fill()
    NSGraphicsContext.restoreGraphicsState()
    NSColor.black.withAlphaComponent(0.08).setStroke(); path.lineWidth = max(1, s * 0.002); path.stroke()
    let cfg = NSImage.SymbolConfiguration(pointSize: tile.width * 0.42, weight: .medium)
        .applying(NSImage.SymbolConfiguration(paletteColors: [.black]))
    let g = NSImage(systemSymbolName: "waveform", accessibilityDescription: nil)!.withSymbolConfiguration(cfg)!
    g.draw(in: CGRect(x: tile.midX - g.size.width / 2, y: tile.midY - g.size.height / 2, width: g.size.width, height: g.size.height))
}

let iconset = out.appendingPathComponent("Flux.iconset")
try? FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
for pt in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let name = scale == 1 ? "icon_\(pt)x\(pt).png" : "icon_\(pt)x\(pt)@2x.png"
        try! png(NSSize(width: pt, height: pt), scale: CGFloat(scale), drawIcon).write(to: iconset.appendingPathComponent(name))
    }
}

// ---- DMG background, 660x400 points ----
// Icon centres (Finder, top-left origin): Flux (165,175), Applications (495,175) (app/dmg/dmg_settings.py).
func drawBackground(_ r: CGRect) {
    NSGradient(starting: NSColor(white: 0.985, alpha: 1), ending: NSColor(white: 0.95, alpha: 1))!.draw(in: r, angle: -90)
    let y = r.height - 175   // flip: Finder y is from the top
    let arrow = NSBezierPath()
    arrow.move(to: NSPoint(x: 250, y: y)); arrow.line(to: NSPoint(x: 405, y: y))
    arrow.lineWidth = 2.5; arrow.lineCapStyle = .round
    NSColor(white: 0.62, alpha: 1).setStroke(); arrow.stroke()
    let head = NSBezierPath()
    head.move(to: NSPoint(x: 393, y: y + 10)); head.line(to: NSPoint(x: 407, y: y)); head.line(to: NSPoint(x: 393, y: y - 10))
    head.lineWidth = 2.5; head.lineCapStyle = .round; head.lineJoinStyle = .round; head.stroke()
    let para = NSMutableParagraphStyle(); para.alignment = .center
    NSAttributedString(string: "Drag Flux to Applications, then open it to set it up.",
        attributes: [.font: NSFont.systemFont(ofSize: 13), .foregroundColor: NSColor(white: 0.42, alpha: 1), .paragraphStyle: para])
        .draw(in: CGRect(x: 0, y: r.height - 300, width: r.width, height: 20))
}

try! png(NSSize(width: 660, height: 400), scale: 1, drawBackground).write(to: out.appendingPathComponent("background.png"))
try! png(NSSize(width: 660, height: 400), scale: 2, drawBackground).write(to: out.appendingPathComponent("background@2x.png"))
print("art in \(out.path)")
