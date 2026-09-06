# Puregram — Data Safety form + Content Rating answers

**App:** Puregram · `app.puregram` · 13.1.0 (67759) · Free · armeabi-v7a, arm64-v8a, x86, x86_64
Unofficial, independent build based on Telegram's open-source Android client. Not affiliated
with Telegram. Privacy policy: `https://puregram.app/privacy.html`

> Updated 2026-09-05 for ADR-002. The app no longer downloads a curated list; each user keeps
> their **own** allow/block lists, and those lists sync across their devices through our
> server. That sync is data collection under Play's definition, so this form declares it.
>
> **Verified against the live Console on 2026-09-05.** The saved answers were *not* "no data
> collected" as this file previously assumed — the form was already completed on 7 Jul 2026
> with: collects data **Yes**, encrypted in transit **Yes**, deletion URL
> `https://puregram.app/privacy.html`, sign-in method "username + other auth", and these five
> types ticked: **Name**, **User IDs**, **App interactions**, **Other user-generated
> content**, **Device or other IDs**. Steps 3 and 4 both read "complete". That set already
> covers everything the rules server stores, so **no edit is required** for ADR-002.
>
> One open question is recorded under A.6 below.

---

## PART A — Data Safety form

### A.0 Top-level answers

| Question | Answer |
|---|---|
| Does your app collect or share required user data types? | **Yes** |
| Is all collected data encrypted in transit? | **Yes** (HTTPS/TLS) |
| Do you provide a way to request data deletion? | **Yes** — in-app, under Settings ▸ Allowed and blocked ▸ Delete my data |
| Privacy policy URL | `https://puregram.app/privacy.html` |
| Is any data sold? | **No** |
| Is any data shared with third parties? | **No** |
| Any data used for advertising / marketing / third-party analytics? | **No** |

> **Correction (2026-09-05):** an earlier draft of this file claimed the build ships no Google
> Play Services or Firebase. That is true of the website APK, **not** of the Play AAB. The
> bundle links `firebase-messaging`, `firebase-config`, `firebase-datatransport`,
> `firebase-appindexing` and several `play-services-*` libraries (maps, auth, location,
> vision, wearable, wallet), plus MLKit, Play Integrity, SafetyNet and reCAPTCHA. There is
> **no** Crashlytics and **no** Firebase Analytics (`firebase-core` is excluded and no
> `firebase-analytics` dependency exists), so no crash-log or analytics type is collected.
> FCM's own device token is covered by the **Device or other IDs** declaration in A.2.

### A.1 Telegram account id (numeric)
- **Category / type:** Personal info → **User IDs**
- Collected **Yes** · Shared **No** · Ephemeral **No** · **Linked to identity: Yes**
- **Purpose:** App functionality (the key the user's own lists are stored under, so they
  appear on every device that user signs in on)
- **Required** — without it the lists cannot follow the account
- *Note:* a numeric account identifier only. No name, phone number, or email is collected.

### A.2 Device identifier
- **Category / type:** Device or other IDs → **Device or other IDs**
- Collected **Yes** · Shared **No** · Ephemeral **No** · **Linked to identity: Yes**
- **Purpose:** App functionality; Fraud prevention & security — it records which devices the
  account has approved for syncing, so a stranger who knows the account id cannot read or
  add to that account's lists
- **Required**

### A.3 The user's allow / block lists
- **Category / type:** App activity → **Other user-generated content**
- Collected **Yes** · Shared **No** · Ephemeral **No** · **Linked to identity: Yes**
- **Purpose:** App functionality (this *is* the feature — the lists the user set, synced
  between their own devices)
- **Required**
- *Note (state plainly to pre-empt a mis-classification):* each entry is **chat metadata the
  user chose** — a chat id, its kind, and its title/@username for display. It is **NOT**
  message content and **NOT** the device's phone contacts. Declare this single type; do not
  also tick Contacts or Messages.

### A.4 Declare as NOT collected (leave unchecked)
Message content · Email address · Password · Phone number / Contacts · Location · Photos or
videos · Financial info · Health & fitness · Web browsing history · Calendar · SMS / call
logs · Audio · Files & docs · Approximate or precise location.

> A messenger declaring **no "Messages" data** is unusual — correct here because messaging
> runs entirely over Telegram's network and never touches Puregram's server.

### A.5 Deletion path (Play requires this whenever account-linked data is collected)
In-app: **Settings ▸ Allowed and blocked ▸ Delete my data**. The request is recorded and
carried out **60 days later**; the user may cancel at any point during the wait.

The delay is a deliberate product decision, and the listing/privacy policy state it: deleting
the data also clears the blocks the user made permanent, so an instant button would be a
one-tap way around the very commitment the app exists to keep. Deletion is still offered,
unconditionally, to every user — only its timing is delayed, and the user is told the exact
effective date.

