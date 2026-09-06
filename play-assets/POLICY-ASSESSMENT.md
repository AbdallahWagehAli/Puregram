# Puregram — Google Play Policy Risk Assessment

> ## UPDATE 2026-09-03 — control model replaced (ADR-001), verdict now **GO**
>
> The per-account supervision layer that drove risk (b) below **no longer exists**. Since
> 12.9.0 / 67699 the client uploads nothing: no device id, no account id, no reported chat
> list, no supervisor links. It only downloads one public list (`GET /control/v1/policy`)
> that decides which channels and bots open; private chats and groups are untouched;
> Telegram's own restriction labels are enforced; channel/bot discovery surfaces are removed.
>
> Consequences for this assessment:
> - **(b) Supervision / stalkerware line — ELIMINATED.** There is no monitoring of one
>   person by another, nothing is reported off-device, and the "consent" machinery is gone
>   because there is nothing to consent to.
> - **User Data / Data Safety — simplified to "No data collected"** (see
>   `listing/data-safety-and-content-rating.md`). The standalone flavour ships no Google /
>   Firebase / analytics SDK.
> - **Families / parental-control framing — dropped.** Position as a plain ad-free
>   messenger with a curated channel list; do not enrol in Designed for Families.
> - Still applies: (a) unofficial-client identity rules (no "Telegram" in title / icon /
>   graphics, visible disclaimer, GPL attribution + Licenses screen) and reviewer
>   testability of a login-gated app (provide a test account in the Console).
> - The old `12.8.x` verdict text below is kept for history only.


**App:** Puregram (`app.puregram`) · versionName 12.8.7 / versionCode 67619 · Free · arm64-v8a
**Date:** 2026-07-06 · **Scope:** pre-submission Play policy risk (engineering assessment, not legal advice)

---

## Overall verdict: **NEEDS-CHANGES** (submittable after the Top 5)

The concept is policy-viable — unofficial open-source clients, consent-based parental
control, and ad-free forks are each individually allowed. But three surfaces will fail
review as-is: **brand identity** (using "Telegram"), the **surveillance/consent framing**,
and **reviewer testability** of a login-gated app. Fix the Top 5 and it becomes a
defensible GO.

---

## (a) Unofficial third-party Telegram client — **MEDIUM**

*Policy areas: Impersonation; Intellectual Property; Deceptive Behavior.*

A third-party client built on Telegram's open-source code is permitted **in principle**;
the risk is letting users think it's official. Note: Telegram's Android client is licensed
**GPL-2.0-or-later** — preserve copyright notices and publish/link your modified source as
the license requires. (Play doesn't enforce GPL, but an IP complaint can still get you
removed under the IP policy.)

**Mitigations:** prominent "unofficial / not affiliated with Telegram FZ-LLC" disclaimer
(first-run + listing); keep your own Puregram name/icon; ship an in-app **About → Licenses**
screen and link source/attribution from the listing.

## (b) Supervision / parental-control layer — **MEDIUM–HIGH (top functional risk)**

*Policy areas: Stalkerware/"Surveillance" provisions of Malware/Deceptive Behavior;
Families/Parental-control requirements; User Data.*

Google's line is bright: **parental-control/EMM apps are allowed; covert monitoring /
stalkerware is banned.** An app that reads a chat list and reports it to another person
sits right on that line. What keeps Puregram on the **allowed** side: consent is built in
(the supervised person approves in-app, either side can unlink, a code/QR is visible on the
supervised device) and **no message content** is read or stored.

**Mitigations:**
1. **Add a persistent, non-dismissible "This device is supervised by [X]" indicator** on
   any supervised account. This is *not* an absolute statutory "must" for this consent-based,
   chat-scoped model, but Play's parental-control/stalkerware guidance **strongly expects**
   an ongoing, visible indicator — adding one is the single best move to stay clearly on the
   compliant side. *(Recommended change — not currently shipped.)*
2. Make the consent flow (request → explicit in-app approval → unlink anytime) reachable and
   observable by a reviewer.
3. **Language discipline:** never "spy / covert / hidden / secretly / track" anywhere.
   Use "supervision", "with consent", "the supervised person approves".
4. Scope the audience to parents/guardians/mentors supervising a device **with consent**.
5. State plainly you never read message content — only the chat list and approval state.
6. Do **not** enrol in "Designed for Families"; target audience = adults (18+).

## (c) Not showing Telegram's sponsored messages / ads — **LOW**

*Policy areas: Deceptive Behavior/Interference; your Ads policy (governs only your ads).*

There is **no Play policy that requires you to display a third party's ads.** Your client
shows no ads and uses no ad SDK — clean. The only theoretical exposure is contractual/IP with
Telegram (their lane, via the IP process), not a Play review failure.

