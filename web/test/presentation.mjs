import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const source = fs.readFileSync('src/App.tsx', 'utf8') + '\nexport { longDate, reviewSummary }\n'
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText
const exports = {}
vm.runInNewContext(compiled, {
  exports,
  require: name => name.startsWith('./') ? {} : require(name),
})

assert.equal(exports.longDate('June 30th, 2024'), 'June 30th, 2024')
assert.ok(!exports.longDate('2024-06-30').includes('Invalid Date'))
const legacy = {summary: 'meets all requirements', note_to_subcontractor: 'meets all requirements'}
assert.match(exports.reviewSummary(legacy), /Historical result/)
console.log('Presentation checks passed: source dates and historical summaries (drafts are tested in tests/test_customer_feedback.py)')
