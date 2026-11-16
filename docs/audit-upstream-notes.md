# PSST: upstream requirements vs our setup (audit notes, 2026-11-16)

Scope: Element Web/Desktop 1.12.35 (`forks/web`), Element X Android 26.11 (`forks/android`), Element X iOS 26.11
(`forks/ios`), server templates in `server/templates/`. Sources: the code and config in this repo plus upstream docs.
Nothing was run against production, so all "verify" items are still open. Line numbers refer to the template files.

Legend: **needs** = what the feature requires from the server or build, **we provide** = what our setup has,
**risk** = what may break, **ev** = evidence.

---

## Cross-cutting findings (most serious first)

1. **iOS NSE filtering entitlement is probably missing, so iOS can show stray "Notification" banners.** The CI removes
   `com.apple.developer.usernotifications.filtering` when the NSE profile lacks it
   (`ci/workflows/ios-release.yml:183-189`), and Apple only grants that entitlement on request (D55). Without it, every
   NSE path that returns `.processedShouldDiscard` or `.unsupportedShouldDiscard` cannot hide the notification. iOS then
   shows the APNs default alert (`locKey: "Notification"`, `NotificationService.swift:141-151`) in these cases:
   ringing calls (CallKit screen plus a banner, `NSE/Sources/NotificationHandler.swift:202-266`), redactions,
   verification events, events from ignored users, and events the NSE cannot decrypt. Fix: request the entitlement
   from Apple, then check that the profile contains it.
2. **Android only registers the pusher after the session is verified.** `DefaultPushService.kt:92-95` returns
   `AccountNotVerified` and skips registration. A user who signs in but does not finish verification (other device or
   recovery key) gets no push at all. This is upstream behaviour, but it combines badly with item 3.
3. **Verification requests sent as to-device messages never trigger a push, on any platform.** This is a protocol
   limitation: push rules and pushers only see room events (see the Push Gateway API spec). No MSC I could find adds
   push for to-device messages. MSC3944 only drops stale to-device messages. On Android, an incoming self-verification
   request is kept for 2 min and then dropped if the app is not in the foreground
   (`appnav/.../verification/IncomingVerificationRequestObserver.kt`, `withTimeoutOrNull(2.minutes)`). In-room
   user-to-user verification requests are room messages, so they do push. The `Accept/Ready/Start/Key/Mac/Done/Cancel`
   follow-up events are filtered out on purpose (`DefaultNotifiableEventResolver.kt:263-271`). Practical effect: to
   verify a new device, the user must open the old one by hand. Document this for users.
4. **People can only be found by full MXID.** `user_directory.search_all_users: false` together with
   `limit_profile_requests_to_users_who_share_rooms: true` (`homeserver.yaml:83-88`) hides users with no shared room
   from search. Element X Android still shows a typed full `@user:chat.macet.eu` as an "unresolved" result
   (`libraries/usersearch/impl/.../MatrixUserRepository.kt:31-63`), so DMs and invites still work. Element Web warns
   "may not exist" and lets the user continue. This is a privacy choice, but it hurts usability for new users.
   Consider `search_all_users: true`, since the server is closed and token-only.
5. **E2EE is forced on public channels.** `encryption_enabled_by_default_for_room_type: all` (`homeserver.yaml:90`) also
   encrypts rooms published in the directory. New joiners cannot read history from before they joined (no key
   sharing on join). Large channels add cost to Megolm key distribution. Room previews from the directory show no
   messages. Accept this or use `invite` instead.
6. **No password recovery path.** MAS has `password_recovery_enabled: false` and `email.transport: blackhole`
   (`templates/mas/config.yaml:57,68`). `email_change_allowed: true` (line 58) lets users add an email that can never be
   verified. The admin page has no password reset (`server/admin/app.py` routes: invites, lock/unlock only), so a
   forgotten password needs `mas-cli` over SSH. A lost password plus a lost recovery key means the account's
   encrypted history is lost.
