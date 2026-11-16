# Device verification request ("Use another device"): what is sent and when it expires

Scope: PSST Web / Desktop (Element Web/Desktop fork 1.12.35, `forks/web`) as the **requesting** new session, and
Element X (iOS/Android, official or our fork) as the **receiving** already-verified device. Versions: matrix-js-sdk
45.1.0, `@matrix-org/matrix-sdk-crypto-wasm` 18.9.2 (built from `matrix-sdk-crypto` 0.19.1), Element X iOS 26.11
(matrix-rust-components-swift 26.11.05 = matrix-rust-sdk `3ff03638`).

## 1. What Web/Desktop sends

Code path on the new session (screen "Confirm your digital identity", `Views.COMPLETE_SECURITY`):

1. `CompleteSecurity` → `SetupEncryptionBody.onVerifyClick()` (`apps/web/src/components/structures/auth/SetupEncryptionBody.tsx`)
   calls `cli.getCrypto().requestOwnUserVerification()` and opens `VerificationRequestDialog` with that promise.
2. matrix-js-sdk `RustCrypto.requestOwnUserVerification()` (`src/rust-crypto/rust-crypto.ts`) →
   `OwnUserIdentity.requestVerification(methods)` (wasm) → `OutgoingRequestProcessor.sendToDeviceRequest()`.
3. matrix-sdk-crypto `OwnUserIdentity::request_verification_helper()` (`src/identities/user.rs`) picks the recipients
   with `filter_devices_to_request()`: **all of our own devices that are signed by our self-signing key
   (cross-signed = verified), except the current device**. Unverified devices do not get the request.
4. `VerificationRequest::request_to_device()` (`src/verification/requests.rs`) builds one to-device message per
   recipient device:

```
PUT /_matrix/client/v3/sendToDevice/m.key.verification.request/{random txnId}
{"messages": {"@user:chat.macet.eu": {"<DEVICEID>": {
    "from_device": "<new session device id>",
    "transaction_id": "<random flow id, same for all recipients>",
    "methods": ["m.sas.v1", "m.qr_code.show.v1", "m.reciprocate.v1"],
    "timestamp": <sender's clock, ms since epoch>
}}}}
```

The methods come from Element Web's client options (`apps/web/src/utils/createMatrixClient.ts`:
`verificationMethods: [Sas, ShowQrCode, Reciprocate]`). The message is **not encrypted** (plain to-device event) and
is not a room event.

## 2. When it expires

- **Requester (Web/Desktop):** `VERIFICATION_TIMEOUT = 10 min` (`matrix-sdk-crypto` `src/verification/requests.rs`),
  measured from the creation of the request object. `VerificationRequest.timeout` in js-sdk returns the remaining
  milliseconds (`timeRemainingMillis()`). After the 10 minutes, the next sync runs `VerificationMachine::garbage_collect()`
  (called from `preprocess_sync_changes`), which cancels the request with `m.timeout` and sends
  `m.key.verification.cancel` to the same devices. The dialog then shows the "cancelled" state.
  Closing the dialog cancels the request immediately (`SetupEncryptionBody`: `request.cancel()` → `m.user`).
- **Receiver (Element X, rust SDK):** `VerificationMachine::is_timestamp_valid()` (`src/verification/machine.rs`)
  silently ignores a request whose `timestamp` is **more than 10 minutes in the past or more than 5 minutes in the
  future** compared with the receiver's clock. So a request is usable for at most ~10 minutes after it was sent, and
  a sender clock that is >10 min behind or >5 min ahead makes every request invalid.
- **Element X iOS adds no further time limit.** The FFI (`bindings/matrix-sdk-ffi/src/client.rs` event handler for
  `ToDeviceKeyVerificationRequestEvent` → `session_verification.rs` `process_incoming_verification_request`) shows the
  request if it is still in state `Requested`. For a request from one of our own devices it drops it silently only
  if the phone is itself verified but lacks the private self-signing key. (An earlier note in DECISIONS D62
  mentioned a 1-minute limit; this is not in the code of these versions.)
- Once accepted, the SAS (emoji) step has its own limits: 5 min total, 1 min between messages
  (`src/verification/sas/sas_state.rs`, `MAX_AGE`, `MAX_EVENT_TIMEOUT`).

## 3. Why the iPhone did not show it

To-device messages are **not pushed**: Matrix push rules and the push gateway (Sygnal) only handle room events, and
there is no spec mechanism to push to-device messages. The server queues the message until the phone's app syncs.
Element X on iOS only syncs while it is in the foreground (iOS suspends it shortly after it goes to the background).
So when the iPhone app is closed or in the background:

- nothing appears on the phone, no notification;
- the request is only processed when the user opens Element X;
- if that happens more than 10 minutes after the request was sent (or after the requester cancelled it, e.g. by
  closing the dialog or by the 10-minute timeout), the phone ignores it or receives the cancel together with it, and
  nothing is shown.

The second attempt worked because the app on the phone was open (syncing) at the time of the request.

## 4. What PSST Web/Desktop shows now (D71)

While waiting for the other device, the dialog says to open psst/Element on the other device now, that the request
does not arrive as a notification, that it is valid for about 10 minutes, and shows the remaining time
(`VerificationRequest.timeout`). "Send again" cancels the current request and sends a new one; it is also offered
after the request expired or was cancelled, instead of only "Got it". Strings are in `en_EN.json` and `sk.json`
(`encryption.verification.psst_*`); code in `PsstSelfVerificationWaiting.tsx`, `EncryptionPanel.tsx`,
`VerificationPanel.tsx`, `VerificationRequestDialog.tsx` (`allowResend`, set only by `SetupEncryptionBody`).

Advice for users: start verification on the new device, then **open the app on the old phone** and keep it open
until the request appears; if nothing appears within a few seconds, press "Send again".
