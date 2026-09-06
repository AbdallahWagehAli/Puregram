# Puregram — Public Marketing Site

Static, bilingual (Arabic-first RTL / English LTR) marketing site for **Puregram** — an
**unofficial, independent build based on Telegram's open-source clients** (Android + Desktop).
Puregram adds one thing on top of Telegram: a **content-control layer** — a per-account
allow-list of chats enforced by the client, with **pornography and spam blocked**.

> Honest positioning: this is **not** official Telegram, **not** affiliated with or endorsed by
> Telegram, and **not** a from-scratch app. "Telegram" is a trademark of its owners. The site states
> this openly (hero tag, "What it is / isn't" section, and a footer disclaimer on every page).

Static HTML/CSS/JS only — **no framework, no build step** (served by nginx). Brand: leaf green `#2E9E4F`
+ gold `#D4AF37` on dark navy. Dark theme default, with a light toggle. Logo: the green leaf /
gold-ring / gold-midrib / verified-seal mark.

---

## Files

| Path | Purpose |
|---|---|
| `index.html` | Single-page site (sections below) |
| `privacy.html` | Privacy Policy — bilingual, new honest positioning |
| `terms.html` | Terms of Service — bilingual, new honest positioning |
| `css/style.css` | Design system: dark-default + light theme, RTL-first, responsive, terminal/architecture motifs |
| `js/app.js` | Language toggle (AR/EN), theme toggle (dark/light), mobile menu, FAQ accordion, scroll reveal, year, "coming soon" toast |
| `assets/icons/logo.svg` | The Puregram logo — used in nav, hero, supervision card, CTA, footer, and the favicon family |
| `assets/icons/favicon.svg` | Favicon |
| `img/*.png` | Legacy generated photography (hero/family/support/privacy) — kept; the redesign uses code/diagram motifs instead |

### Sections on `index.html`
1. **Hero** — positioning tag ("unofficial independent build based on Telegram"), a terminal motif showing the whitelist poll, CTAs to the **APK** and to **How supervision works** (`#how`).
2. **Trust strip** — platforms / base / supervision / price at a glance.
3. **ما هو — وما ليس هو** (What it is / What it isn't) — the honest two-column statement + inline trademark line.
4. **كيف يعمل** (How it works) — device-to-device linking diagram (supervised account → consent-based link → supervisor account) + a 4-step in-app pairing flow.
5. **ما المحجوب** (What's blocked) — porn, spam, unapproved chats, untrusted links.
6. **الإشراف داخل التطبيق** (In-app supervision) — the native supervision story with an in-app toggle UI mock; CTA to download.
7. **البنية والثقة** (Architecture & trust) — messaging stays on Telegram, what the control plane stores (account id, reported chats, per-account whitelist), no ads/tracking, consent-based linking.
8. **المنصّات والتحميل** (Platforms & download) — Android APK (now), Desktop (soon). **Main app only** — the retired web Control SPA and separate Control APK are gone.
9. **FAQ** — questions reframed around the new positioning.
10. **CTA band** + footer with the **trademark/affiliation disclaimer**.

---

## In-app supervision (device-based, all-native)
There is **no website login and no web control app**. All supervision happens **inside the app**
(Settings ▸ Puregram):

- The **supervised** account shows a **60-second rotating code + QR**.
- The **supervisor** scans the QR or enters the code from **their own app**.
- **Both sides confirm** in-app (consent-based; either side can unlink anytime).
- The supervisor then **toggles which chats are allowed**, **per Telegram account**.

Filtering is **per-account** and **deny-by-default when supervised**: each account is filtered
independently, and any account **no one supervises behaves like normal Telegram** with no restrictions.
No email, no password, no WebView, no separate Control download.

---

## Local preview
```bash
cd Puregram/site
python -m http.server 8099
# open http://localhost:8099
```
Verify: language toggle (EN/ع), theme toggle (☀/☾), mobile menu, FAQ accordion, scroll reveal,
and the "coming soon" toast on the Desktop/Notify buttons.

---

## TODO before launch
- [ ] **Real APK** at `https://puregram.app/download/puregram.apk` (every download link assumes it).
- [ ] **OG image** — `og:image` points at `https://puregram.app/img/hero.png`; confirm once live.
- [ ] **Legal review** — `privacy.html` / `terms.html` are honest bilingual drafts, not lawyer-reviewed; confirm the data-handling claims match the shipped control plane.
- [ ] **Analytics / sitemap / robots.txt** — add per hosting setup.