### A.6 Open question — the types Telegram itself transmits

The saved answers declare only what **Puregram's own server** stores. They do not declare the
location, photos, files or message content a user sends **through Telegram's network**, on the
reading that Play exempts a transfer the user starts deliberately and plainly.

Upstream Telegram's own Play listing takes the opposite reading and declares Location, Photos
and videos, Messages, Contacts, and Files and docs. Both readings are defensible; declaring
more is the safer one, and the cost of declaring more is only a longer data-safety card.

**Not changed without the owner's say-so** — it is a declaration, and the current answers were
already accepted by the Console.

---

## PART D — Permission declarations (App content ▸ 7 items pending)

Read from the Console 2026-09-05. All seven were raised against the **old** 12.8.8/12.8.9
bundles. Two of them disappear on their own once 13.1.0 is the active bundle, because the
permission is simply gone:

| Declaration | 12.8.8 | 13.1.0 | Action |
|---|---|---|---|
| SMS and Call Log permissions | `SEND_SMS`, `READ_CALL_LOG` present | absent | clears itself |
| Request install packages | `REQUEST_INSTALL_PACKAGES` present | absent (removed with the self-updater) | clears itself |

The remaining five are genuine and need answers:

| Declaration | Why it applies to 13.1.0 | Answer to give |
|---|---|---|
| Advertising ID | required of every developer | **No** — `AD_ID` is not in the bundle and no ad or analytics SDK is linked |
| Location permissions | `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `FOREGROUND_SERVICE_LOCATION` | in-app location sharing and live location, **foreground only** — `ACCESS_BACKGROUND_LOCATION` is absent |
| Foreground service types | 8 declared types | data sync (message sync), media playback, media projection (screen share), microphone + camera + phone call (voice/video calls), location (live location), remote messaging |
| Full-screen intent | `USE_FULL_SCREEN_INTENT` | the app places and receives calls — incoming-call screen on a locked device |
| Photos and videos | `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO` | core function: attaching and sending photos and videos in a chat |

---

## PART B — Content Rating (IARC questionnaire)

Start category: **Social Networking / Communication.**

| # | Question | Answer | Why |
|---|---|---|---|
| 1 | Violence | **No** | none authored by the app |
| 2 | Sexual content / nudity | **No** | the app refuses Telegram-flagged restricted/sensitive peers, and channels/bots/groups are closed by default |
| 3 | Profanity / crude humor | **No** | none authored by the app |
| 4 | Controlled substances | **No** | — |
| 5 | Gambling | **No** | — |
| 6 | **Users can interact / communicate** | **Yes** | it's a messenger |
| 7 | **Users can share user-generated content** | **Yes** | standard messaging; Puregram doesn't read or store it |
| 8 | Users can share their location with others | **Yes** | Telegram's in-chat location sharing is still present (foreground only) |
| 9 | Digital purchases / IAP | **No** | free, no subscription, no IAP |
| 10 | Unrestricted internet / open in-app web browser | **No** | no open-web browser surface; web image search is removed |
| 11 | Personal info shared with other users | **Yes** | inherent to messaging |

**Interactive Elements:** Users Interact = **Yes** · Shares Info = **Yes** · Shares Location =
**Yes** · Digital Purchases = **No**.

**Predicted rating:** **Teen** / **PEGI 12** / **ESRB Teen** — driven by the interactive
elements, not by content descriptors. Do **not** answer "No" to Q6/Q7 to chase a lower rating.

---

## PART C — Target audience & content

| Question | Answer |
|---|---|
| Target age group | **18 and over** |
| Include any under-18 bracket as a target? | **No** |
| Designed for Families / Teacher-approved | **NOT enrolled** |
| Appeals to children? | **No** — self-discipline utility positioning |
| Ads shown to children? | N/A — **no ads at all** |

**Rationale:** a general-purpose communication app with a self-commitment feature, for adults
choosing it for themselves. It is not a parental-control product — nobody supervises anyone
else — so the Families programme does not apply.

---

## Cross-form consistency checklist

- Data safety declares **Name + User IDs + App interactions + Other user-generated content +
  Device IDs**, all collected, none shared, encrypted in transit, deletable → matches the
  privacy policy and the listing's PRIVACY paragraph. Verified live; no edit needed.
- The in-app deletion path exists and is reachable in two taps from Settings.
- "Users can communicate" → Content Rating Q6 = Yes; consistent with the listing.
- No ads anywhere → Content Rating ads = No. No IAP → Digital purchases = No.
- Listing states unofficial / not affiliated and uses no Telegram logo or wordmark.
- Foreground-service permissions are unchanged from the 12.8.x submission, but the Console
  declaration for them was never completed — see PART D.
