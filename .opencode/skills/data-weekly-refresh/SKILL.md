---
name: data-weekly-refresh
description: 双休购数据周更运维 runbook。用于「跑采集、更新岗位、企业池榜单扩编、导出开源数据、数据周更、岗位老化、发布数据包、商品候选」等任务；含分片采集、岗位老化、导出发布与验收清单。仅用于本仓库（shuangxiugou）的数据采集与发布流程。
---

# 数据周更运维（双休购）

## 总原则（先读 AGENTS.md 的硬约束）

- 面向用户只出 L1/L2；全量（L3~L6）产物只进 `data/local/`，绝不提交
- 长任务用后台 + 日志，不要阻塞会话：`nohup ... > data/local/xxx.log 2>&1 &`，用 `tail` 轮询
- 每阶段结束必须过验收标准，再进入下一阶段

## 阶段 A：企业池榜单扩编（榜单年度更新时执行）

```bash
cd crawler
.venv/bin/python fetch_lists.py --dry-run   # 预览新增（先看数量是否合理）
.venv/bin/python fetch_lists.py             # 写 data/companies/seed_extra.csv
.venv/bin/python expand_seed.py             # 合并进 seed.csv（幂等去重）
.venv/bin/python import_seed.py             # 导入 DB（企业/品牌，幂等）
```

验收：`seed.csv` 无重复 key；新增企业全部为 L6 待验证；`git diff data/companies/seed.csv` 抽查企业名合理。

## 阶段 B：证据采集（每周）

本地分片（推荐，约 255 家/片、2~2.5h）：

```bash
cd crawler
nohup .venv/bin/python -u pipeline.py --chunk 1/4 > ../data/local/pipeline-chunk1.log 2>&1 &
tail -f ../data/local/pipeline-chunk1.log   # 轮询进度（每 25~35s/家）
```

本地增量（DB 已有历史证据时更快）：`.venv/bin/python pipeline.py --stale-days 28`

CI（云端，周更自动 / 手动）：GitHub Actions `data-refresh`，手动触发可勾选 `full` 全量；
CI 会自动从 `data/companies.json` 回灌白名单证据并全采白名单，无需人工处理。

验收：日志逐家推进无连续源失败；结束后看 `data/source_health.md`（Bing 0 条属正常诱饵）；
`verify.py` 的等级分布无突变。

## 阶段 C：岗位更新与导出

```bash
cd crawler && .venv/bin/python collect_jobs.py          # 白名单岗位采集 + 过期老化
cd ../backend && .venv/bin/python scripts/export_data.py # 更新 companies.json / jobs.json
cd ../web && npm run local                               # 重建本地版 bundle
```

验收：岗位数无明显异常缩水（老化只作用于成功来源）；新增白名单企业有岗位；
`jobs.json` 的 `generated_at` 与 `count` 已更新。

## 阶段 D：验证与发布

```bash
cd crawler && .venv/bin/python verify.py    # 企业档案/证据/等级/置信度全检
```

PR 检查清单：
- 白名单（L1/L2）数量与等级分布合理（无突增突减）
- 证据链接抽查可打开；新增白名单企业证据 ≥2 条交叉验证
- `web/local/dist` 已同步重建；`data/local/`、`*.db`、`.env` 不在提交中
- 提交信息符合规范（`chore(data): 每周数据刷新` 或 `feat(phaseN): ...`）

## 故障排查

| 现象 | 处理 |
|---|---|
| Bing 全部 0 条 | 正常（诱饵拦截），非 bug；见 `docs/sources.md` |
| 智联某企业 0 条 | 可能「有公司页、无信号岗位」或临时限速；重试该企业 `--names <key>` |
| 岗位数量骤降 | 检查 `source_health_jobs.md` 是否采集失败；老化只作用于成功来源，失败不会误删 |
| CI 白名单震荡 | 确认 `pipeline.py` 的回灌逻辑未被破坏（`rehydrate_whitelist` / `split_whitelist`） |
| 榜单解析 0 条 | 榜单页面改版 → 修 `sources/list_rankings.py` 对应解析函数，补单测 |

## 禁止事项

- 不提交 `data/local/`、`data/*.db`、`.env`、任何 L3~L6 全量数据
- 不在面向用户的页面/接口展示负面评级或非白名单企业
- 不新增负面信息源；不直抓小红书/BOSS/51job（见 `docs/sources.md`）
