// Render many stills of the SpecCheck cut from one bundle: npx tsx remotion/stills.ts <out dir> <frame>[:name] ...
import { bundle } from '@remotion/bundler'
import { renderStill, selectComposition } from '@remotion/renderer'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const [dir, ...args] = process.argv.slice(2)
fs.mkdirSync(dir, { recursive: true })
const serveUrl = await bundle({ entryPoint: path.join(ROOT, 'remotion/index.ts'), publicDir: path.join(ROOT, 'out/stage') })
const composition = await selectComposition({ serveUrl, id: 'SpecCheck' })
for (const a of args) {
  const [frame, name] = a.split(':')
  await renderStill({ serveUrl, composition, frame: Number(frame), output: path.join(dir, `${name ?? frame}.png`) })
  console.log(frame, name ?? '')
}
