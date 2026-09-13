#!/usr/bin/env bash
# 冒烟测试：启动服务并检查关键接口（部署后自检 / 本地发版前用）。
# 用法: backend/scripts/smoke.sh   （需已建 backend/.venv 并安装依赖 + 数据文件存在）
set -u
cd "$(dirname "$0")/.." || exit 1

PORT="${PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"

.venv/bin/uvicorn app.main:app --port "$PORT" > /tmp/sxg_smoke.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT

# 等待服务就绪（最多 15s）
for _ in $(seq 1 30); do
  curl -s -o /dev/null "$BASE/docs" && break
  sleep 0.5
done

pass=0; fail=0
check() { # desc expect actual
  if [ "$2" = "$3" ]; then pass=$((pass+1)); echo "  [PASS] $1 ($3)"
  else fail=$((fail+1)); echo "  [FAIL] $1 期望 $2 实际 $3"; fi
}
code() { curl -s -o /dev/null -w "%{http_code}" "$1"; }

echo "[冒烟] 服务 $BASE"
check "健康检查 /docs"                200 "$(code "$BASE/docs")"
check "隐私政策页"                    200 "$(code "$BASE/privacy/privacy.html")"
check "企业榜（仅白名单）"            200 "$(code "$BASE/api/companies")"
check "求职搜索"                      200 "$(code "$BASE/api/jobs/search?q=%E5%B7%A5%E7%A8%8B%E5%B8%88")"
check "好物搜索"                      200 "$(code "$BASE/api/goods/search?q=%E5%AF%84%E4%BB%B6")"
check "管理接口无 token 拒绝"         403 "$(code "$BASE/api/admin/jobs")"
check "纠错表单（无 token 降级路径）" 200 "$(curl -s -o /dev/null -w '%{http_code}' \
  -X POST "$BASE/api/feedback/correction" -H 'Content-Type: application/json' \
  -d '{"target":"企业档案","subject":"顺丰速运有限公司","detail":"冒烟测试提交的纠错内容"}')"

echo "[冒烟] $pass 通过 / $fail 失败"
[ "$fail" -eq 0 ]