# Android QR code device verification: what is upstream and what is psst

Written for whoever merges a new Element X Android release into the psst fork, or a new matrix-rust-sdk. Decision:
DECISIONS.md D81. The Rust SDK build is shared with message search: see [android-search.md](android-search.md). Both
patches are applied and released together, so update them in one go (section "Updating to a new upstream" below).

## Protocol

psst uses only the standard Matrix "QR codes" verification:

- methods `m.qr_code.show.v1`, `m.qr_code.scan.v1` and `m.reciprocate.v1`, next to `m.sas.v1` (emoji);
- the binary QR payload `MATRIX\x02…`, encoded in byte mode.

This is the same as Element Web and Element Desktop, so the flows work in both directions with them.

**Login with a QR code is a different feature** (MSC4108, `LoginWithQrCodeHandler`) and was not touched.

## What upstream has (matrix-rust-sdk at the commit of sdk-android 26.11.05, Element X Android v26.11.0)

- **Rust crypto and `matrix-sdk`:**
  - complete QR verification (`VerificationRequest::generate_qr_code`, `scan_qr_code`, `QrVerification::confirm`, states `Scanned` / `Reciprocated` / `Done`), behind the cargo feature `qrcode`;
  - `matrix-sdk-crypto` lets a request that shows a QR code still switch to emoji (`start_sas` from `Transitioned`).
- **What was missing:**
  - **FFI (Kotlin interface):** `SessionVerificationController` offered only SAS. It requested and accepted only `m.sas.v1`, and stopped listening when the other side started a non-SAS flow. The `qrcode` feature was not enabled for `matrix-sdk-ffi`.
  - **App screens:** emoji comparison only.
  - **Element X iOS** (official SDK) still offers emoji only.

## What psst changes

| Where | File | What |
|---|---|---|
| Rust FFI (patch) | `scripts/android/rust-sdk/psst-qr-verification.patch` → `bindings/matrix-sdk-ffi/Cargo.toml` (feature `qrcode`), `src/session_verification.rs` | **Methods:** requests and acceptance advertise SAS + QR show/scan + reciprocate. **New calls:** `qr_options()` (which roles the other device allows), `generate_qr_code()` (bytes), `scan_qr_code(bytes)` → `Started` / `InvalidCode` / `KeyMismatch` / `NotApplicable`, `confirm_qr_scanned()`, `set_qr_delegate()` (progress `Scanned` / `Reciprocated` / `Confirmed` / `Done` / `Cancelled`). **Upstream behaviour kept:** `did_finish` / `did_cancel` of the existing delegate are also called for QR. The request listener no longer stops on a QR transition (emoji stays possible), and `start_sas_verification` works after a QR code was shown. **Additive only:** no existing signature changed. |
| CI | `.github/workflows/android-rust-sdk.yml` | Applies every `*.patch`. Builds the AAR with the official `matrix-rust-components-kotlin` project at tag `sdk-v<version>`, because the Kotlin bindings now differ. Fails if they differ anywhere but `matrix_sdk_ffi.kt`. Release `android-rust-sdk-26.11.05-psst2`. |
| fork | `libraries/matrix/api/.../verification/psst/PsstQrVerification.kt` (new) | Kotlin API: options, QR bytes, scan result, confirm, progress, last cancel code. |
| fork | `libraries/matrix/impl/.../verification/RustSessionVerificationService.kt` | Implements it (`PsstQrVerification`, `QrVerificationDelegate`). Marked `PSST (D81)`. |
| fork | `libraries/qrcode/.../PsstBinaryQrCodeImage.kt` (new) | QR image for binary data (ISO-8859-1 → byte mode, no ECI). The camera scanner `QrCodeCameraView` is upstream (zxing-cpp, already returns bytes). |
| fork | `features/verifysession/impl/.../psst/PsstQrVerificationSection.kt` (new) | Once the request is ready, the section shows: our QR code (if the other device can scan), "Naskenovať QR kód" (if it shows one), and always "Porovnať emoji". **Camera:** permission is asked only when scanning; on refusal, a message plus system settings or emoji. **Feedback:** messages for a foreign or invalid code and for a code of another flow (key mismatch). **Progress:** "the other device scanned → confirm", "scanned → confirm on the other device". Also explains why a verification stopped (`m.timeout`, `m.user`, mismatch, `m.accepted`, unsupported method). |
| fork | `features/verifysession/impl/.../outgoing/*`, `.../incoming/*` | **Outgoing** (this device asked): the QR section on the "ready" step; the emoji button is labelled "Porovnať emoji". **Incoming** (another device asked): after accepting, emoji starts at once only if the other device does not support QR (Element X iOS); otherwise the user chooses. **Both state machines:** go to "completed" when a QR flow finishes. **Strings:** `res/values{,-sk}/psst_qr_strings.xml`. |

## Updating to a new upstream

Do this together with the search patch ([android-search.md](android-search.md), "Updating to a new upstream"):

1. **Pin the new release.** Put the new `SDK_VERSION` / `RUST_SDK_REF` in `scripts/android/rust-sdk/pins.env` and set `PSST_REV=1`.
2. **Run the release workflow.** Run *Android Rust SDK (psst patch)*. It fails if a patch no longer applies, or if the bindings change outside `matrix_sdk_ffi.kt`. Then put the new tag and SHA-256 into the fork's `libraries/rustsdk/psst-rust-sdk.properties`.
3. **If `session_verification.rs` changed upstream:** rebase `psst-qr-verification.patch` on it, keeping the delegate calls and the "keep listening on a QR transition" rule.
4. **If upstream adds QR verification itself:** to the FFI and the Element X screens. Drop the patch, `PsstQrVerification*`, `PsstQrVerificationSection` and the `PSST (D81)` lines in the verification state machines.
5. **Expected conflicts:** small ones in `OutgoingVerification{View,Presenter,State,StateMachine}.kt`, `IncomingVerification{View,Presenter,State,StateMachine,ViewEvent}.kt` and `RustSessionVerificationService.kt` (all marked `PSST (D81)`), plus `features/verifysession/impl/build.gradle.kts` (dependency on `libraries:qrcode`).
6. **Test after an update:**
   - Android ↔ web, both directions (the web shows a QR code, Android scans it);
   - Android ↔ Android (one shows, one scans);
   - emoji as a fallback;
   - a new login that decrypts older messages after QR verification.

## Limits

- Element Web and Desktop cannot scan a QR code (no camera in the web client). With them, Android always scans the code they show.
- When the other device says the scan was wrong, Android sends the standard cancel code `m.user` ("Nie – zastaviť overenie"), as Element Web does. The upstream crypto API has no separate "mismatch" for QR.