**Mitigations:** frame neutrally as a user benefit ("no ads, no sponsored messages, no
tracking"); never frame it as defeating/circumventing Telegram's monetization; keep the Data
Safety "no ads / no third-party ad SDK" answer truthful (it is).

## (d) "Telegram" in name / icon / branding / screenshots — **HIGH (top rejection driver)**

*Policy areas: Impersonation; IP/trademark; Store Listing (deceptive metadata).*

Your app name is already **"Puregram"** — good. Exposure is anywhere Telegram's mark/logo
bleeds into **identity** surfaces: the icon, the feature graphic, or screenshots that show
Telegram's logo as if it were the app's.

- **Not allowed (identity use):** "Telegram" in the title/subtitle; Telegram's logo/wordmark
  as your icon or feature graphic; screenshots captioned as "Telegram".
- **Allowed (nominative use):** minimal factual references — "based on Telegram's open-source
  client" — in the **description body only**, each paired with the disclaimer.

**Mitigations:** app name "Puregram" only; icon + feature graphic = your green Puregram brand
(provided in `graphics/`); screenshots show your own chrome; nominative "Telegram" only in the
long description; no keyword-stuffing.

---

## Other landmines

- **Data Safety accuracy — MEDIUM.** The form must match observed behavior **and** the
  privacy policy exactly. See `listing/data-safety-and-content-rating.md`. Verify
  `https://puregram.app/privacy.html` is live and consistent (it is, updated 2026-07).
- **App access (login-gated) — MEDIUM/HIGH if omitted.** The core feature needs a Telegram
  account **and** a second supervisor device. Fill the **App access** section with detailed
  step-by-step instructions **and** a seeded demo/review path (not a Google-only backdoor,
  which would itself violate Deceptive Behavior) so a reviewer can watch: sign-in → locked
  deny-by-default → rotating code/QR → supervisor link approval → toggle a chat open.
- **Permissions — MEDIUM.** Request the minimum. Avoid Accessibility / `QUERY_ALL_PACKAGES` /
  `PACKAGE_USAGE_STATS` / SMS / Call Log for monitoring (a known rejection trap). Supervision
  is in-app (it governs which chats *your own* client opens), so you should not need
  device-wide monitoring permissions — keep it that way and say so. Justify camera as
  "scan the link QR" only.
- **Device & Network Abuse — LOW.** Don't self-update the APK out of band on the Play build.
- **Target Audience & Content — MEDIUM.** Target = adults (18+); do not enrol in Designed for
  Families; complete IARC honestly (communication app → likely Teen/PEGI 12).

---

## Top 5 required changes before submitting

1. **Strip "Telegram" from every identity surface** — title = "Puregram" only; icon + feature
   graphic + screenshots use the green Puregram brand; nominative references only in the body.
2. **Add a persistent "This device is supervised" indicator** on supervised accounts (plus the
   existing explicit approval + anytime unlink) — moves you decisively from "stalkerware" to
   "consent-based parental control".
3. **Provide reviewer-testable access** — a documented demo/review mode or seeded demo account
   covering the full supervised → link → approve → toggle flow, written into **App access**.
4. **Make Data Safety exactly match the privacy policy** — Device ID, account/user id, reported
   chat list, whitelist; purposes = App functionality/Account management; encrypted in transit;
   not sold, not shared; deletion via unlink; all four **linked to the user's identity**.
5. **Prominent unofficial/not-affiliated disclaimer** on first run + listing, plus **GPL-2.0
   open-source attribution** in an in-app Licenses screen and the listing. Remove any
   spy/covert/hidden/track wording; set **target audience = adults (18+)**.

---

## Play Console upload checklist (create app → roll out to production)

1. **Create the app** — Play Console → *All apps → Create app*. App name **"Puregram"**,
   default language, type = App, category **Free**. (Complete developer identity verification
   + payments profile first; they block publishing if incomplete.)
2. **Dashboard → "Set up your app"** — confirm Free, no in-app purchases; complete initial
   declarations.
3. **App content → Privacy policy** — enter `https://puregram.app/privacy.html` (live, matches
   the collected data types).
4. **App content → App access** — "Some functionality is restricted"; add reviewer
   step-by-step instructions + demo credentials / demo-review-mode covering the full flow.
5. **App content → Ads** — "No, my app does not contain ads."
6. **App content → Content rating** — complete the **IARC** questionnaire honestly (see
   data-safety doc); submit to get ratings.
7. **App content → Target audience & content** — target **18+**; do **not** enrol in Designed
   for Families; "appeals to children" = No.
8. **App content → Data safety** — declare the four collected items, purposes (App
   functionality / Account management), **encrypted in transit = Yes, sold = No, shared = No**,
   each **linked to identity = Yes**, deletion via unlink. Match the privacy policy.
9. **App content → other declarations** — Financial features / Health / Government / News =
   not applicable.
10. **Main store listing** — app name "Puregram"; short + full description (from
    `listing/store-listing.md`) leading with value + the not-affiliated disclaimer; nominative
    "Telegram" only. No "Telegram" in the title.
11. **Graphics** — icon 512×512 (`graphics/icon-512.png`), feature graphic 1024×500
    (`graphics/feature-graphic-1024x500.png`), 2–8 phone screenshots (`screenshots/`, replace
    with real device captures — see that folder's README). No Telegram logo/wordmark.
12. **Store settings** — category **Communication**; contact email (monitored) + website;
    add open-source **license attribution** line.
13. **Release → Production → Create new release** — enrol in **Play App Signing** (let Google
    manage the app signing key; you keep the upload key — see `keystore/`).
14. **Upload the AAB** — `puregram-12.8.7-67619.aab` (versionName 12.8.7 / versionCode 67619),
    signed with the upload key. Confirm target API meets Google's current minimum and
    `arm64-v8a` is present.
15. **Add release notes**, fix any pre-launch report / policy warnings.
16. **Countries/regions & pricing** — choose availability; Free.
17. **Recommended:** run **Internal testing** first to validate the reviewer-access/demo path,
    then promote to Production.
18. **Submit for review → Roll out** — use a **staged rollout** (10–20%) and monitor policy
    status, crashes, and reviews before going to 100%.

---

**Bottom line: NEEDS-CHANGES.** Concept allowed; execution must prove *non-affiliation*
(branding) and *consent/non-covertness* (persistent supervised indicator + reviewer-testable
consent flow), with a Data Safety form that mirrors your honest data practices. Land the Top 5
and this is a defensible production submission.
