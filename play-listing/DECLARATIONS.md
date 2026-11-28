# Play Console — permission declarations (D87)

Exact English texts for **App content → Permissions / Foreground service permissions / Full-screen intent**.
Source: merged manifest of **b51** (`aapt2 dump xmltree` / `check-manifest.py --list`, see FACTS.md §2).
Video (one recording covers the full-screen intent and both call foreground services):

- **Video URL:** `https://psst.pro/video/psst-incoming-call-and-background-call.mp4`
  (Android emulator, Android 14, psst b51; 1080×2400, no sound). Shown in it: the phone is locked → another
  user calls → full-screen incoming-call screen over the lock screen → Accept → call runs → Home: the call
  continues in the background with the ongoing-call notification → back to the call → Hang up.
- Second video for the short service: `https://psst.pro/video/psst-message-notification.mp4`
  (app in the background / screen off → a message arrives → notification with sound appears).

Nothing was submitted to Play Console.

---

## 1. Full-screen intent (`android.permission.USE_FULL_SCREEN_INTENT`)

**Question:** Does your app's core functionality require full-screen intent? →
**Yes — "Calling: making and receiving phone, video or VoIP calls".**

Declaration text:

> psst is a messaging app with voice and video calls. When another user calls, psst shows a full-screen
> incoming-call screen over the lock screen with Accept and Decline buttons, like the phone app, so the user does
> not miss the call while the screen is off. The full-screen intent is used only for incoming calls (a
> notification of category CALL on the "incoming call" channel); message notifications never use it. If the
> user turns the permission off, psst shows a normal high-priority call notification instead.

Evidence: `IncomingCallActivity` (`showWhenLocked`, `turnScreenOn`) in `features/call/impl`, notification
category CALL; the Settings → "Notifications & calls" screen shows the real state of the permission and opens
`ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT` (D72).

## 2. Foreground service types

The form asks, per type: description of the feature, user impact if the task is deferred or interrupted, video
link, and the use case.

### 2a. `microphone` — `CallForegroundService` (also in `ElementCallForegroundService`)

- **Use case:** VoIP call / Phone call (ongoing voice or video call).
- **Description:**
  > During an ongoing voice or video call, psst runs a foreground service of type microphone so that the call
  > keeps sending the user's voice when they switch to another app or lock the screen. The service starts only
  > when the user starts or accepts a call and stops as soon as the call ends. While it runs, an ongoing-call
  > notification with a Hang up button is shown.
- **User impact if deferred:**
  > The call could not start: the user would accept a call and the other side would not hear them.
- **User impact if interrupted (paused/restarted):**
  > The other participants would stop hearing the user in the middle of the call, or the call would drop.
- **Video:** `https://psst.pro/video/psst-incoming-call-and-background-call.mp4`

### 2b. `camera` — `ElementCallForegroundService` (type camera|microphone)

- **Use case:** Video call.
- **Description:**
  > During a video call, psst keeps the camera running in a foreground service of type camera, so the other
  > participants keep seeing the user when the call is in picture-in-picture or the user briefly switches to
  > another app. The camera is used only while the user has their camera turned on in a call; the service stops
  > when the call ends.
- **User impact if deferred / interrupted:**
  > The user's video would freeze or disappear for the other participants during the call.
- **Video:** the same video (the call is a video call; the camera preview stays on when the app goes to the
  background).

### 2c. `shortService` — `FetchPushForegroundService`

- **Use case:** Other — completing a short, user-visible task after a push notification.
- **Description:**
  > When a Firebase Cloud Messaging message arrives, it carries only an event ID (messages are end-to-end
  > encrypted, so their content is never sent through Google). psst starts a short foreground service for a few
  > seconds to download the new message from the psst server, decrypt it on the device and show the
  > notification. The service stops as soon as the notification is shown (shortService, at most 3 minutes).
- **User impact if deferred:**
  > The user would see the notification late or not at all, and could miss a message or a call.
- **User impact if interrupted:**
  > The notification for that message would not be shown.
- **Video:** `https://psst.pro/video/psst-message-notification.mp4`

### 2d. `location` — `LiveLocationSharingService` (od 26.11.1, D97)

