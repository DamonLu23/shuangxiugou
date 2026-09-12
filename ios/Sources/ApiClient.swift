import Foundation

/// 后端客户端（搜索 / 企业档案 / UGC 上报）。
struct ApiClient {
    static let shared = ApiClient()

    let baseURL: URL

    /// baseURL 优先级：注入值 > Info.plist 的 ApiBaseURL > 本地开发默认值。
    /// 生产发布时在 Xcode Build Config 的 Info.plist 注入 https 域名。
    init(baseURL: URL? = nil) {
        if let baseURL {
            self.baseURL = baseURL
        } else if let raw = Bundle.main.object(forInfoDictionaryKey: "ApiBaseURL") as? String,
                  let url = URL(string: raw) {
            self.baseURL = url
        } else {
            self.baseURL = URL(string: "http://127.0.0.1:8000")!
        }
    }

    private var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    /// 商品搜索：GET /api/search?q=&level=&sort=&page=&indexed_only=
    /// 后端已完成 品牌打标 + 双休优先排序，前端按返回顺序展示。
    func search(q: String, level: Int? = nil, sort: String = "rest_first",
                page: Int = 1, indexedOnly: Bool = false) async throws -> [Product] {
        var comps = URLComponents(url: baseURL.appendingPathComponent("api/search"),
                                  resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "q", value: q),
            URLQueryItem(name: "sort", value: sort),
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "indexed_only", value: indexedOnly ? "true" : "false"),
        ]
        if let level { comps.queryItems?.append(URLQueryItem(name: "level", value: "\(level)")) }

        let (data, response) = try await URLSession.shared.data(from: comps.url!)
        try Self.validate(response)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let itemsData = try JSONSerialization.data(withJSONObject: json?["items"] ?? [])
        return try decoder.decode([Product].self, from: itemsData)
    }

    /// 企业双休档案：GET /api/companies/{id}
    func company(id: Int) async throws -> CompanyDetail {
        let url = baseURL.appendingPathComponent("api/companies/\(id)")
        let (data, response) = try await URLSession.shared.data(from: url)
        try Self.validate(response)
        return try decoder.decode(CompanyDetail.self, from: data)
    }

    /// 企业列表：GET /api/companies?level=
    func companies(level: Int? = nil, limit: Int = 50) async throws -> [CompanyListItem] {
        var comps = URLComponents(url: baseURL.appendingPathComponent("api/companies"),
                                  resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        if let level { comps.queryItems?.append(URLQueryItem(name: "level", value: "\(level)")) }
        let (data, response) = try await URLSession.shared.data(from: comps.url!)
        try Self.validate(response)
        return try decoder.decode([CompanyListItem].self, from: data)
    }

    /// UGC 上报：POST /api/companies/{id}/report
    /// - Returns: (reportId, status)
    func reportEvidence(companyId: Int,
                        sourceType: String,
                        description: String,
                        imageURL: String?) async throws -> (Int, String) {
        var body: [String: Any] = [
            "source_type": sourceType,
            "description": description,
        ]
        if let imageURL, !imageURL.isEmpty {
            body["image_url"] = imageURL
        }
        var request = URLRequest(url: baseURL
            .appendingPathComponent("api/companies/\(companyId)/report"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return (json?["report_id"] as? Int ?? 0, json?["status"] as? String ?? "")
    }

    private static func validate(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        guard (200...299).contains(http.statusCode) else {
            throw URLError(.init(rawValue: http.statusCode))
        }
    }
}

struct CompanyListItem: Codable, Hashable {
    let name: String
    let level: Int
    let levelName: String
    let confidence: Double
    let disputed: Bool
}