7. **The server fallback `templates/app/config.json` has drifted from `forks/web/apps/web/psst/config.json`.** The
   fallback has no `oidc_metadata`, no `element_call.use_exclusively`, a different brand, and no `features`. MAS
   policy `allow_missing_client_uri: false` (`mas/config.yaml:91`) would then reject Element Web's dynamic client
   registration, so login would break. DM calls would also fall back to legacy WebRTC, which has no TURN in Synapse
   and does not interoperate with Element X. It is only served when the distribution has no `config.json`
   (`nginx/psst.conf:262-273`); CI checks that it does (`web-desktop.yml:75,177,247`). Low probability, high impact.
   Sync the two files.
8. **Stale or duplicate config entries.** The push comment still says "ntfy for Android" (`homeserver.yaml:173`).
   `allow_public_rooms_without_auth` appears twice (`homeserver.yaml:58,85`). PyYAML accepts duplicate keys, but
   strict linters do not.
9. **MAS compat location is narrower than upstream's.** `nginx/psst.conf:94`
   `^/_matrix/client/[^/]+/(login|logout|refresh)$` does not match `/v3/logout/all` or `/v3/login/sso/redirect...`.
   The MAS docs use `^/_matrix/client/(.*)/(login|logout|refresh)`. Only legacy (non-OIDC) clients are affected.
10. **The Sygnal notify endpoint is public** (`nginx/psst.conf:121`). This is needed so Synapse can reach it by
    hostname, but anyone can POST to it, and a caller who knows a pushkey could send pushes to that device. Consider
    `allow 172.30.0.0/24; deny all;`, because Synapse reaches nginx from inside the Docker network (D34).

---

## Token registration
- needs: MAS with token-gated password registration; clients that open MAS with `prompt=create`. Element Web needs
  `oidc_metadata` for dynamic registration.
- we provide: `password_registration_token_required: true` (`mas/config.yaml:56`), Synapse `enable_registration: false`
  (`homeserver.yaml:64`), tokens issued from the admin page (MAS admin API). Web `oidc_metadata` in
  `psst/config.json:126-131`. Android `METADATA_HOST_REVERSED=eu.macet.app` (`BuildTimeConfig.kt:23`).
- risk: low. MAS per-IP registration limits work because nginx forwards the real client IP (proxy_protocol plus
  `trusted_proxies`). Fallback config drift (item 7).

## Login / logout
- needs: MSC2965/MSC3861 discovery (`/_matrix/client/v1/auth_metadata`), MAS OAuth under `/auth/`, and compat
  endpoints for legacy clients.
- we provide: `matrix_authentication_service.enabled` (`homeserver.yaml:68-71`), compat rewrite
  (`psst.conf:94-103`), MAS prefix vhost (`psst.conf:107-117`). Element X and Web log out through OAuth revocation.
  No `m.authentication` in well-known is needed, because clients use `auth_metadata`.
- risk: item 9 (`logout/all` for legacy clients).

## QR login (MSC4108 / MSC4388)
- needs: Synapse rendezvous (`/_matrix/client/unstable/org.matrix.msc4108/rendezvous`, `/_synapse/client/rendezvous`),
  MAS device-code grant, and clients on the same MSC revision.
- we provide: `msc4108_enabled: true`, `msc4388_mode: open` (`homeserver.yaml:102-103`). Both paths go to Synapse
  (`psst.conf:130`). Verified in production in one direction only: web shows the QR, Android scans it (D58).
- risk: the other combinations are unverified (Android or iOS as the existing device, desktop, iOS as the new device).
  `open` lets unauthenticated clients create rendezvous sessions; abuse is limited by the Synapse rate limit.

## Device verification (emoji + QR)
- needs: to-device messaging and cross-signing upload (UIA is handled by MAS through `org.matrix.cross_signing_reset`).
  No extra server config.
- we provide: Synapse defaults; `force_verification: true` on web (`psst/config.json:12`).
- risk: no push for to-device requests (item 3); Android discards a background request after 2 min. Element Web cannot
  scan QR codes, it can only show them. Cross-signing reset goes through the MAS account page.