- **Use case:** Other — user-started live location sharing in a chat (Play category: "Location sharing").
- **Description:**
  > When the user chooses "Share live location" in a chat and picks 15 or 60 minutes, psst runs a foreground
  > service of type location so the people in that chat keep seeing the user's current position while the app is
  > in the background or the screen is locked. The service runs only during this user-started sharing, shows an
  > ongoing notification ("Location sharing in progress") the whole time, and stops by itself when the chosen time
  > ends or when the user taps Stop in the chat. psst never requests background location (no ACCESS_BACKGROUND_LOCATION) and never determines the location
  > without an active sharing session.
- **User impact if deferred:**
  > The other people would not see the user's position although the user started sharing it.
- **User impact if interrupted:**
  > The shared position would freeze for the others in the middle of the session (e.g. while walking to a meeting
  > point), without the user noticing.
- **Video:** `https://psst.pro/video/psst-live-location.mp4` (Android 15 emulátor, build 26.11.1-b58, 2 min 36 s: vysvetlenie →
  povolenie „While using the app“ → 15 minút → lišta Stop → appka na pozadí, trvalé upozornenie → Stop → „Live location ended“)
- **Location permissions form** (App content → Location permissions): netýka sa — appka nežiada polohu na
  pozadí (ACCESS_BACKGROUND_LOCATION); poloha len pri používaní a počas zdieľania spusteného používateľom.

## 3. Permissions that are NOT in the app any more (removed in b51, D87)

| Permission | Why it was removed | Replacement |
|---|---|---|
| `REQUEST_INSTALL_PACKAGES` | Play allows it only for apps whose core purpose is installing packages | an `.apk` attachment is opened like any other file; updates are downloaded in the browser from app.psst.pro/download |
| ~~`ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `FOREGROUND_SERVICE_LOCATION`~~ | **vrátené v 26.11.1 (D97)** — len na vyžiadanie používateľa, pozri §2d | `ACCESS_BACKGROUND_LOCATION` ostáva zakázané |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Play: not acceptable for chat/calling apps that can use FCM (developer.android.com/training/monitoring-device-state/doze-standby#exemption-cases, row "Instant messaging, chat, or calling app … Yes, using FCM → Not Acceptable") | the "Battery" step in Notifications & calls explains App info → Battery → Unrestricted and opens the app's system page |

`scripts/android/check-manifest.py` fails the CI build and the signing script if any of them comes back.

---

## 4. Precise location declaration (`ACCESS_FINE_LOCATION`) — required from 27 January 2027 (D109)

**What Google requires** (checked 28. 11. 2026; overiť znenie v prehliadači pred vyplnením):
- Play Console Help „Minimum Scope: Foreground Location Access and the Location Button“
  (https://support.google.com/googleplay/android-developer/answer/17033915): „All apps requesting precise location
  (`ACCESS_FINE_LOCATION`) must complete a declaration in the Play Console“; timeline: 15. 4. 2026 oznámenie,
  „December 2026: The declaration … will be available“ (anglická UK verzia stránky uvádza November 2026),
  „January 27, 2027: Policy compliance is mandatory for all apps“, potom predĺženie v Play Console (US verzia
  60 dní, UK verzia 30 dní — overiť v konzole).
- Policy announcement 29. 10. 2026 (https://support.google.com/googleplay/android-developer/answer/18100766):
  „Apps using `ACCESS_FINE_LOCATION` must complete a Play Console declaration“ to „justify why coarse location or
  the location button is insufficient“.
- Policy „Permissions and APIs that Access Sensitive Information“ (answer/16558241): „Foreground Services access
  of device location must be user-initiated and temporary“.
- **Android 17:** psst cieli na API 37. Pre appky s targetSdk 37+ je „Android location button … the required minimum
  scope method“ pre jednorazové žiadosti; príklad Google: „One-time Sharing: Sending a current location to a friend
  in a messaging app“. Tlačidlo dáva presnú polohu len na reláciu („strictly for foreground, transactional use“).
  Ongoing FINE je pre „continuous, real-time tracking“; riadok „Live tracking“ má príklad „sharing ongoing location
  with people“ — to je živé zdieľanie psst.
- **Odporúčanie pre tím Androidu (pred 27. 1. 2027):** „Poslať polohu“ (jednorazovo) prerobiť na tlačidlo polohy
  (`androidx.core.locationbutton`, zatiaľ alpha; pod Android 17 bežná výzva), živé zdieľanie 15/60 min nechať na
  `ACCESS_FINE_LOCATION`. Ak to do termínu nebude, odpoveď nižšie uvedie obe funkcie pravdivo tak, ako sú.

**Form answers (English, as filled in):**

1. *Which user-facing features in your app require ACCESS_FINE_LOCATION?*
   - **Live tracking** — "Share live location" in a chat: the user chooses 15 or 60 minutes and the people in that
     chat see the user's position update in real time until the time ends or the user taps Stop.
   - **One-time location sharing** — "Send location" in a chat: the user's current position is sent once as a
     message. *(Vynechať, ak už bude „Send location“ cez tlačidlo polohy.)*

2. *Explain why ACCESS_COARSE_LOCATION or LocationButton is not sufficient and you need ongoing
   ACCESS_FINE_LOCATION.*
   > psst is a private messenger. Live location sharing is started only by the user from a chat, for 15 or 60
   > minutes, and is the reason psst needs ACCESS_FINE_LOCATION. During this session the position is updated
   > continuously so the other people in the chat can follow the user on the map, for example while walking to a
   > meeting point; approximate location (≥ 3 km²) would show a point that can be kilometres away and is useless
   > for this. The session keeps running when the user switches to another app or locks the screen (foreground
   > service of type location with an ongoing notification and a Stop action), which a session-scoped,
   > foreground-only location button grant does not cover. Location is read only while a share is active (or once
   > when the user sends their current position), never in the background otherwise: psst does not request
   > ACCESS_BACKGROUND_LOCATION, has no ads or analytics, and does not use location for anything else. The
   > permission is requested only the first time the user starts location sharing, after an in-app explanation.

- Video (ak ho formulár žiada): ten istý ako pre službu v popredí §2d —
  `https://psst.pro/video/psst-live-location.mp4`.
