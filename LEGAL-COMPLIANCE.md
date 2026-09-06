# Puregram — legal position before publishing on Google Play

Researched 2026-09-05 against the primary sources, not from memory. Every claim below
links to where it comes from. This is a compliance review, not legal advice.

Three bodies of rules apply at once, and they are not the same rules:

1. the **GNU GPL**, because the code we build on is copyleft;
2. **Telegram's API Terms of Service**, because we connect to their network with an `api_id`;
3. **Google Play's developer policies**, because that is where we are publishing.

A fork can satisfy any two and still be taken down over the third.

---

## 1. The GPL

### What licence, exactly

| Component | Licence | Where it says so |
|---|---|---|
| `telegram/telegram-android/` | **GPL v2 or later** | every source header: "It is licensed under GNU GPL v. 2 or later"; `LICENSE` carries the GPLv2 text |
| `telegram/tdesktop/` | **GPL v3 or later**, with the OpenSSL exception | upstream `LICENSE` |

"Or later" matters: it means we may distribute the Android fork under GPLv3 if we ever want
GPLv3's explicit patent and anti-tivoisation terms.

### The obligation we have not met yet

GPLv2 §3 says that whoever distributes a binary must also give the recipient the complete
corresponding source — either shipped alongside, or through a written offer valid for three
years. We are distributing binaries today (the APK and the desktop zip on `puregram.app`)
and are about to distribute one through Google Play, and **the source is not published
anywhere**. `NOTICE.md` promises "the complete corresponding source … is this repository",
but the repository is not public. That promise is currently false.

This is the single largest legal exposure in the project, and it is also the easiest to fix.

Three smaller gaps go with it:

- There is **no `LICENSE` file at the repository root** — only inside each fork.
- **Nothing in the app or on the site links to the source.** A user who installs from Play
  has no way to reach it. The offer has to travel with the binary.
- Releases are not tagged, so "the source that corresponds to *this* build" is not identifiable.

### Google Play's "automatic protection" conflicts with the GPL — and it is switched on

