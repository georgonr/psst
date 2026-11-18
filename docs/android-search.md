# Android message search: what is upstream and what is psst

Written for whoever merges a new Element X Android release into the psst fork, or a new matrix-rust-sdk. Decision:
DECISIONS.md D80.

## What upstream already has (Element X Android v26.11.0 + matrix-rust-sdk at the commit of sdk-android 26.11.05)

The whole pipeline exists upstream. psst completes it; it does not add a second index.

- **Index.** `matrix-sdk-search` (Rust) keeps one tantivy index per room in
  `files/sessions/<id>/search-index/<room id>/`.
  - It is encrypted at rest with the session secret (`withSearchIndexStore(path, key)` in `RustMatrixClientFactory`).
  - Nothing leaves the phone, and it is deleted with the session directory on logout.
- **What gets indexed.** The event cache indexes every decrypted `m.room.message` (text, notice, emote, file and media
  names and captions), stickers and polls. This covers:
  - events arriving from sync or back-pagination;
  - edits: the newest version replaces the old one in the index;
  - redactions: the event is removed from the index.
  - Encrypted and unencrypted rooms are treated the same, because indexing happens after decryption.
- **History.** `run_search_backfill`:
  - first reindexes everything already stored in the event cache;
  - then back-paginates every joined room week by week, up to 13 weeks, at the lowest priority of the back-pagination queue.
- **When the history is filled.**
  - upstream runs it while the global search screen is open (`FOREGROUND`, rooms 1 s apart);
  - and in an hourly WorkManager job that needs a charger and Wi-Fi (`BACKGROUND`, at most 10 min per run).
- **Search.**
  - `Client::search_messages` searches every joined room's index. It merges the results newest first, 20 per page, and loads each event.
  - The UI (`SearchService` → `RustMessageSearch`) is the "Messages" tab of the home screen search.
  - Tapping a result opens the room at that event.
  - Feature flag `MessageSearch` (default on, not finished upstream).

## Why it found nothing (b23–b29)

The index used tantivy's default analyzer, which only splits words and lowercases them. The query parser matched whole
words only. So:

- `cislo` never found `číslo`;
- `ob` never found `obed`;
- partial and diacritic-free words always returned "no results".

The test in b27 typed such words. Exact words were found, but only in the newest messages: history was only indexed
while the search screen was open.

## What psst changes

