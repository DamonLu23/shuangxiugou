import SwiftUI

/// 企业双休档案页：等级大徽章 + 置信度 + 证据时间线 + 补充证据入口。
struct CompanyDetailView: View {
    let company: CompanyDetail

    @State private var showEvidenceReport = false

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                heroCard
                evidenceSection
                disclaimer
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 24)
        }
        .background(Color.sxgBackground.ignoresSafeArea())
        #if canImport(UIKit)
        .navigationBarTitleDisplayMode(.inline)
        #endif
        .sheet(isPresented: $showEvidenceReport) {
            EvidenceReportView(companyId: company.id, companyName: company.name)
        }
    }

    private var heroCard: some View {
        VStack(spacing: 14) {
            RestBadge(level: company.restLevel, prominent: true)
                .scaleEffect(1.4)
                .padding(.top, 14)
            Text(company.name)
                .font(.title3.bold())
                .multilineTextAlignment(.center)
                .padding(.horizontal, 8)
            Text(company.disputed ? "⚠️ 档案存在争议，复核中" : "基于 \(company.evidenceCount) 条公开证据交叉验证")
                .font(.caption)
                .foregroundColor(company.disputed ? .sxgOrange : .secondary)

            VStack(spacing: 4) {
                ProgressView(value: company.confidence)
                    .tint(.sxgGreen)
                HStack {
                    Text("置信度 \(Int(company.confidence * 100))%")
                    Spacer()
                    Text("数据更新：\(company.evidenceCount) 个来源")
                }
                .font(.caption).foregroundColor(.secondary)
            }

            Button {
                showEvidenceReport = true
            } label: {
                Label("补充证据", systemImage: "plus.circle")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Capsule().fill(Color.sxgGreen))
            }
            .buttonStyle(.plain)
        }
        .padding(18)
        .background(RoundedRectangle(cornerRadius: 22).fill(.white)
            .shadow(color: .black.opacity(0.05), radius: 10, y: 4))
    }

    private var evidenceSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("证据来源（公开渠道）")
                .font(.headline)
            ForEach(Array(company.evidences.enumerated()), id: \.offset) { pair in
                let ev = pair.element
                let isLast = pair.offset == company.evidences.count - 1
                evidenceRow(ev)
                if !isLast {
                    Divider().opacity(0.3)
                }
            }
            if company.evidences.isEmpty {
                HStack {
                    Spacer()
                    Text("暂无公开证据，欢迎补充")
                        .font(.footnote).foregroundColor(.secondary)
                    Spacer()
                }
                .padding(.vertical, 20)
            }
        }
    }

    private var disclaimer: some View {
        Text("双休等级由公开渠道信息交叉验证生成，仅供参考，可能与企业实际情况存在出入。如信息有误，欢迎通过「补充证据」提交更正。")
            .font(.caption2)
            .foregroundColor(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 4)
    }

    private func sourceIcon(_ type: String) -> String {
        switch type {
        case "ugc_contract": return "doc.text"
        case "ugc_offer": return "envelope"
        case "job_post": return "briefcase"
        default: return "text.bubble"
        }
    }

    private func sourceName(_ type: String) -> String {
        switch type {
        case "ugc_contract": return "劳动合同/工资条"
        case "ugc_offer": return "Offer 截图"
        case "job_post": return "招聘岗位描述"
        case "review": return "员工口碑"
        case "review_promo": return "公开信息（低权重）"
        default: return "其他来源"
        }
    }

    private func evidenceRow(_ ev: EvidenceItem) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: sourceIcon(ev.sourceType))
                    .font(.caption)
                    .foregroundColor(.sxgGreen)
                Text(sourceName(ev.sourceType))
                    .font(.caption.weight(.semibold))
                Spacer()
                Text("\(Int(ev.rawScore))")
                    .font(.caption2.monospaced())
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(Capsule().fill(ev.rawScore >= 0
                                               ? Color.sxgMint.opacity(0.25)
                                               : Color.sxgRed.opacity(0.18)))
            }
            Text(ev.title.isEmpty ? "（无标题，见来源链接）" : ev.title)
                .font(.footnote)
                .lineLimit(2)
                .foregroundColor(.primary)
            Text("关键词：\(ev.keywords.joined(separator: "、")) · \(ev.collectedAt)")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(.white))
    }
}