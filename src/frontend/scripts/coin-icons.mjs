// Copies free coin symbols into public/coins/<SYMBOL>.svg before dev and build, so the app
// shows real symbols without asking anyone on the internet (ADR 0031). Sources:
// @web3icons/core (MIT, branded tokens), cryptocurrency-icons (CC0) for what the first lacks.
// One file per coin: the browser loads only the symbols a page shows.
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const out = path.resolve('public/coins')
// node_modules paths directly: @web3icons/core does not export its package.json
const web3 = path.resolve('node_modules/@web3icons/core/dist/svgs/tokens/branded')
const cci = path.resolve('node_modules/cryptocurrency-icons/svg/color')
// Asset symbols in our data that the icon sets name differently.
const ALIASES = { RENDER: 'RNDR', POL: 'POL', WBTC: 'WBTC' }
// Native coins whose token logo is missing, taken from the same set's network logos.
const networks = path.resolve('node_modules/@web3icons/core/dist/svgs/networks/branded')
const NETWORK_COINS = { RON: 'ronin' }

// Exchange, wallet and network logos from the same set (M7): public/logos/<kind>/<name>.svg
const logos = path.resolve('public/logos')
if (!fs.existsSync(path.join(logos, '.complete'))) {
  let m = 0
  for (const kind of ['exchanges', 'wallets', 'networks']) {
    const dir = path.resolve(`node_modules/@web3icons/core/dist/svgs/${kind}/branded`)
    fs.mkdirSync(path.join(logos, kind), { recursive: true })
    for (const f of fs.readdirSync(dir)) {
      if (!f.endsWith('.svg.js')) continue
      const mod = await import(pathToFileURL(path.join(dir, f)).href).catch(() => null)
      if (typeof mod?.default !== 'string') continue
      fs.writeFileSync(path.join(logos, kind, f.replace('.svg.js', '.svg')), mod.default)
      m++
    }
  }
  fs.writeFileSync(path.join(logos, '.complete'), String(m))
  console.log(`logos: ${m}`)
}

if (fs.existsSync(path.join(out, '.complete'))) process.exit(0)
fs.mkdirSync(out, { recursive: true })
let n = 0
for (const f of fs.readdirSync(web3)) {
  if (!f.endsWith('.svg.js')) continue
  const mod = await import(pathToFileURL(path.join(web3, f)).href).catch(() => null)
  if (typeof mod?.default !== 'string') continue
  fs.writeFileSync(path.join(out, f.replace('.svg.js', '.svg')), mod.default)
  n++
}
for (const f of fs.readdirSync(cci)) {
  const target = path.join(out, f.replace('.svg', '').toUpperCase() + '.svg')
  if (!fs.existsSync(target)) { fs.copyFileSync(path.join(cci, f), target); n++ }
}
for (const [asset, network] of Object.entries(NETWORK_COINS)) {
  const target = path.join(out, `${asset}.svg`)
  const mod = fs.existsSync(target) ? null : await import(pathToFileURL(path.join(networks, `${network}.svg.js`)).href).catch(() => null)
  if (typeof mod?.default === 'string') { fs.writeFileSync(target, mod.default); n++ }
}
for (const [asset, icon] of Object.entries(ALIASES)) {
  const from = path.join(out, `${icon}.svg`), to = path.join(out, `${asset}.svg`)
  if (asset !== icon && fs.existsSync(from) && !fs.existsSync(to)) fs.copyFileSync(from, to)
}
fs.writeFileSync(path.join(out, '.complete'), String(n))
console.log(`coin icons: ${n}`)
