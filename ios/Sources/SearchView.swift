import SwiftUI

/// 首页：大搜索框 + 双休好物榜入口 + slogan。
struct SearchView: View {
    @State private var query = ""
    @State private var submitted = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()
                VStack(spacing: 8) {
                    Image(systemName: "leaf.fill")
                        .font(.system(size: 44))
                        .foregroundColor(.sxgGreen)
                    Text("双休购")
                        .font(.largeTitle.bold())
                    Text("买东西，支持双休")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 8)

                HStack(spacing: 12) {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("搜索商品，如「键盘」「咖啡」", text: $query)
                        .submitLabel(.search)
                        .onSubmit { submitted = query }
                    RestBadge(level: .strict)
                }
                .padding(16)
                .background(Capsule().fill(.white).shadow(color: .black.opacity(0.05), radius: 12, y: 4))
                .padding(.horizontal, 28)

                Button("搜索") { submitted = query }
                    .font(.headline)
                    .foregroundColor(.white)
                    .padding(.horizontal, 48).padding(.vertical, 12)
                    .background(Capsule().fill(Color.sxgGreen))

                Spacer()

                NavigationLink("双休企业好物榜", value: "rank")
                    .font(.headline)
                    .foregroundColor(.sxgGreen)
                    .padding(.bottom, 32)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.sxgBackground.ignoresSafeArea())
            .navigationDestination(for: String.self) { dest in
                if dest == "rank" {
                    RankingView()
                } else {
                    ProductListView(query: submitted)
                }
            }
        }
        .tint(.sxgGreen)
    }
}