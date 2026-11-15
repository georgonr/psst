# PSST iOS → TestFlight

Jednorazovo ručne (Apple to cez API nedovolí):

1. **App Group** — developer.apple.com → Certificates, IDs & Profiles → Identifiers → (filter App Groups) → **+** →
   App Groups → Description `psst`, Identifier `group.eu.macet.psst` → Register.
2. **Priradiť App Group** — Identifiers → `eu.macet.psst` → App Groups → **Configure** → zaškrtnúť
   `group.eu.macet.psst` → Continue → **Save**. To isté pre `eu.macet.psst.nse` a `eu.macet.psst.shareextension`.
   Pri `eu.macet.psst` (voliteľne) zaškrtnúť aj **Communication Notifications** (avatary v notifikáciách).
3. **Záznam appky** — appstoreconnect.apple.com → Apps → **+** → New App: iOS, názov `psst` (ak je obsadený
   `psst secure chat`, potom `psst by Macet`), jazyk Slovak, Bundle ID `eu.macet.psst`, SKU `eu.macet.psst`,
   User Access: Full Access.

Potom už len:

```sh
scripts/ios/release-testflight.sh
```

Skript overí appku a App Group, vygeneruje profily, nastaví GitHub secrets, spustí podpísaný build v CI s uploadom,
počká na spracovanie, pridá build do internej skupiny „psst" (tester Geo M) a uloží IPA do `dist/ios/`.
Kľúče ostávajú v `~/psst-keys` (API kľúč, distribučný certifikát `ios-dist/`), nikdy v repe.
