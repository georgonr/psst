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
| fork | `RustMatrixClientFactory.kt` | Marker `search-index/psst-folded-v1`. An index without it (written by a build before b30) is deleted once, so the SDK reindexes stored events and the backfill refetches the history. |
| fork | `libraries/matrix/api/.../search/psst/PsstSearchIndexing.kt`, `impl/.../search/psst/DefaultPsstSearchIndexing.kt` (new); `appnav/.../LoggedInPresenter.kt` | Runs the upstream `FOREGROUND` backfill while psst is on screen: 8 s after start, then at most every 6 h; it stops when psst goes to the background. Exposes "history is still being indexed". |
| fork | `features/home/impl/.../search/GlobalSearch{State,Presenter,View}.kt` | Snippet around the first match with the searched words highlighted; "Staršie správy sa ešte indexujú" row. |
| fork | `features/roomdetails/impl/.../psst/search/*` (new); `RoomDetails{View,Node,FlowNode}.kt` | Room details → "Hľadať v správach": search in one conversation, using upstream `createMessageSearch(roomId)`. Tapping a result opens the timeline at the message. |
| fork | `libraries/designsystem/.../psst/PsstSearchHighlight.kt` (new) | Folding-aware snippet and highlight, shared by both screens. |
| fork | `res/values{,-sk}/psst_search_strings.xml` in home and roomdetails | SK/EN texts. |

## Updating to a new upstream

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

## Limits

- The history goes back about 3 months (upstream backfill limit, 13 weeks). Older messages are found only if they are already in the event cache, for example from scrolling up in the room.
- A message is searchable only once it is decrypted. Messages whose keys never arrived (no key backup, no other device) are not indexed.
- Prefix matching applies to single words. A word that contains punctuation (`1/2/2024`) is split into its parts.
- Room search filters the global result stream (upstream design). In a room with few matches it pages through other rooms' results first; this is fast enough for psst's number of rooms.
