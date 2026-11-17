# Android message notifications: psst vs. upstream Element X (v26.11.0)

Written for batch 12 (2026-11-16). The goal was to find why a Samsung Galaxy A05 (One UI, Android 14) only beeps on a new message: no pop-up, nothing on the lock screen, the message only in the shade. A Honor phone works. **The Samsung was not connected over adb during this batch**, so this is a code comparison plus emulator evidence. The diagnostics screen added in b24 is how to get evidence from the phone itself.

## How a message notification is produced (upstream and psst are the same here)

1. **Push arrives.** FCM data message → `DefaultPushHandler.handle`.
   - The push holds only `event_id`, `room_id`, `unread` and `cs` (the client secret identifying the account).
   - The request is stored in the push history DB and a WorkManager job (`NOTIFICATION_SYNC`) is queued.
2. **The job resolves the event.** `DefaultNotifiableEventResolver` uses the Rust `NotificationClient`. It fetches and decrypts the event and evaluates push rules (noisy = rule has a sound).
   - If resolution fails or times out, a `FallbackNotifiableEvent` is produced instead: "You have N new messages", no content.
3. **`NotificationResultProcessor` → `DefaultNotificationDrawerManager` → `NotificationRenderer.render`.** For each account it posts these notifications in this order:
   - one notification per room (tag = room id, id = per-account messages id), built by `NotificationCreator.createMessagesListNotification`:
     - `MessagingStyle`;
     - category `msg`;
     - group = user id;
     - `setGroupAlertBehavior(GROUP_ALERT_CHILDREN)`;
     - `setOnlyAlertOnce(isUpdated || no new events)`;
     - `setShortcutId(...)`, so it is a conversation notification;
     - channel = noisy channel if the push rule has sound, otherwise silent.
   - invitations and simple events, each `GROUP_ALERT_ALL` + `onlyAlertOnce`;
   - a fallback notification (`GROUP_ALERT_ALL`, `onlyAlertOnce`, `PRIORITY_LOW`, noisy channel if noisy);
   - **the group summary, posted last** (`createSummaryListNotification`): same noisy channel, `setOnlyAlertOnce(true)`, `setGroupSummary(true)`.
     - Upstream does **not** set a group alert behaviour on the summary, so it keeps the default `GROUP_ALERT_ALL`.

**Upstream bug.** The comment on the children says GROUP_ALERT_CHILDREN is there "to avoid notification making sound twice (due to the summary)". But on a child that flag does nothing: it only mutes a notification when set on the *summary*. So the first summary of a group (and again after every "clear all" or "open the app") is itself an alerting notification on the same channel.

## What psst changes

| | upstream v26.11.0 | psst |
|---|---|---|
| Message channel | `DEFAULT_NOISY_NOTIFICATION_CHANNEL_ID_V2…`, **IMPORTANCE_DEFAULT** (sound, never a pop-up) | `PSST_MESSAGES_V4[_vN]`, **IMPORTANCE_HIGH**, named "Správy"; old channels deleted (D53, D61) |
| Group summary | alerting (`GROUP_ALERT_ALL`) | **`GROUP_ALERT_CHILDREN`, never alerts** (b24, D67) |
| Setup wizard | — | checks notifications, lock-screen setting, full-screen intents, battery (D61) |
| Diagnostics | developer "push history" only | Settings → Notifications → "Diagnostika upozornení (psst)" (b24, D67) |
| Verification request | not pushed | server wake-up push → "Žiadosť o overenie" notification (b24, D68) |

Everything else in the push path (WorkManager queue, resolver, fallback, renderer order, MessagingStyle, shortcuts) is unchanged upstream code.

## Emulator evidence (Android 14, AOSP SystemUI)

Captured with `logcat -b events` (`notification_enqueue`, `notification_alert`) and `dumpsys notification`.

- **b23:** the room notification (`858601`) and the summary (`858600`) are enqueued 6 ms apart on the same HIGH channel. Only the child produced `notification_alert`, and it showed as a pop-up.
  - The summary was **muted only by AOSP's per-app alert rate limiter** (about one alert per second per package). Nothing in the notification itself muted it.
- **b24:** the summary now has `groupAlertBehavior=2` (CHILDREN). The child still alerts and pops up; the summary never alerts.
- **Wake-up push for a verification request:** delivered with the app force-stopped, about 0.5 s after the web client sent the request (`notification_alert` for id 7431). Tapping it opened the "Verification requested" screen.

## Why this can look like "beep, no pop-up" on a Samsung

1. **The summary may take the alert.** A summary is never shown as a pop-up and is hidden behind its children in the shade and on the lock screen. If a launcher lets the summary alert instead of rate-limiting it, the visible result is exactly a sound with no pop-up.
   - One UI's SystemUI and NotificationManagerService are heavily modified, and the A05 is slow, so the time between the two posts is larger.
   - **b24 removes this possibility:** the summary can no longer alert at all.
2. **Phone-level One UI settings the app cannot change.** These are not visible in the per-app page:
   - "Notification pop-up style" (Brief / Detailed, and per-app lists for Brief);
   - lock screen notification style "Icons only";
   - per-category "Show as pop-up" when "Notification categories" is enabled (One UI 6.1+).
   - The diagnostics report dumps every readable `global/secure/system` setting matching notif / heads_up / popup / lock_screen / edge_lighting / brief, so the next report shows them.
3. **System ranking that differs from the channel.** A conversation can get its own sub-channel with its own importance and sound. The report shows it as a `CHANNEL` line under every active psst notification (read with `getNotificationChannel(channel, shortcutId)`).
   - Per-notification ranking (`suppressed` visual effects, `intercepted` by DND, lock-screen override) needs a `NotificationListenerService`. psst no longer has one (DECISIONS.md D83): Google Play Protect blocks installing sideloaded apps that declare it. The DND filter and the lock state are still logged for every posted notification.

## What the user's report from the phone will tell

To produce it: Settings → Notifications → "Diagnostika upozornení (psst)" → receive a real message → "Uložiť a odoslať".

The `== log` section then shows, for every push:

- when it arrived and how long it took to resolve;
- whether the result was a real message or a FALLBACK (with cause);
- every posted notification with its channel, the channel importance at that moment, `onlyAlertOnce`, group alert behaviour, summary flag, conversation flag, lock state, and DND filter;

The two self-tests separate the message shape from the phone settings:

- "chat-like" = the same shape as a real message: MessagingStyle, group, silent summary;
- "plain" = a single HIGH notification.

If the plain test pops up and the chat-like test does not, grouping or MessagingStyle is the cause. If neither pops up, a One UI setting is.
