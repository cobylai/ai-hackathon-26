// Draws Muse's art locally (no downloaded assets):
//   swift app/dmg/art.swift <outdir>
// -> <outdir>/Muse.iconset/*.png (for iconutil), background.png (660x400), background@2x.png (1320x800)
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

// ---- App icon: white waveform on a soft blue-grey rounded square ----
func drawIcon(_ r: CGRect) {
    let s = r.width
    let inset = s * 0.1
    let tile = r.insetBy(dx: inset, dy: inset)
    let path = NSBezierPath(roundedRect: tile, xRadius: tile.width * 0.225, yRadius: tile.width * 0.225)
    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.25)
    shadow.shadowOffset = NSSize(width: 0, height: -s * 0.012)
    shadow.shadowBlurRadius = s * 0.03
    shadow.set()
    NSColor(red: 0.36, green: 0.45, blue: 0.56, alpha: 1).setFill()
    path.fill()
    NSGraphicsContext.restoreGraphicsState()
    NSGradient(starting: NSColor(red: 0.47, green: 0.57, blue: 0.68, alpha: 1),
               ending: NSColor(red: 0.30, green: 0.38, blue: 0.49, alpha: 1))!.draw(in: path, angle: -90)
    // waveform: seven rounded bars
    let heights: [CGFloat] = [0.16, 0.32, 0.52, 0.70, 0.52, 0.32, 0.16]
    let barW = tile.width * 0.075, gap = tile.width * 0.045
    let total = CGFloat(heights.count) * barW + CGFloat(heights.count - 1) * gap
    var x = tile.midX - total / 2
    NSColor.white.setFill()
    for h in heights {
        let bh = tile.height * h
        NSBezierPath(roundedRect: CGRect(x: x, y: tile.midY - bh / 2, width: barW, height: bh),
                     xRadius: barW / 2, yRadius: barW / 2).fill()
        x += barW + gap
    }
}

let iconset = out.appendingPathComponent("Muse.iconset")
try? FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
for pt in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let name = scale == 1 ? "icon_\(pt)x\(pt).png" : "icon_\(pt)x\(pt)@2x.png"
        try! png(NSSize(width: pt, height: pt), scale: CGFloat(scale), drawIcon).write(to: iconset.appendingPathComponent(name))
    }
}

// ---- DMG background, 660x400 points ----
// Icon centres (Finder, top-left origin): Muse (165,150), Applications (495,150); bottom row y=322 (app/dmg/dmg_settings.py).
func drawBackground(_ r: CGRect) {
    NSGradient(starting: NSColor(white: 0.985, alpha: 1), ending: NSColor(white: 0.94, alpha: 1))!.draw(in: r, angle: -90)
    let y = r.height - 150   // flip: Finder y is from the top
    // arrow between the two icons
    let arrow = NSBezierPath()
    arrow.move(to: NSPoint(x: 250, y: y)); arrow.line(to: NSPoint(x: 405, y: y))
    arrow.lineWidth = 2.5; arrow.lineCapStyle = .round
    NSColor(white: 0.62, alpha: 1).setStroke(); arrow.stroke()
    let head = NSBezierPath()
    head.move(to: NSPoint(x: 393, y: y + 10)); head.line(to: NSPoint(x: 407, y: y)); head.line(to: NSPoint(x: 393, y: y - 10))
    head.lineWidth = 2.5; head.lineCapStyle = .round; head.lineJoinStyle = .round; head.stroke()
    // one line of text under the icons
    let para = NSMutableParagraphStyle(); para.alignment = .center
    let text = NSAttributedString(string: "Drag Muse to Applications, then open it to finish setup.",
        attributes: [.font: NSFont.systemFont(ofSize: 13), .foregroundColor: NSColor(white: 0.40, alpha: 1), .paragraphStyle: para])
    text.draw(in: CGRect(x: 0, y: r.height - 258, width: r.width, height: 20))
    // hairline above the bottom row
    NSColor(white: 0.86, alpha: 1).setFill()
    NSBezierPath(rect: CGRect(x: 60, y: r.height - 274, width: r.width - 120, height: 1)).fill()
}

try! png(NSSize(width: 660, height: 400), scale: 1, drawBackground).write(to: out.appendingPathComponent("background.png"))
try! png(NSSize(width: 660, height: 400), scale: 2, drawBackground).write(to: out.appendingPathComponent("background@2x.png"))
print("art in \(out.path)")
