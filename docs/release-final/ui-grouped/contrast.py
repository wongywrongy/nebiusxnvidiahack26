# WCAG contrast for every text pair this pass touches; fails the run below 4.5:1.
def lum(h):
    c = [int(h[i:i+2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
bg = {'page': '#0b0c0f', 'panel': '#16191e', 'well': '#1e2128', 'raised': '#262a32', 'selected': '#2f343d'}
pairs = [(f'{t} on {b}', c, bg[b]) for t, c in [('ink', '#f2f3f5'), ('soft', '#cfd3da'), ('muted', '#a6abb4'), ('faint', '#a0a5ae')] for b in bg]
pairs += [('red value on panel', '#e5534b', bg['panel']), ('blue value on panel', '#7fa7d9', bg['panel']),
          ('amber value on panel', '#e5a93b', bg['panel']), ('green on panel', '#2e9e68', bg['panel']),
          ('.btn text on #262a32', '#f2f3f5', '#262a32'),
          ('glyph meets', '#06150d', '#2e9e68'), ('glyph fails', '#1d0606', '#e5534b'), ('glyph option', '#1e1403', '#e5a93b'),
          ('glyph not confirmed on panel', '#a9c8f0', bg['panel']), ('glyph not confirmed on raised (row hover)', '#a9c8f0', bg['raised']),
          ('pill revise', '#ff9e99', '#3a1414'), ('pill exceptions', '#a9c8f0', '#12233a'), ('pill no exceptions', '#6be0a6', '#10291d'),
          ('pill not reviewed', '#a6abb4', bg['panel'])]
bad = 0
print('| Pair | Text | Background | Ratio |\n|---|---|---|---|')
for name, fg, b in pairs:
    r = ratio(fg, b); bad += r < 4.5
    print(f'| {name} | `{fg}` | `{b}` | {r:.2f}:1{"  FAIL" if r < 4.5 else ""} |')
raise SystemExit(bad)
