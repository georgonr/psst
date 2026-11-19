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

## 3. Permissions that are NOT in the app any more (removed in b51, D87)

| Permission | Why it was removed | Replacement |
|---|---|---|
| `REQUEST_INSTALL_PACKAGES` | Play allows it only for apps whose core purpose is installing packages | an `.apk` attachment is opened like any other file; updates are downloaded in the browser from app.psst.pro/download |
| `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `FOREGROUND_SERVICE_LOCATION` | location sharing is not offered in psst (no map key); the live-location service and the location provider were removed | — |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Play: not acceptable for chat/calling apps that can use FCM (developer.android.com/training/monitoring-device-state/doze-standby#exemption-cases, row "Instant messaging, chat, or calling app … Yes, using FCM → Not Acceptable") | the "Battery" step in Notifications & calls explains App info → Battery → Unrestricted and opens the app's system page |

`scripts/android/check-manifest.py` fails the CI build and the signing script if any of them comes back.