## Recovery key + key backup; history on a new device
- needs: `/room_keys` (server-side key backup), account data for secret storage (SSSS). Both are Synapse defaults.
- we provide: defaults. QR login also transfers secrets, including the backup key.
- risk: with no password recovery (item 6), a lost recovery key plus a lost device means history is gone.
  Android devices that are not verified get no push (item 2).

## 1:1 DMs / groups / room invites
- needs: user directory or profile lookup, `/createRoom` presets, local invites.
- we provide: E2EE for every room type (`homeserver.yaml:90`); power-level overrides keep Synapse defaults and set call
  membership to 0 (`homeserver.yaml:113-149`).
- risk: discoverability (item 4).

## Public channels (room directory)
- needs: `room_list_publication_rules` that allow publishing, an alias for each public room, a directory visible to
  logged-in users, and MSC3266 room summary for Element X previews.
- we provide: `room_list_publication_rules: allow` (`homeserver.yaml:59-60`), `allow_public_rooms_without_auth: false`,
  `allow_public_rooms_over_federation: false`; web `UIFeature.allowCreatingPublicRooms/Spaces: true`,
  `room_directory.servers: [chat.macet.eu]`. The comment says MSC3266 is stable in 1.165 (`homeserver.yaml:104`).
- risk: E2EE on channels (item 5). Verify MSC3266 and MSC4222 by checking `/_matrix/client/versions` for v1.15+ or the
  unstable flags (not done here). Any user can publish to the directory; there is no moderation rule.

## Files / images / video / voice messages
- needs: an upload limit in Synapse and nginx, authenticated media (MSC3916, Synapse default since 1.120), and service
  worker or desktop support for authenticated media.
- we provide: `max_upload_size: 100M` (`homeserver.yaml:47`), `client_max_body_size 100M` (`psst.conf:11,138`),
  `proxy_read_timeout 600s`. `sw.js` is served with no-cache (`psst.conf:276`). Desktop has `media-auth.ts`.
  `url_preview_enabled: false` (no link previews, on purpose).
- risk: low. There is no media retention policy, so the disk grows without limit. Location sharing is disabled
  (`UIFeature.locationSharing: false`; maps are off on mobile).

## Replies / reactions / edits / redaction / mentions / read receipts / typing
- needs: nothing beyond Synapse defaults. Push rules for mentions come from intentional mentions (`m.mentions`) and are
  default.
- we provide: defaults. `presence.enabled: false` (`homeserver.yaml:80-81`), so there are no online indicators;
  receipts and typing are not affected.
- risk: `rc_message 0.5/s, burst 30` (`homeserver.yaml:166-168`) is more permissive than the default (0.2/10). Fine.

## Search
- needs: web cannot search encrypted rooms on the server. Desktop needs Seshat. Mobile uses local SDK search where
  available.
- we provide: Desktop ships `@matrix-org/seshat ^6.0.1` as a regular dependency (`apps/desktop/package.json:55`), with
  both arches installed for the macOS universal build (`web-desktop.yml:158-165`). `enableEventIndexing` defaults to
  true (`apps/web/src/settings/Settings.tsx:1311-1315`). iOS registers the `eu.macet.psst.background.search-backfill`
  BGTask (`ElementX/SupportingFiles/target.yml`).
- risk: web cannot search encrypted rooms (which is every room). There is no Linux desktop build. Android Element X
  has no encrypted-message search (not verified in code).

## Notifications
- needs: web uses the Notification API with the tab open (Element Web has no Web Push). Desktop uses Electron while the
  app runs. Android uses FCM through Sygnal (gcm v1). iOS uses APNs through Sygnal plus the NSE and App Group
  `group.eu.macet.psst`. Synapse needs to reach the gateway.