- Fakty: D97 (len na vyžiadanie, 15/60 min, `ACCESS_BACKGROUND_LOCATION` zakázané v `check-manifest.py`),
  manifest `features/location/impl/src/main/AndroidManifest.xml` (COARSE + FINE), `MapDefaults.permissions`.

## 5. Bluetooth (LoRa, 26.11.2) — no Play declaration (D109)

- `BLUETOOTH_SCAN` (`android:usesPermissionFlags="neverForLocation"`) and `BLUETOOTH_CONNECT` are runtime
  permissions of the „Nearby devices“ group. Play has **no declaration form** for them: they are not in the list of
  permissions requiring a declaration in „Permissions and APIs that Access Sensitive Information“
  (answer/16558241: fine/background location, photos/videos, all files, SMS/Call Log, package visibility, install
  packages, Health Connect, Accessibility, exact alarm, full-screen intent, local network, manage contacts).
- `neverForLocation` = the app asserts it does not derive physical location from scan results
  (developer.android.com/develop/connectivity/bluetooth/bt-permissions: „you can strongly assert that your app
  doesn't derive physical location“; „some BLE beacons are filtered from the scan results“). Meshtastic radios
  are found by their GATT service, so the filtering does not matter. psst keeps ACCESS_FINE_LOCATION for D97 only;
  the BLE scan does not need it.
- **Ak** Android drží spojenie s rádiom na pozadí službou v popredí (typ `connectedDevice`), treba ju vyhlásiť v
  App content → Foreground service permissions s videom (answer/13392821: video „must show the in-app setup and
  subsequent device interaction, not system settings“). Toto som v Android forku neoveril (LoRa tam v mojej kópii
  ešte nie je) — overí tím Androidu podľa zlúčeného manifestu (`check-manifest.py --list`).
- Local network permission (Android 17, deklarácia od 25. 8. 2027) sa LoRa cez BLE netýka; týkala by sa
  pripojenia rádia cez Wi-Fi/TCP.
