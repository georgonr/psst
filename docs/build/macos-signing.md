# macOS: podpis Developer ID + notarizácia (D69)

**Stav 2026-11-16:** DMG z https://app.macet.eu/download nie je podpísaný ani notarizovaný → Gatekeeper ho pri
stiahnutí z webu blokuje („Presunúť do koša“). Stránka na stiahnutie preto pri macOS ukazuje slovenský návod
(Systémové nastavenia → Súkromie a bezpečnosť → *Napriek tomu otvoriť*). Návod zmizne sám pri prvom podpísanom builde.

## Prečo to nejde automaticky

Certifikát *Developer ID Application* (ani G2, ani starý typ) cez App Store Connect API kľúč vytvoriť nejde:

```
POST /v1/certificates  {"certificateType": "DEVELOPER_ID_APPLICATION_G2", "csrContent": …}
403 FORBIDDEN_ERROR  "This request is forbidden for security reasons"
                     "This operation can only be performed by the Account Holder."
```

(rovnako pre `DEVELOPER_ID_APPLICATION`; kľúč U4SWSW9CRM, tím GexPay SE MHV67VMY8T). Žiadna rola API kľúča
ani používateľa to nezmení — Developer ID certifikát vytvára len **Account Holder** tímu. V tíme zatiaľ nie je
žiadny Developer ID certifikát (GET /v1/certificates, filter DEVELOPER_ID_APPLICATION[_G2] → 0).
**Notarizácia** tým istým API kľúčom funguje (`xcrun notarytool history --key … --key-id U4SWSW9CRM --issuer …` → OK).

## Čo urobí Account Holder (GexPay SE) — cca 3 minúty

Súkromný kľúč je pripravený u nás a z Macu nikam neodchádza; Account Holder potrebuje len súbor **`devid.csr`**
(žiadosť o certifikát, nie je tajná) z `~/psst-keys/macos-devid/devid.csr`.

1. Prihlásiť sa na https://developer.apple.com/account ako Account Holder tímu **GexPay SE (MHV67VMY8T)**.
   Ak sa hore zobrazí žltý pruh *„… agreement has been updated / Review Agreement“*, najprv ho otvoriť a súhlasiť
   (bez platnej Apple Developer Program License Agreement nejde vytvoriť certifikát ani notarizovať).
2. **Certificates, Identifiers & Profiles → Certificates → „+“** (https://developer.apple.com/account/resources/certificates/add).
3. V časti *Software* zvoliť **Developer ID** → Continue → **Developer ID Application** → profil **G2 Sub-CA
   (Xcode 11.4.1 or later)** → Continue.
4. *Choose File* → `devid.csr` → Continue → **Download**. Stiahne sa `developerID_application.cer`.
5. Súbor `developerID_application.cer` poslať späť (je verejný, môže ísť e-mailom/chatom).

Nič iné v tíme sa nemení (žiadne existujúce certifikáty, profily ani aplikácie).

*Alternatíva:* Account Holder vytvorí certifikát vlastným CSR z Keychain Access, exportuje ho ako `.p12` s heslom
a pošle `.p12` a heslo **oddelene** (iným kanálom).

## Čo potom urobíme my (1 príkaz)

```sh
scripts/desktop/macos-devid-secrets.sh ~/Downloads/developerID_application.cer --run
# alebo pri .p12:  scripts/desktop/macos-devid-secrets.sh devid.p12 subor-s-heslom --run
```

Skript overí, že certifikát patrí ku kľúču `~/psst-keys/macos-devid/devid.key` a tímu MHV67VMY8T, zostaví
`devid.p12` (s Apple medziľahlým CA, náhodné heslo, oboje v `~/psst-keys/macos-devid/`, chmod 600), overí import
do kľúčenky a nastaví **šifrované** GitHub secrets `PSST_MAC_CERT_P12_BASE64` + `PSST_MAC_CERT_PASSWORD`
(účet georgonr). Notarizácia používa existujúce `APP_STORE_CONNECT_API_KEY_BASE64`, `APP_STORE_CONNECT_API_KEY_ID`,
`APP_STORE_CONNECT_ISSUER_ID`, `APPLE_TEAM_ID`. `--run` spustí Web + Desktop. Do repa sa nič nezapisuje.

## Čo robí CI (`web-desktop.yml`)

- **Desktop macOS (universal)**: bez secretu `PSST_MAC_CERT_P12_BASE64` build nepodpísaný (warning, nie chyba).
  So secretom: electron-builder podpíše `psst.app` (hardened runtime, `build/entitlements.mac.plist`: JIT, kamera,
  mikrofón, vypnutá library validation), notarizuje ho API kľúčom a priloží (staple) lístok; potom sa podpíše aj DMG,
  notarizuje cez `xcrun notarytool submit --wait` a `stapler staple`. Overenie v jobe: `codesign --verify --deep
  --strict`, `spctl -a -t exec` (app), `spctl -a -t open --context context:primary-signature` (DMG), `stapler validate`.
- **Publish to app.macet.eu/download**: nahrá DMG ako doteraz; pri podpísanom builde navyše
  `ssh psst-dl@… signed macos <build> <sha256>` → `latest.json` dostane `"signed": true` a stránka už nezobrazuje
  návod pre nepodpísanú appku. Každý nový upload bez tohto kroku návod vráti.
- **Gatekeeper check of the published DMG** (`macos-gatekeeper.yml`, aj ručne): na macos-15 stiahne DMG z
  https://app.macet.eu/download cez HTTPS, nastaví `com.apple.quarantine` ako prehliadač a spustí
  `spctl -a -vvv -t install` + `-t open --context context:primary-signature` (DMG), `spctl -a -vvv -t exec` +
  `codesign --verify --deep --strict` (app v DMG), `xcrun stapler validate` (DMG aj app). Pri podpísanom builde
  musí všetko prejsť, inak len zapíše výsledok.
