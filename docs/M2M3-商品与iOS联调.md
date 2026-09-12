# M2/M3 完成记录（2026-09-11）

## M2 商品链路

| 组件 | 文件 | 说明 |
|---|---|---|
| 品牌→企业映射 | backend/app/services/brand.py | seed.csv 导入（幂等）；商品标题最长匹配识别（避免 OPPOReno 错分）；`import_seed` / `build_lookup` / `extract_brand` |
| 淘宝联盟客户端 | backend/app/services/mall.py | `taobao.tbk.dg.material.optional` 真实签名请求；**未配 AppKey 时自动 mock** 演示商品（含真实双休档案品牌，验证排序链路） |
| 搜索排名 API | backend/app/routers/search.py | `GET /api/search?q=&level=&sort=`：联盟搜索 → 标题提取品牌 → 企业双休档案打标 → rest_first 排序（L1 严格双休优先，未收录最后） |

> 配置 `TAOBAO_APPKEY / TAOBAO_SECRET / TAOBAO_ADZONE_ID` 环境变量即切真实联盟；当前开发用 mock。
> 本应用仅以联盟作商品数据源，不运营返佣。

## M3 iOS 联调

| 页面 | 数据源 |
|---|---|
| 搜索 → 商品列表 | `GET /api/search`（后端已完成品牌打标+双休优先排序） |
| 商品详情 | 列表传入打标数据 + `GET /api/companies/{id}` 拉真实档案（等级/置信度/证据数） |
| 双休企业好物榜 | `GET /api/companies?limit=100`（L1 优先） |
| 企业档案页 | `GET /api/companies/{id}`：大徽章 + 置信度 + 证据来源时间线 + 补充证据入口 |
| 补充证据 | 通用 `EvidenceReportView`（多页复用）→ `POST /api/companies/{id}/report` |

契约验证脚本 /tmp/contract_check.py（search/product、company detail、evidence item、list 四组字段对齐，convertFromSnakeCase）。

## 验证

- 后端 11 测试（品牌映射/签名/mock/搜索链路/排序/筛选/DB 等级联动）ALL PASS
- crawler 13 测试 + M1 verify 5 项 ALL PASS
- HTTP 端到端：`/api/search?q=键盘` → L1 顺丰 → L2 苏泊尔 → L4 华为 → L6 待验证，筛选/排序全部正确
- iOS 8 文件 macOS SDK typecheck CLEAN
- 契约验证 7 项 ALL PASS

## 遗留（M4 上架前置）

- [ ] M0 人工资质：域名/服务器/ICP 备案(个体户)/淘宝联盟 AppKey/Apple 开发者 → 见 docs/M0-资质清单.md
- [ ] iOS 需要真机/模拟器运行确认（本机无 Xcode 完整版，已用 macOS SDK typecheck + 契约验证兜底）
- [ ] App 图标/启动图/隐私政策页面上线
- [ ] TestFlight 内测 → 中国区上架