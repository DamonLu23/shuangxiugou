# 贡献指南

感谢参与「双休购」：只推荐双休企业的开源项目。

## 三种贡献方式

### 1. 提交企业证据（数据准确性核心）

白名单档案的证据来源类型与权重：

| 来源 | 权重 | 需要什么 |
|---|---|---|
| `ugc_contract` | 1.0 | 劳动合同/工资条（截图请脱敏：姓名、身份证、金额可留） |
| `ugc_offer` | 0.9 | Offer 截图（脱敏后） |
| `review` | 0.9 | 员工口碑（知乎/牛客/脉脉等的公开链接） |
| `job_post` | 0.4 | 招聘岗位描述的公开链接（明确写「双休/做五休二」） |
| `review_promo` | 0.1 | 一般公开报道（权重低，仅供参考） |

**提交方式**：PR 修改 `data/companies_all.json` 不行——数据由仓库每周自动生成，请改为：
- 提供**证据链接** + 企业全名，在 Issue 或 PR 中说明，维护者将证据加入证据库后重跑生成
- 或在 `data/evidences.json` 的 PR 中附带新证据条目（`company_name` + `url` + `keywords` + 来源类型）

### 2. 维护好物目录

`data/goods.csv` 列：

```csv
company_name,category,product,official_link,note
顺丰速运有限公司,物流服务,顺丰寄件,https://www.sf-express.com,示例
```

规则：
- **只允许收录白名单（L1/L2）企业**的商品
- 链接指向品牌官方店/官网（不收录第三方分销链接）
- 每家建议 1~5 件代表商品，品类标注准确

### 3. 反馈与上报

- **岗位失效**：白名单岗位链接打不开 → Issue 标注「岗位失效」，维护者下架
- **档案争议**：走 [APPEAL.md](APPEAL.md) 企业申诉流程
- **Bug/功能建议**：直接提 Issue

## 开发环境

```bash
# 后端
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# 测试
cd backend && .venv/bin/python -m pytest tests/ -q
cd crawler && .venv/bin/python -m pytest tests/ -q

# 数据校验
cd crawler && .venv/bin/python verify.py
```

## 提交规范

- PR 描述写明改动动机与验证方式
- 数据类 PR：附证据链接；代码类 PR：附测试结果
- 保持「白名单承诺」：严禁在面向用户的代码/数据中引入负面展示

## 讨论

- Issue 用于问题与申诉
- 社区规范：理性讨论，尊重证据