# PSST iOS → TestFlight

Jeden príkaz:

```sh
scripts/ios/release-testflight.sh            # všetko: kontrola → profily → secrets → podpísaný build v CI → TestFlight
scripts/ios/release-testflight.sh --check    # len kontrolný zoznam, nič nemení
```

Skript najprv vypíše kontrolný zoznam (API kľúč, bundle ID `eu.macet.psst`, `.nse`, `.shareextension` a ich
capabilities, distribučný certifikát, záznam appky, App Group). Čo API dovolí, **pridá** sám (chýbajúce bundle ID,
capabilities, nový distribučný certifikát z nášho CSR). Čo API nedovolí, vypíše ako presný návod pre Account Holdera
a skončí s kódom 3. Potom profily (náš ACTIVE profil sa použije znova, inak sa pridá nový „psst AppStore <id> <dátum>"),
šifrované GitHub secrets, číslo buildu = posledný TestFlight + 1 (D54), workflow *iOS release (signed)* (archív,
podpis, upload), čakanie na spracovanie, interná skupina „psst" (tester Geo M), exportná zhoda, URL zásad ochrany
súkromia a IPA do `dist/ios/` (len lokálne — stránka na stiahnutie ostáva pri iOS „Coming soon").

Tím `MHV67VMY8T` je zdieľaný: skript len **pridáva** objekty „psst …"; nič existujúce nemení, neodvoláva ani nemaže
(ani staršie psst profily — tie len vypršia). Kľúče ostávajú v `~/psst-keys` (API kľúč `AuthKey_U4SWSW9CRM.p8`,
`ios-dist/`), do GitHubu idú len ako šifrované secrets, nikdy do repa.

## Čo musí raz urobiť Account Holder (stav 16. 11. 2026)

Hotové: bundle ID ×3 s capabilities, App Group `group.eu.macet.psst` priradená ku všetkým trom (overené profilmi
z 16. 11.), distribučný certifikát `K2778R2L24` (do 14. 11. 2027).

Chýba len:

1. **Záznam appky** — appstoreconnect.apple.com → Apps → **+** → New App: iOS, názov `psst` (ak je obsadený
   `psst secure chat`), jazyk Slovak, Bundle ID `eu.macet.psst`, SKU `eu.macet.psst`, User Access: Full Access
   → Create. (Môže aj Admin / App Manager s právom „Create apps".)
2. Ak developer.apple.com alebo App Store Connect ukazuje banner s novou licenčnou zmluvou (Program License
   Agreement), prijať ju — inak Apple odmietne vytváranie profilov aj upload.

Potom už len `scripts/ios/release-testflight.sh`.
