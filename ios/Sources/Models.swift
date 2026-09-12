import SwiftUI

/// 双休等级（L1~L6），含中文名与徽章配色（清新治愈系语义色）。
enum RestLevel: Int, CaseIterable, Identifiable, Codable {
    case strict = 1   // 严格双休
    case rest = 2     // 双休
    case alternating = 3  // 大小周
    case single = 4   // 单休
    case nineNineSix = 5  // 996
    case unknown = 6  // 待验证

    var id: Int { rawValue }

    var name: String {
        switch self {
        case .strict: return "严格双休"
        case .rest: return "双休"
        case .alternating: return "大小周"
        case .single: return "单休"
        case .nineNineSix: return "996"
        case .unknown: return "待验证"
        }
    }

    var color: Color {
        switch self {
        case .strict: return .sxgGreen
        case .rest: return .sxgMint
        case .alternating: return .sxgYellow
        case .single: return .sxgOrange
        case .nineNineSix: return .sxgRed
        case .unknown: return .sxgGray
        }
    }
}

struct Product: Codable, Identifiable, Hashable {
    let itemId: String
    let title: String
    let image: String
    let price: Double
    let brand: String?
    let category: String?
    let restLevel: Int?
    let restLevelName: String?
    let companyId: Int?
    let companyName: String?
    let confidence: Double?
    let clickUrl: String

    var id: String { itemId }

    /// 未打标商品（品牌未收录）视为待验证
    var level: RestLevel { RestLevel(rawValue: restLevel ?? 6) ?? .unknown }
}

struct EvidenceItem: Codable, Hashable {
    let sourceType: String
    let url: String
    let title: String
    let keywords: [String]
    let rawScore: Double
    let collectedAt: String
}

struct CompanyDetail: Codable, Hashable {
    let id: Int
    let name: String
    let level: Int
    let levelName: String
    let confidence: Double
    let disputed: Bool
    let evidenceCount: Int
    let evidences: [EvidenceItem]

    var restLevel: RestLevel { RestLevel(rawValue: level) ?? .unknown }
}