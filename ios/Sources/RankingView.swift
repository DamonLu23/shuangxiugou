import SwiftUI

/// 双休企业好物榜：按企业档案等级排序的列表（L1 严格双休优先）。
struct RankingView: View {
    @State private var companies: [CompanyListItem] = []
    @State private var isLoading = true
    @State private var loadError: String?

    var body: some View {
        Group {
            if isLoading {
                ProgressView("正在加载企业档案…")
            } else if let loadError {
                ContentUnavailableView("加载失败", systemImage: "wifi.exclamationmark",
                                       description: Text(loadError))
            } else if companies.isEmpty {
                ContentUnavailableView("暂无档案", systemImage: "tray")
            } else {
                List {
                    ForEach(companies, id: \.name) { item in
                        HStack(spacing: 12) {
                            RestBadge(level: RestLevel(rawValue: item.level))
                                .frame(width: 76, alignment: .leading)
                            Text(item.name)
                                .font(.subheadline)
                                .lineLimit(1)
                            Spacer()
                            Text("\(Int(item.confidence * 100))%")
                                .font(.caption.monospaced())
                                .foregroundColor(.secondary)
                        }
                        .padding(.vertical, 2)
                        .listRowBackground(Color.sxgBackground)
                    }
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("双休企业好物榜")
        #if canImport(UIKit)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            companies = try await ApiClient.shared.companies(limit: 100)
        } catch {
            loadError = "无法连接后端（\(error.localizedDescription)）"
        }
    }
}