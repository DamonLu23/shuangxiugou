import SwiftUI

/// 商品列表：卡片 = 图 + 标题 + 价格 + 双休等级徽章；筛选条 + 双休优先排序（后端已排序）。
struct ProductListView: View {
    let query: String
    @State private var products: [Product] = []
    @State private var filterLevel: RestLevel? = nil
    /// 只看已收录双休档案的商品（默认开：避免满屏「待验证」稀释核心体验）
    @State private var indexedOnly = true
    @State private var isLoading = true
    @State private var loadError: String?

    var visible: [Product] {
        products.filter { filterLevel == nil || $0.restLevel == filterLevel?.rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    indexedChip
                    ForEach(RestLevel.allCases) { lv in
                        FilterChip(level: lv, selected: filterLevel == lv) {
                            filterLevel = filterLevel == lv ? nil : lv
                        }
                    }
                }
                .padding(.horizontal, 16).padding(.vertical, 10)
            }

            if isLoading {
                Spacer()
                ProgressView("正在搜索「\(query)」…")
                Spacer()
            } else if let loadError {
                errorView(loadError)
            } else if visible.isEmpty {
                ContentUnavailableView("暂无商品", systemImage: "tray",
                                       description: Text(indexedOnly
                                          ? "已收录企业中暂无匹配商品，可关闭「只看已收录」查看全部"
                                          : "换个关键词试试，或等待联盟商品库接入"))
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(visible) { p in
                            NavigationLink(value: p) {
                                ProductCard(product: p)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(16)
                }
                .refreshable { await load() }
            }
        }
        .background(Color.sxgBackground.ignoresSafeArea())
        .navigationTitle(query)
        #if canImport(UIKit)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .navigationDestination(for: Product.self) { ProductDetailView(product: $0) }
        .task { await load() }
    }

    private var indexedChip: some View {
        Button {
            indexedOnly.toggle()
            Task { await load() }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: indexedOnly ? "checkmark.circle.fill" : "circle")
                Text("只看已收录")
            }
            .font(.footnote.weight(indexedOnly ? .semibold : .regular))
            .foregroundColor(indexedOnly ? .sxgGreen : .secondary)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(Capsule().fill(Color.sxgGreen.opacity(indexedOnly ? 0.12 : 0.05)))
        }
        .buttonStyle(.plain)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            ContentUnavailableView("加载失败", systemImage: "wifi.exclamationmark",
                                   description: Text(message))
            Button("重试") { Task { await load() } }
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.white)
                .padding(.horizontal, 28).padding(.vertical, 8)
                .background(Capsule().fill(Color.sxgGreen))
        }
    }

    private func load() async {
        isLoading = true
        loadError = nil
        defer { isLoading = false }
        do {
            products = try await ApiClient.shared.search(q: query, indexedOnly: indexedOnly)
        } catch {
            loadError = "无法连接后端（\(error.localizedDescription)）\n请确认已启动 uvicorn 且模拟器可访问本机 8000 端口"
        }
    }
}

private struct FilterChip: View {
    let level: RestLevel
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                if level != .unknown { Circle().fill(level.color).frame(width: 8, height: 8) }
                Text(level.name)
            }
            .font(.footnote.weight(selected ? .semibold : .regular))
            .foregroundColor(selected ? .white : level.color)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(Capsule().fill(selected ? level.color : level.color.opacity(0.12)))
        }
        .buttonStyle(.plain)
    }
}

struct ProductCard: View {
    let product: Product

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.gray.opacity(0.15))
                .frame(width: 88, height: 88)
                .overlay(Image(systemName: "photo").foregroundColor(.gray))
            VStack(alignment: .leading, spacing: 6) {
                Text(product.title)
                    .font(.subheadline)
                    .lineLimit(2)
                    .foregroundColor(.primary)
                Text(product.brand ?? "品牌未收录")
                    .font(.caption)
                    .foregroundColor(.secondary)
                HStack {
                    Text(String(format: "¥%.0f", product.price))
                        .font(.headline)
                        .foregroundColor(.sxgGreen)
                    Spacer()
                    RestBadge(level: RestLevel(rawValue: product.restLevel ?? 6))
                }
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 18).fill(.white).shadow(color: .black.opacity(0.04), radius: 8, y: 3))
    }
}