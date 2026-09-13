// Web API 层纯函数测试（api.js 无 DOM 依赖部分）。
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { LEVEL_NAMES, levelBadgeClass } from '../src/api.js'

test('LEVEL_NAMES 覆盖 1~6 级', () => {
  assert.deepEqual(Object.keys(LEVEL_NAMES).map(Number).sort(), [1, 2, 3, 4, 5, 6])
  assert.equal(LEVEL_NAMES[1], '严格双休')
  assert.equal(LEVEL_NAMES[6], '待验证')
})

test('levelBadgeClass：白名单/非白名单样式区分', () => {
  assert.equal(levelBadgeClass(1), 'l1')
  assert.equal(levelBadgeClass(2), 'l2')
  assert.equal(levelBadgeClass(3), 'unknown')
  assert.equal(levelBadgeClass(6), 'unknown')
  assert.equal(levelBadgeClass(undefined), 'unknown')
})