| Where | File | What |
|---|---|---|
| Rust (patch) | `scripts/android/rust-sdk/psst-search.patch` → `matrix-sdk-search/src/schema.rs`, `index/mod.rs` | Message body tokenizer `psst_folded` = default + `AsciiFoldingFilter`, which also runs on the query. Query parser: every single word is a prefix match (`set_field_fuzzy(body, prefix, distance 0)`). Unit test `test_search_folds_diacritics_and_matches_prefixes`. **No FFI change.** |
| CI | `.github/workflows/android-rust-sdk.yml`, `scripts/android/rust-sdk/{pins.env,unzip-stream.py}` | Builds `libmatrix_sdk_ffi.so` for arm64, armv7 and x86_64 at the pinned commit with the patch. Proves that the generated Kotlin bindings are byte-identical to the official sources jar. Swaps the `.so` into the **official** `sdk-android` AAR and publishes the GitHub release `android-rust-sdk-<ver>-psst<rev>` (AAR + SHA-256). |
| CI | `.github/workflows/android.yml` | Downloads that AAR (tag and SHA-256 from the fork's `libraries/rustsdk/psst-rust-sdk.properties`) into `libraries/rustsdk/matrix-rust-sdk.aar`. Checks that the built APKs contain exactly its `.so`. |
| fork | `libraries/matrix/impl/build.gradle.kts` | Release builds use `libraries/rustsdk/matrix-rust-sdk.aar` when it exists (upstream only did this for debug). |
| fork | `libraries/matrix/impl/.../search/PsstSearchQuery.kt` (new), `RustMessageSearch.kt` (1 line) | The query is split into words exactly like the index splits them, and each word is required (`+word`). Upstream's `TantivyQueryEscaper.kt` is kept unchanged but no longer used. |
| fork | `RustMatrixClientFactory.kt` | **Index marker:** `search-index/psst-folded-v1`. An index without it (written by b29 or older) is deleted once, so the SDK reindexes stored events and the backfill refetches the history. |
| fork | `RustMatrixClientFactory.kt` | **Key backup:** `backupDownloadStrategy(ONE_SHOT)`. After the recovery key is entered, all room keys come from the key backup at once. The redecryptor then decrypts the stored history and indexes it. Upstream fetches one key per decryption failure, but only for events the timeline shows. After a new login, the history fetched by the backfill stayed encrypted: measured 38 of 56 hits, and the missing ones appeared only after scrolling through each conversation. |
| fork | `libraries/matrix/api/.../search/psst/PsstSearchIndexing.kt`, `impl/.../search/psst/DefaultPsstSearchIndexing.kt` (new); `appnav/.../LoggedInPresenter.kt` | Runs the upstream `FOREGROUND` backfill while psst is on screen: 8 s after start, then at most once a day per device (time stored in SharedPreferences); it stops when psst goes to the background. Exposes "history is still being indexed". |
| fork | `features/home/impl/.../search/GlobalSearch{State,Presenter,View}.kt` | Snippet around the first match with the searched words highlighted, sender kept. "Staršie správy sa ešte indexujú" row. Upstream starts a sweep each time search is first opened; psst only does that when the daily sweep is due, because one sweep re-reads the whole stored history: about 10 s CPU for ~930 messages on the emulator. |
| fork | `features/roomdetails/impl/.../psst/search/*` (new); `RoomDetails{View,Node,FlowNode}.kt` | Room details → "Hľadať v správach": search in one conversation, using upstream `createMessageSearch(roomId)`. Tapping a result opens the timeline at the message. |
| fork | `libraries/designsystem/.../psst/PsstSearchHighlight.kt` (new) | Folding-aware snippet and highlight, shared by both screens. |
| fork | `res/values{,-sk}/psst_search_strings.xml` in home and roomdetails | SK/EN texts. Since D84 also the Slovak for upstream's search screen (tabs, empty states), which Localazy does not have yet. |
| fork | `features/home/impl/.../search/GlobalSearchView.kt` (D84) | The **Chats** tab shows its own empty state ("No chat with this name" + "Search in messages") instead of upstream's Messages empty state. |

## "Search finds nothing" in b42/b43 was a test error (D84)

Batch 16 reported that b42 and b43 find nothing, not even a message that just arrived. That was wrong:

- The test typed the word and read the screen without switching to **Messages**. The search screen opens on the
  **Chats** tab, which only matches chat NAMES.
- Upstream shows the Messages empty state ("No results in the last 3 months – There are no results for “…” in your
  recent messages") on the Chats tab too. So the screen looked exactly like a broken message search.
- Repeated on b43 (2026-11-18): the Chats tab shows exactly those texts, and the Messages tab shows the results.
- Every build b37 → b38 → … → b43, updated in place on one account, found the old messages and a message received
  right after each update. b43 also finds messages after a clean install, after a new login with the recovery key, and
  after an identity reset.
- The QR run (batch 15) was right: it switched to Messages and found 5 of 5.

Fixes:

- **App:** the Chats tab now has its own empty state ("No chat with this name") with a **Search in messages** button.
- **Tests:** `scripts/android/search_ui.py` counts only on the Messages tab. It fails if it cannot see the Messages
  header or the Messages empty state.

## Release check (D84)

`scripts/android/sign-release.sh` runs `scripts/android/search-gate.sh` on the x86_64 release APK before signing. A
failure means nothing is signed or uploaded. The check:

1. installs the APK (with a throwaway signature) in the Android 14 emulator;
2. signs in a fresh test account `qa-sg…`;
3. a partner (`search_check.py`, matrix-nio with E2EE) sends 8 Slovak messages into an **encrypted** room;
4. on the phone it searches the **Messages** tab for `cislo`, `stastn`, `ob`, `zlty kon`, `dvanast` (no diacritics,
   word beginnings) and for a word that is not there;
5. it restarts the app, receives one more message and finds it, plus the new total for `cislo`.

The expected counts are computed from the message texts with the index's rules (ASCII folding, every word a prefix),
not typed by hand. The test accounts and the room are deleted at the end, also on failure.

Run by hand:

```sh
scripts/android/search-gate.sh path/to/app-gplay-x86_64-release-unsigned.apk
```

It needs the psst test venv (`~/.local/psst-venv` with `matrix-nio[e2e]`), ssh access `psst`, and the AVD `psst34`
(or an attached emulator).

## Updating to a new upstream

The same psst Rust SDK build also carries the QR code verification patch ([android-qr-verification.md](android-qr-verification.md)). Since D81 the AAR is built from the patched sources with the official Kotlin components project (the bindings differ only in `matrix_sdk_ffi.kt`), not by swapping `.so` files. Update both patches in one go.

1. **New matrix-rust-sdk / sdk-android version** (`libs.versions.toml` `matrix_sdk`):
   - Take the Rust commit from the release notes of `matrix-rust-components-kotlin` tag `sdk-v<version>` and put it in `pins.env` (`SDK_VERSION`, `RUST_SDK_REF`, `PSST_REV=1`).
   - Run *Android Rust SDK (psst patch)*. It fails if the patch no longer applies, or if the bindings differ from the official ones (that would mean the commit is wrong).
   - Put the new `tag`, `file` and `sha256` in the fork's `libraries/rustsdk/psst-rust-sdk.properties`.
2. **Check in the Rust patch:**
   - whether `RoomMessageSchema::new` still adds `body` as `TEXT`;
   - whether `RoomIndex::new_with` is still the only place that creates the query parser.
   - If upstream adds its own folding or prefix search, drop the patch, the marker and `PsstSearchQuery.kt`.
3. **If upstream changes the schema or tokenizer:** bump the marker name in `RustMatrixClientFactory.kt` (`psst-folded-v2`), so existing indexes are rebuilt.
4. **Kotlin conflicts are expected in:**
   - `GlobalSearchView.kt`, `RoomDetailsView.kt`, `RoomDetailsFlowNode.kt`, `LoggedInPresenter.kt`: small, marked `PSST (D80)`;
   - `libraries/matrix/impl/build.gradle.kts`.
5. **If `MessageSearchService.createMessageSearch(roomId)` becomes a real room filter in the SDK:** the room screen's "page until 20 results" loop in `PsstRoomSearchPresenter` can go.
6. **If upstream changes its backup download default, or starts decrypting back-paginated events with backup downloads:** re-check the `ONE_SHOT` line. Run the test "log out → log in with the recovery key → global search finds the whole history".

## Limits

- The history goes back about 3 months (upstream backfill limit, 13 weeks). Older messages are found only if they are already in the event cache, for example from scrolling up in the room.
- A message is searchable only once it is decrypted. Messages whose keys never arrived (no key backup, no other device) are not indexed.
- Prefix matching applies to single words. A word that contains punctuation (`1/2/2024`) is split into its parts.
- An edited message is found by its new text. Its result shows the time of the edit, because the index keeps the newest version as the edit event. Tapping it opens the message.
- Typing words with diacritics in the search field works (the analyzer folds the query too). The emulator test typed only ASCII through adb; the Rust unit test covers `Šťast`/`číslo`.
- Room search filters the global result stream (upstream design). In a room with few matches it pages through other rooms' results first; this is fast enough for psst's number of rooms.