- we provide: Synapse `push.include_content: false`, `ip_range_whitelist: [nginx]` (`homeserver.yaml:175-180`). Sygnal
  v0.15.1 apps are generated by `deploy.sh:296-324`: `eu.macet.psst` gcm v1, and `eu.macet.psst.ios.prod` (production)
  / `.ios.dev` (sandbox) apns, topic `eu.macet.psst`. Android: `PUSHER_HTTP_URL` points to our Sygnal
  (`FirebaseConfig.kt:17`), `EVENT_ID_ONLY` (`RustPushersService.kt:40`), FCM only (`BuildTimeConfig.kt:47-48`).
  Synapse sends encrypted events as `prio: high`, so FCM wakes the app in Doze. iOS: pusher app id
  `<bundle>.ios.prod|dev` (`AppSettings.swift:231-237`), gateway `https://chat.macet.eu` (`:241`), `eventIdOnly` with
  `mutable-content` (`NotificationService.swift:141-151`). The App Group is set in `app.yml:6` and in every
  entitlements file, and CI requires it in all three profiles (`ios-release.yml:197-200`). The NSE target exists
  (`NSE/SupportingFiles/target.yml:58-75`). Release builds use `aps-environment: production` (`ios-release.yml:181`).
- risk: items 1, 2, 3 and 10. Lock-screen and killed-state behaviour on Android depends on the IMPORTANCE_HIGH
  channel (D53) and on full-screen intent permission for calls (D57). Communication Notifications (sender avatars)
  may also be removed by CI (`ios-release.yml:191-195`). Debug and nightly Android app ids (`eu.macet.psst.debug`,
  `.nightly`) are not in Sygnal unless `ANDROID_PUSH_APP_IDS` is set (intended). Desktop shows nothing when it is
  not running; web shows nothing without an open tab.

## 1:1 voice/video call, group call
- needs: Element Call only, for interop with Element X. For MatrixRTC that means: well-known `rtc_foci` and/or
  `/rtc/transports` (MSC4143), lk-jwt-service, LiveKit, MSC4140 delayed events, power level 0 for call membership,
  and ringing via `m.rtc.notification`.
- we provide: web `element_call.use_exclusively: true` (`psst/config.json:68-72`), so DMs also use Element Call
  (`apps/web/src/hooks/room/useRoomCall.ts:118-122,186-190`). Well-known `org.matrix.msc4143.rtc_foci` uses the legacy
  `livekit_service_url` (`psst.conf:81`). Synapse `matrix_rtc.transports` has both `m.livekit` and legacy `livekit`
  (`homeserver.yaml:151-160`); MSC4143/4502/4512 are enabled (`:95-98`). `max_event_delay_duration: 24h` (`:107`),
  `rc_delayed_event_mgmt` (`:169-171`). lk-jwt-service: full access for our server only, remote publishing off
  (`compose.yml:85-88`). LiveKit `auto_create: false` (`livekit.yaml:24`). Standalone Element Call uses
  `matrix_rtc_mode: compatibility` (`element-call/config.json:8`). Call membership is set to power level 0 (D24).
- risk: low. Element Web uses an embedded Element Call build and Element X bundles its own; versions can drift from
  `element-call:v0.28.2` at call.macet.eu. Keep them in step at upgrades. Legacy `m.call.*` from third-party clients
  are not supported (Synapse has no `turn_uris`; on purpose).

## Screen sharing
- needs: web uses `getDisplayMedia`; Desktop uses `displayMediaCallback.ts` (upstream). Android would need
  MediaProjection plus a foreground service type.
- we provide: Web and Desktop work as upstream.
- risk: Element X Android has no MediaProjection code (grep found none), so it cannot share its screen but can view
  shares. Element X iOS has no broadcast extension, so likely the same. Upstream limitation, not caused by our
  changes.

## Calls behind blocked UDP
- needs: ICE/TCP to the SFU (7881) and TURN/TLS on 443.
- we provide: LiveKit `tcp_port 7881`, `udp_port 7882` (`livekit.yaml:7-9`) and `turn_servers` TLS on 443
  (`:14-19`). The nginx stream sends call.macet.eu traffic without h2/http1 ALPN to coturn
  (`nginx.conf:20-23,34-43`). coturn relays only to the SFU (`turnserver.conf:18-21`). Relay-only was verified (D35).