Play Console offers a feature that injects an installer check into the app's bytecode at
build time, so a copy installed from anywhere but Play prompts the user to go get the Play
version; for some developers it also adds anti-tamper checks and obfuscation designed to
resist removal.
([Play Console Help](https://support.google.com/googleplay/android-developer/answer/10183279))

For a GPL app that is a problem twice over:

- GPLv2 §6 forbids imposing further restrictions on the recipient's exercise of the rights
  the licence grants. A runtime mechanism whose purpose is to discourage redistribution
  outside one channel is exactly that kind of restriction. This is the same argument the FSF
  made against Apple's App Store over GNU Go, where the objection was to the extra terms
  layered on top of distribution, not to store distribution itself.
  ([The Register](https://www.theregister.com/2010/05/27/gnu_go_fsf_apple_itunes/))
- The injected code is not in our source tree, so the binary on Play would no longer
  correspond to the source we publish — breaking §3 as well.

**It is currently enabled on our app** (Play Console → محمي من خلال Google Play → منع عمليات
التثبيت غير الرسمية, 1 of 1 service active). Google documents it as optional and switchable.
It should be off.

**It will not switch off.** Tried on 2026-09-05 at
`app-integrity/automatic-integrity-protection-settings`. The toggle flips, the Save button
enables, saving raises no error and shows no confirmation — and the setting is back on after a
reload. Three attempts, two different ways of clicking. There is no pending change waiting on
the publishing overview either. The release-preparation page still reports the service as
active, alongside a note that the bundle has to be re-uploaded for optimisation changes to
apply, which suggests the setting is meant to be changeable.

Either the Console is failing silently or the switch is locked for this app. The page carries a
"الحصول على الدعم" link, and that is the next step: ask Play support to disable automatic
protection, saying the app is distributed under the GPL and the injected installer check adds a
restriction the licence does not permit.

Beyond that one feature, GPLv2 distribution through Google Play is generally considered
workable — Play does not impose the per-device usage limits that triggered the Apple dispute.

---

## 2. Telegram's API Terms of Service

Every third-party client that logs users into Telegram's network is bound by these.
([core.telegram.org/api/terms](https://core.telegram.org/api/terms),
[obtaining_api_id](https://core.telegram.org/api/obtaining_api_id))

| Requirement | Puregram today |
|---|---|
| Use your own `api_id` | ✅ `31525680`, ours |
| Title must not contain "Telegram" unless prefixed "Unofficial" | ✅ "Puregram" |
| Must not use the official Telegram logo | ⚠️ **see below** |
| Say in the store description that the app uses the Telegram API | ⚠️ implied, not stated |
| Disclose every monetisation method in every store listing | ✅ there is none |
| Must not break self-destruct, last seen, read receipts, typing | ✅ untouched |
| Must not use Telegram data to train AI | ✅ |
| **Support official sponsored messages and not interfere** (§3.3) | ❌ **violated** |

### The sponsored-messages problem

Section 3.3 requires an app that gives access to channel content to support Telegram's
official sponsored messages and not interfere with them.

`PuregramRules.HIDE_SPONSORED_MESSAGES = true` suppresses them in
`MessagesController.java:20823` and `video/VideoAds.java:181`. The store listing then
advertises the fact in so many words — "No sponsored messages and no ads, anywhere."

So the violation is not only present, it is published. Under §4.2 Telegram gives ten days to
fix a violation, after which they cut off API access **and contact the app stores about
removing the app**. As copyright holder of the code and operator of the network they are the
one party who can act on both fronts at once.

Two honest options, and this is a product decision, not a technical one:

- **Restore sponsored messages.** Compliant. Costs us the "no ads anywhere" claim, and
  sponsored messages only ever appear in public channels — which are closed by default in
  Puregram anyway, so in practice most users would rarely see one.
- **Keep hiding them** and accept that the app can be pulled at ten days' notice, with no
  appeal, at any time Telegram chooses to look.

### The icon

Telegram's guidance to people publishing modified versions is not to use the Telegram name
or the standard logo — a white paper plane in a blue circle — or else to make unmistakably
clear that the build is unofficial.

Our icon **was** a white paper plane in a green circle. The colour changed; the mark did not.
That is the weaker half of the test to be relying on, and it is also the thing Google Play's
Impersonation policy looks at directly: it prohibits titles and icons so similar to an
existing product that users may be misled.
([Play Impersonation policy](https://support.google.com/googleplay/android-developer/answer/9888374))

**Replaced on 2026-09-05** with a "P" monogram — no plane, no borrowed silhouette. One
generator, `brand/make_icons.py`, draws the mark and writes all 59 assets: the Android legacy
and adaptive icons at five densities, the monochrome adaptive layer, the Play 512, the site
logo and favicon, the `brand/` PWA set, and the desktop icons including `icon256.ico`. The
originals are kept under `archive/icons-before-2026-09-05/`.

Everything else about our positioning was already careful — the listing, the site and the FAQ
all say plainly that this is unofficial and not affiliated. The icon was the one piece
undoing that work.

---

## 3. Google Play policies

- **Impersonation** — the icon, as above. Name, developer name and listing text are clean.
- **Repetitive content** — Play rejects apps that merely reproduce an experience already on
  the store. A thin re-skin of Telegram would be squarely in that category. Our permanent
  one-way block is a real functional difference and the listing already leads with it; keep
  it leading.
- **Device and Network Abuse** — self-updating outside Play is forbidden. Already removed
  from the Play build via `-PpuregramPlay`.
- **Data safety** — declared and verified; see `play-assets/listing/data-safety-and-content-rating.md`.

---

## 4. What the other Telegram forks on Play actually do

| Fork | On Play | Source published | Notes |
|---|---|---|---|
| [Nekogram](https://github.com/Nekogram/Nekogram) | yes | yes, full repo | own name and icon; describes itself as an open-source third-party Telegram client. The model worth copying. Recent user reports allege the Play binary diverged from the published source — a reminder that publishing a repo is not the same as publishing *the* corresponding source. |
| [NekoX](https://github.com/NekoX-Dev/NekoX) | yes | yes | same pattern |
| Plus Messenger | yes, 50M+ installs | **no** — nothing since Sept 2017 | now ships an unpublished ad and billing layer. A public compliance complaint was filed in Sept 2026 with the FSF Compliance Lab, Software Freedom Conservancy and FSFE, and with Telegram. ([XDA](https://xdaforums.com/t/plus-messenger-9-years-of-telegram-gpl-code-with-no-source-now-with-an-unpublished-paid-ads-layer.4800334/)) |
| Graph Messenger, Vidogram, Mobogram and similar | yes | no public repo found | proprietary forks of GPL code — the ecosystem's standing problem |
| [Telegram-FOSS](https://github.com/Telegram-FOSS-Team/Telegram-FOSS) | no | yes | avoids Play entirely, ships through F-Droid |

The pattern is clear enough. Forks that publish source and use their own branding sit on Play
for years without trouble. Forks that do not are fine until somebody looks — and when
somebody looked at Plus Messenger in September 2026, after nine years and fifty million
installs, the complaint went to four organisations at once.

We are not choosing between "comply" and "get away with it". We are choosing between
complying now, cheaply, and complying later under a ten-day deadline.

---

## 5. What to do, in order

| # | Action | State |
|---|---|---|
| 1 | Turn **off** Play's automatic protection | ⛔ blocked — the toggle will not persist; needs Play support |
| 2 | Publish the repository, add a root `LICENSE`, tag the release commit | ⏳ open — the largest exposure |
| 3 | Link the source from the app, the site and the Play listing | ⏳ open, waiting on #2 |
| 4 | Sponsored messages | ✅ decided: behaviour kept, and the listing no longer advertises it |
| 5 | Replace the paper-plane icon | ✅ done — "P" monogram, 59 assets regenerated |
| 6 | State in the listing that the app uses the Telegram API | ✅ done, English and Arabic |

On #4 the owner chose to keep hiding sponsored messages and accept the risk, on the reasoning
that the fix is a one-line change and Telegram gives ten days' notice. The listing claim was
removed because it was the cheapest way to stop advertising the violation. Worth restating
once: an enforcement action cuts the `api_id`, and that stops the sideloaded APK and the
desktop build too, not only the Play release.

---

## Sources

- [Telegram API Terms of Service](https://core.telegram.org/api/terms)
- [Obtaining an api_id](https://core.telegram.org/api/obtaining_api_id)
- [Telegram for Android — LICENSE](https://github.com/DrKLO/Telegram/blob/master/LICENSE)
- [Google Play Impersonation policy](https://support.google.com/googleplay/android-developer/answer/9888374)
- [Google Play automatic protection](https://support.google.com/googleplay/android-developer/answer/10183279)
- [Google Play Developer Content Policy](https://play.google/developer-content-policy/)
- [FSF vs Apple over GNU Go — The Register](https://www.theregister.com/2010/05/27/gnu_go_fsf_apple_itunes/)
- [Nekogram](https://nekogram.app/) · [source](https://github.com/Nekogram/Nekogram)
- [Plus Messenger GPL complaint, Sept 2026 — XDA](https://xdaforums.com/t/plus-messenger-9-years-of-telegram-gpl-code-with-no-source-now-with-an-unpublished-paid-ads-layer.4800334/)
