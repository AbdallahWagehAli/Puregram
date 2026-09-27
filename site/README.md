# Puregram site

The public site at https://puregram.app. Static HTML, CSS and JavaScript with no
build step, served by nginx.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Home: hero with the decision simulation, the rule, what's new, discovery, privacy, download, questions |
| `privacy.html` | Privacy Policy |
| `terms.html` | Terms of Use |
| `css/style.css` | All styling. Light and dark palettes follow the system setting |
| `js/app.js` | Arabic and English switch, per-language tab titles, the decision simulation |
| `assets/icons/` | Logo and favicon |
| `img/og.png` | Social preview image (1200 by 630) |

## Copy rules

- Every translatable node carries `data-ar` and `data-en`. The markup ships in
  Arabic, so the page reads correctly before the script runs.
- No em dash or en dash anywhere, including tab titles and comments. Use a
  period, a comma, a colon, or the middle dot `·` as a title separator.
- Facts on the page must match the server and the apps: versions, sizes and
  SHA-256 fingerprints in the download cards come from the files actually served
  under `/download/`, and the privacy text lists exactly what the server stores.

## On each release

1. Update the version, size and SHA-256 in the download cards of `index.html`,
   plus the eyebrow line in the hero and the "What's new" block.
2. Check the pages for dash characters:
   `python -c "import pathlib,re;d='[%s-%s]'%(chr(0x2010),chr(0x2015));[print(p) for p in pathlib.Path('.').rglob('*.*') if re.search(d,p.read_text('utf-8','ignore'))]"`
3. Deploy with `bash deploy/release-policy.sh site` from the repository root.