- risk: a TURN client that sends ALPN `http/1.1` would be routed to HTTPS instead of coturn. libwebrtc sends no ALPN,
  so this is fine today. call.macet.eu gets SSL Labs grade A instead of A+ (D46). The whole design depends on the
  ALPN heuristic. A separate `turn.` DNS name would be more robust, but DNS is fixed (D42).

## Profile + avatar
- needs: `enable_set_displayname`/`avatar_url`; MAS `displayname_change_allowed`.
- we provide: `homeserver.yaml:76-77`, `mas/config.yaml:59`.
- risk: low. Profile lookups are limited to users who share a room (item 4).

## Password change / session management
- needs: MAS `account_management_uri` (published in `auth_metadata`), `password_change_allowed`, and the MAS account
  page for sessions. Clients link to it (Element X Settings, Element Web Settings and session manager).
- we provide: MAS `passwords.enabled`, `password_change_allowed: true` (`mas/config.yaml:46-60`), and the human
  resource on `/auth/`.
- risk: no recovery (item 6). Element Web hides its own password form under OIDC (expected).

## User blocking (ignore) / leaving rooms / member and power-level management
- needs: Synapse defaults (`m.ignored_user_list` account data, `/leave`, `/forget`, power levels).
- we provide: defaults. The power-level overrides copy Synapse's defaults (`homeserver.yaml:113-149`).
- risk: an ignored user's events can still trigger an iOS push. The NSE drops them, but without the filtering
  entitlement a "Notification" banner appears (item 1).

## Admin page (server/admin)
- needs: MAS admin API (client_credentials `urn:mas:admin`), Synapse admin API internally, and an OIDC login client.
- we provide: static MAS client plus `policy.data.admin_clients` (`mas/config.yaml:75-85`). The admin app calls
  `http://synapse:8008/_synapse/admin/...` internally (`server/admin/app.py:32,382,507`), while the public
  `/_synapse/admin` returns 404 (`psst.conf:91`). Locking is done in both MAS and Synapse.
- risk: no password reset or deactivation in the UI. The users list is capped at `limit=1000` (`app.py:382`).

## Download page and new-version check
- needs: desktop checks `/download/latest.json`. Web compares the `/version` file. Mobile has nothing built in.
- we provide: `apps/desktop/src/psst-update-check.ts`: 60 s after start, then daily, using keys `windows`/`macos` with
  `.build` (matches `server/scripts/downloads.py:174`). Element's updater is off because there is no
  `update_base_url` (`electron-main.ts:231-234`). Web: `VersionFilePlugin` writes `version` (`webpack.config.*:740`),
  nginx serves it with no-cache (`psst.conf:276`). Android: none; sideloaded APKs never prompt for updates. iOS:
  TestFlight/App Store handles updates.
- risk: Android users keep stale builds indefinitely (e.g. D52, where UnifiedPush builds silently lost push).
  Consider a small `latest.json` check in the Android fork. The desktop check needs `Notification.isSupported()`;
  macOS notifications from an ad-hoc-signed app may be denied silently, and the check has no in-app fallback.

## Analytics / telemetry removal (sanity)
- Web: no `posthog`, `sentry` or `bug_report_endpoint_url` in `psst/config.json`. Desktop still bundles
  `@sentry/electron` (`package.json:56`), but it only starts when `config.sentry.dsn` is set (`electron-main.ts:67-91`).
  Android: PostHog/Sentry/rageshake are null (`BuildTimeConfig.kt:38-44`). iOS: NSE configured with `sentryURL: nil`
  (`NotificationServiceExtension.swift`). MAS telemetry and Sentry are off (`mas/config.yaml:101-107`). No breakage
  found from these removals.

Sources: Matrix Push Gateway API spec (https://spec.matrix.org/v1.9/push-gateway-api), MSC3944
(https://github.com/matrix-org/matrix-spec-proposals/pull/3944), MAS reverse-proxy docs, and the Element Call
self-hosting guide.
