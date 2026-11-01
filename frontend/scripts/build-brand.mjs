// Renders the favicons, app icons and PNG exports from lib/brand.ts: `npm run brand`.
import { mkdir, writeFile } from "node:fs/promises"
import { resolve } from "node:path"
import sharp from "sharp"
import {
  INK,
  MARK_PATH,
  MARK_VIEW_BOX,
  PAPER,
  WORDMARK_PATH,
} from "../lib/brand.ts"

const root = resolve(import.meta.dirname, "..")
const out = (path) => resolve(root, path)

const mark = (fill) => `<path fill="${fill}" fill-rule="evenodd" d="${MARK_PATH}"/>`
const svg = (viewBox, body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">${body}</svg>\n`

const markSvg = (fill) => svg(MARK_VIEW_BOX, mark(fill))
const logoSvg = (fill) =>
  svg(
    "0 0 680 200",
    `${mark(fill)}<path fill="${fill}" transform="translate(236 148) scale(1.4)" d="${WORDMARK_PATH}"/>`,
  )

// The browser tab can be dark, so the vector favicon follows the system theme.
const tabIconSvg = svg(
  MARK_VIEW_BOX,
  `<style>path{fill:${INK}}@media (prefers-color-scheme:dark){path{fill:${PAPER}}}</style>` +
    `<path fill-rule="evenodd" d="${MARK_PATH}"/>`,
)

// Mark on a paper square. `share` is the part of the square the mark takes up;
// 0.62 stays inside the safe zone of maskable icons.
const tileSvg = (share, radius = 0) => {
  const offset = (200 * (1 - share)) / 2
  return svg(
    MARK_VIEW_BOX,
    `<rect width="200" height="200" rx="${radius}" fill="${PAPER}"/>` +
      `<g transform="translate(${offset} ${offset}) scale(${share})">${mark(INK)}</g>`,
  )
}

const png = (source, width) =>
  sharp(Buffer.from(source), { density: 600 }).resize({ width }).png().toBuffer()

// An ICO is a directory of embedded PNGs.
const ico = (images) => {
  const header = Buffer.alloc(6 + 16 * images.length)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(images.length, 4)
  let offset = header.length
  images.forEach(({ size, data }, i) => {
    const entry = 6 + 16 * i
    header.writeUInt8(size, entry)
    header.writeUInt8(size, entry + 1)
    header.writeUInt16LE(1, entry + 4)
    header.writeUInt16LE(32, entry + 6)
    header.writeUInt32LE(data.length, entry + 8)
    header.writeUInt32LE(offset, entry + 12)
    offset += data.length
  })
  return Buffer.concat([header, ...images.map(({ data }) => data)])
}

const socialCard = () => {
  const width = 680 * 1.1
  const x = (1200 - width) / 2
  const y = (630 - 200 * 1.1) / 2
  return svg(
    "0 0 1200 630",
    `<rect width="1200" height="630" fill="${PAPER}"/>` +
      `<g transform="translate(${x} ${y}) scale(1.1)">${logoSvg(INK).replace(/^<svg[^>]*>|<\/svg>\n$/g, "")}</g>`,
  )
}

await mkdir(out("public/brand"), { recursive: true })

const favicon = await Promise.all(
  [16, 32, 48].map(async (size) => ({
    size,
    data: await png(tileSvg(0.86, 36), size),
  })),
)

const files = {
  "app/icon.svg": tabIconSvg,
  "app/favicon.ico": ico(favicon),
  "app/apple-icon.png": await png(tileSvg(0.68), 180),
  "app/opengraph-image.png": await png(socialCard(), 1200),
  "public/brand/icon-192.png": await png(tileSvg(0.62), 192),
  "public/brand/icon-512.png": await png(tileSvg(0.62), 512),
  "public/brand/corvus-mark.svg": markSvg(INK),
  "public/brand/corvus-mark-light.svg": markSvg(PAPER),
  "public/brand/corvus-logo.svg": logoSvg(INK),
  "public/brand/corvus-logo-light.svg": logoSvg(PAPER),
  "public/brand/corvus-mark-1024.png": await png(markSvg(INK), 1024),
  "public/brand/corvus-logo-2000.png": await png(logoSvg(INK), 2000),
}

await Promise.all(
  Object.entries(files).map(([path, data]) => writeFile(out(path), data)),
)
