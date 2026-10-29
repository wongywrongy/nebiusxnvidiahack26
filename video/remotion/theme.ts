// Colors from web/src/index.css (@theme), so the cards match the app.
import { loadFont } from '@remotion/google-fonts/Geist'
import { loadFont as loadMono } from '@remotion/google-fonts/GeistMono'

export const C = {
  page: '#0b0c0f', ink: '#e6e7ea', muted: '#8b8f98', soft: '#b9bdc6', faint: '#80848d', panel: '#111317', well: '#0d0e11',
  raised: '#1f2229', line: '#202329', edge: '#686e79', flare: '#f5791a', good: '#2e9e68', warn: '#e5a93b', bad: '#d9534f',
}
export const sans = loadFont('normal', { weights: ['400', '500', '600', '700'], subsets: ['latin'] }).fontFamily
export const mono = loadMono('normal', { weights: ['400', '500'], subsets: ['latin'] }).fontFamily
