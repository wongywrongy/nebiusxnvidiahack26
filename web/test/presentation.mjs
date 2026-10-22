import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const source = fs.readFileSync('src/App.tsx', 'utf8') + '\nexport { longDate, replacement, approvalNote, reviewSummary }\n'
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
const candidate = ok => ({ candidates: [{ name: 'Manufacturer product', checks: [
  { label: 'Required rating', ok, note: 'not stated' },
] }] })
assert.match(exports.replacement(candidate(null))[0], /couldn't confirm Required rating/)
assert.ok(!exports.replacement(candidate(null))[0].includes('fails'))
assert.match(exports.replacement(candidate(false))[0], /fails/)
assert.equal(exports.replacement({ suggest: 'Verified replacement' })[1], true)
const pending = 'The checked product data can be approved. Assembly proof remains pending.'
assert.match(exports.approvalNote({number: '01'}, {note_to_subcontractor: pending, validity: 'valid'}), /Assembly proof remains pending/)
assert.ok(!exports.approvalNote({title: 'Assembly'}, {summary: pending}).includes('No exceptions'))
const legacy = {summary: 'meets all requirements', note_to_subcontractor: 'meets all requirements'}
assert.match(exports.reviewSummary(legacy), /Historical result/)
assert.ok(!exports.approvalNote({title: 'Old recording'}, legacy).includes('meets all requirements'))
console.log('Presentation checks passed: source dates, unconfirmed replacement evidence and scoped approval drafts')
