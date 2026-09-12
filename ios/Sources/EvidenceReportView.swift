import SwiftUI

/// 通用「补充证据」组件：任意页面传入 companyId 即可复用。
/// 后端：POST /api/companies/{companyId}/report → pending 队列，人工审核后生效。
struct EvidenceReportView: View {
    let companyId: Int
    let companyName: String

    @Environment(\.dismiss) private var dismiss

    /// 证据类型（决定审核通过后的权重：合同 1.0 / offer 0.9 / 其他 0.5）
    enum SourceType: String, CaseIterable, Identifiable {
        case contract = "ugc_contract"
        case offer = "ugc_offer"
        case other = "ugc_other"

        var id: String { rawValue }

        var name: String {
            switch self {
            case .contract: return "劳动合同 / 工资条"
            case .offer: return "Offer 截图"
            case .other: return "其他"
            }
        }

        var hint: String {
            switch self {
            case .contract: return "最具说服力（人工审核后权重最高）"
            case .offer: return "入职确认单等（截图请打码敏感信息）"
            case .other: return "口头说明实际工时安排"
            }
        }
    }

    @State private var sourceType: SourceType = .contract
    @State private var description = ""
    @State private var imageURL = ""
    @State private var submitting = false
    @State private var errorMessage: String?
    @State private var result: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("证据类型") {
                    Picker("来源", selection: $sourceType) {
                        ForEach(SourceType.allCases) { Text($0.name).tag($0) }
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                    Text(sourceType.hint)
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }

                Section("实际工时安排（必填）") {
                    TextEditor(text: $description)
                        .frame(minHeight: 90)
                        .overlay(alignment: .topLeading) {
                            if description.isEmpty {
                                Text("例如：劳动合同约定五天工作制，周末双休，基本不加班")
                                    .foregroundColor(.gray.opacity(0.6))
                                    .padding(.top, 8).padding(.leading, 5)
                                    .allowsHitTesting(false)
                            }
                        }
                }

                Section("截图链接（可选，打码后）") {
                    TextField("https://…", text: $imageURL)
                        #if canImport(UIKit)
                        .keyboardType(.URL)
                        #endif
                    Text("不要上传含身份证/银行卡等敏感信息的截图")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }

                if let errorMessage {
                    Section {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.circle.fill")
                            Text(errorMessage).font(.footnote)
                        }
                        .foregroundColor(.red)
                    }
                }

                if let result {
                    Section {
                        HStack(spacing: 6) {
                            Image(systemName: "checkmark.circle.fill")
                            Text(result).font(.footnote)
                        }
                        .foregroundColor(.sxgGreen)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        HStack(spacing: 8) {
                            if submitting { ProgressView() }
                            Text("提交证据")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(submitting || description.trimmingCharacters(in: .whitespaces).count < 5)
                } footer: {
                    Text("提交后进入人工审核队列（一般 1~3 个工作日），通过后计入企业双休评级。")
                }
            }
            .navigationTitle("为 \(companyName) 补充证据")
            #if canImport(UIKit)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
            }
        }
        .tint(.sxgGreen)
    }

    private func submit() async {
        submitting = true
        errorMessage = nil
        defer { submitting = false }
        do {
            let (_, status) = try await ApiClient.shared.reportEvidence(
                companyId: companyId,
                sourceType: sourceType.rawValue,
                description: description.trimmingCharacters(in: .whitespacesAndNewlines),
                imageURL: imageURL.isEmpty ? nil : imageURL
            )
            result = status == "pending" ? "已受理 ✅ 1~3 个工作日内生效" : "已提交（状态：\(status)）"
        } catch {
            errorMessage = "提交失败，请稍后重试（\(error.localizedDescription)）"
        }
    }
}