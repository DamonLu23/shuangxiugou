import SwiftUI

/// 商品详情：企业双休卡（等级 + 置信度 + 证据数）→ 企业档案页 / 补充证据 + 到淘宝购买。
struct ProductDetailView: View {
    let product: Product
    @State private var company: CompanyDetail?
    @State private var companyLoadFailed = false
    @State private var showEvidenceReport = false

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                RoundedRectangle(cornerRadius: 20)
                    .fill(Color.gray.opacity(0.15))
                    .frame(height: 260)
                    .overlay(Image(systemName: "photo").font(.largeTitle).foregroundColor(.gray))

                VStack(alignment: .leading, spacing: 8) {
                    Text(product.title).font(.headline)
                    Text(String(format: "¥%.0f", product.price))
                        .font(.title2.bold()).foregroundColor(.sxgGreen)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 20)

                companyCard

                if let url = URL(string: product.clickUrl), !product.clickUrl.isEmpty {
                    Link(destination: url) {
                        Text("到淘宝购买")
                            .font(.headline).foregroundColor(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 14)
                            .background(Capsule().fill(Color.sxgGreen))
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
                }
            }
            .padding(.bottom, 20)
        }
        .background(Color.sxgBackground.ignoresSafeArea())
        #if canImport(UIKit)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .navigationDestination(for: CompanyDetail.self) { CompanyDetailView(company: $0) }
        .sheet(isPresented: $showEvidenceReport) {
            EvidenceReportView(
                companyId: company?.id ?? product.companyId ?? 1,
                companyName: company?.name ?? product.companyName ?? product.brand ?? "该企业"
            )
        }
        .task { await loadCompany() }
    }

    private var companyCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let company {
                NavigationLink(value: company) {
                    HStack {
                        Text(company.name).font(.headline)
                        Spacer()
                        RestBadge(level: company.restLevel)
                        Image(systemName: "chevron.right").font(.footnote).foregroundColor(.secondary)
                    }
                }
                .buttonStyle(.plain)
                VStack(spacing: 4) {
                    ProgressView(value: company.confidence).tint(.sxgGreen)
                    HStack {
                        Text("置信度 \(Int(company.confidence * 100))%")
                        Spacer()
                        Text("\(company.evidenceCount) 条证据来源")
                    }
                    .font(.caption).foregroundColor(.secondary)
                }
                if company.disputed {
                    Label("该企业档案存在争议，正在复核中", systemImage: "exclamationmark.triangle")
                        .font(.caption).foregroundColor(.sxgOrange)
                }
            } else if companyLoadFailed {
                HStack {
                    Text("企业档案加载失败")
                        .font(.caption).foregroundColor(.secondary)
                    Spacer()
                    Button("重试") { Task { await loadCompany() } }
                        .font(.caption.weight(.semibold))
                        .foregroundColor(.sxgGreen)
                }
            } else {
                HStack {
                    Text(product.companyName ?? product.brand ?? "该企业")
                        .font(.headline)
                    Spacer()
                    RestBadge(level: RestLevel(rawValue: product.restLevel ?? 6))
                }
                Text("暂未收录该企业双休档案")
                    .font(.caption).foregroundColor(.secondary)
            }
            Button("信息有误？纠错 / 补充证据") {
                showEvidenceReport = true
            }
            .font(.footnote).foregroundColor(.sxgGreen)
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 18).fill(.white)
            .shadow(color: .black.opacity(0.04), radius: 8, y: 3))
        .padding(.horizontal, 20)
    }

    private func loadCompany() async {
        guard let companyId = product.companyId, company == nil else { return }
        companyLoadFailed = false
        do {
            company = try await ApiClient.shared.company(id: companyId)
        } catch {
            // 档案加载失败不阻塞购买路径，企业卡显示失败态 + 重试
            companyLoadFailed = true
        }
    }
}