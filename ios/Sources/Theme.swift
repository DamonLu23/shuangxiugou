import SwiftUI

/// 清新治愈系设计令牌。
extension Color {
    static let sxgBackground = Color(red: 0.98, green: 0.98, blue: 0.97)   // 暖白 #FAFAF7
    static let sxgGreen = Color(red: 0.18, green: 0.55, blue: 0.34)       // 主色草绿
    static let sxgMint = Color(red: 0.45, green: 0.72, blue: 0.55)
    static let sxgYellow = Color(red: 0.93, green: 0.75, blue: 0.28)
    static let sxgOrange = Color(red: 0.94, green: 0.55, blue: 0.25)
    static let sxgRed = Color(red: 0.85, green: 0.32, blue: 0.27)
    static let sxgGray = Color.gray.opacity(0.6)
}

/// 双休等级徽章：花瓣形药丸 + 等级色。
struct RestBadge: View {
    let level: RestLevel?
    var prominent = false

    var body: some View {
        Group {
            if let level, level == .strict {
                HStack(spacing: 3) {
                    Image(systemName: "leaf.fill")
                    Text(level.name)
                }
                .font(.caption.weight(.semibold))
                .foregroundColor(.white)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(Capsule().fill(level.color))
            } else if let level {
                Text(level.name)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(level.color)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Capsule().stroke(level.color, lineWidth: 1))
            } else {
                Text("暂未收录")
                    .font(.caption)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .foregroundColor(.sxgGray)
                    .background(Capsule().fill(Color.sxgGray.opacity(0.15)))
            }
        }
    }
}