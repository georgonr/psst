# PSST — rozhodnutia

Každé rozhodnutie: čo, prečo, dôsledok. Detailné rozhodnutia jednotlivých platforiem sú v
[docs/decisions/](docs/decisions/) a sú zhrnuté nižšie.

## Prostredie a stratégia

**D1 — Ťažké buildy bežia na GitHub Actions, nie lokálne.**
Lokálny stroj: Intel Mac (x86_64), macOS 15.7, **6,3 GB voľného miesta**, bez Dockeru, bez Android SDK,
Java len z `brew openjdk@17` (keg-only), Xcode 16.0. Build Element Web/Desktop (pnpm monorepo + Electron),
Element X Android (Gradle + SDK + NDK cache) aj Element X iOS (SPM, matrix-rust-sdk binárky) potrebuje
desiatky GB. Repo je verejné → runnery GitHub Actions (ubuntu/macos/windows) sú zadarmo a prostredie je
reprodukovateľné. Lokálne sa robí len to, čo sa zmestí: ikony, keystore, editácia forkov, dokumentácia.

**D2 — Forky ako samostatné GitHub forky + git submoduly v hlavnom repe.**
`georgonr/psst-web` (fork element-hq/element-web), `georgonr/psst-android` (fork element-x-android),
`georgonr/psst-ios` (fork element-x-ios). Úpravy sú na vetve `psst` založenej na najnovšom stabilnom tagu.
Prečo nie subtree: element-web má ~600 MB histórie; subtree by nafúkal hlavné repo a zlúčenia z upstreamu
sú cez fork + `git merge <tag>` priamočiarejšie. GitHub fork zároveň viditeľne zachováva AGPL pôvod.
Hlavné repo `georgonr/psst` drží ikony, server, CI a dokumentáciu; forky sú v `forks/*` ako submoduly.

**D3 — Žiadne samostatné repo psst-desktop.** `element-hq/element-desktop` je archivovaný; desktop bol
vrátený do monorepa element-web (`apps/desktop`). Fork `psst-web` preto pokrýva web aj desktop.

**D4 — Verzie upstreamov (najnovšie stabilné k 2026-11-13):** element-web **v1.12.35**,
element-x-android **v26.11.0**, element-x-ios **26.11.0** (tag `release/26.11.0`),
element-call **v0.28.2**, lk-jwt-service **v0.10.0**.

**D5 — CI workflowy sú v hlavnom repe**, nie vo forkoch. Forky obsahujú desiatky upstream workflowov
(publikovanie, Sentry, Localazy…), ktoré nechceme spúšťať; v hlavnom repe sa fork checkoutne na vetve `psst`.

**D6 — Overenie (bod 7) beží v efemérnych CI runneroch.** Docker lokálne nie je a na disku nie je miesto na VM
(colima). Runner `ubuntu-latest` má Docker, KVM pre Android emulátor a je to stále „lokálne" overenie,
nie nasadenie na server.

## Logo a ikony

**D7 — Piaty stĺpec (výška 8) má polomer 4, nie 6,5.** SVG pri `rx=6.5` na obdĺžniku 13×8 orezá `ry` na 4,
čím vznikne elipsa, nie zaoblený stĺpec. Polomer `min(6.5, h/2)` zachová „zaoblené konce" ako u ostatných.

**D8 — Generátor ikon bez závislostí.** Na stroji nie je rsvg/inkscape/ImageMagick/Pillow. `scripts/make-icons.sh`
volá čistý Python rasterizér (signed-distance funkcie zaoblených obdĺžnikov s analytickým anti-aliasingom),
ktorý **kreslí každú veľkosť z geometrie**, nič sa neprevzorkováva. `.icns` balí `iconutil`, `.ico` sa skladá
priamo (PNG záznamy 16–256). Android ikony sú VectorDrawable generované z tej istej geometrie.

**D9 — Varianty podľa platformy:** web/Windows/Linux/Android legacy = zaoblený štvorec ako master;
iOS, `apple-touch-icon`, PWA maskable a Android adaptívna ikona = pozadie cez celú plochu (OS si masku
robí sám; iOS ikony bez alfa kanála); macOS = mriežka Big Sur (dlaždica 824/1024, polomer 36/160 ≈ Apple 185/824).
Notifikačná a monochromatická ikona = plné biele stĺpce bez pozadia.

**D10 — Slovná značka** (`assets/psst-wordmark.svg`) má text „psst" ako geometrické ťahy (nie font), aby
nezávisela od písma; hrúbka ťahu 12 ladí so stĺpcami šírky 13.

## Podpisovanie

**D11 — Android release kľúč nikdy neopustí lokálny stroj.** Keystore je v `~/psst-keys` (mimo repa,
ignorovaný). CI stavia **nepodpísané** release APK/AAB a podpisujú sa lokálne skriptom
`scripts/android/sign-release.sh` (zipalign + apksigner, jarsigner pre AAB). Kľúč ani heslá sa nenahrávajú
do GitHub secrets — únik kľúča by znamenal stratu možnosti aktualizovať appku; lokálne podpisovanie je
jednoduchšia a bezpečnejšia hranica dôvery. Emulátorový test v CI používa jednorazový debug kľúč.
