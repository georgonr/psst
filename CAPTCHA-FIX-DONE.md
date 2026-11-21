# psst — dávka 24: registrácia s hCaptcha opravená

Stav k 2026-11-21. Rozhodnutia: DECISIONS.md **D91**.

## Príčina
MAS 1.29.0 po úspešnom overení tokenu na api.hcaptcha.com porovná `hostname` z odpovede s doménou svojej stránky
**presnou zhodou** (`chat.psst.pro`). hCaptcha však vracia registrovateľnú doménu (`psst.pro`), aj keď je v
nastaveniach subdoména — známa chyba MAS **#3549** (otvorená; oprava PR #5376 nebola zlúčená, ani `main`, ani
1.30.0-rc.0 to nerieši). MAS chybu zahodí (`is_ok()`), preto v logoch nebola. Nastavenie domény v dashboarde
hCaptcha to nemohlo opraviť. Rovnaký problém bol príčinou, prečo v dávke 21 MAS odmietal aj testovacie kľúče.

Overené na serveri: DNS a HTTPS na api.hcaptcha.com fungujú (siteverify odpovedá), secret v MAS = `~/psst-keys`
(porovnané hashom), je platný (`invalid-input-response`, nie `invalid-input-secret`), site key = d49cfb64-…, MAS
posiela secret, response a remoteip skutočného klienta (z X-Forwarded-For), bez sitekey.

## Oprava
- Vlastný build MAS 1.29.0 s patchom `server/mas/psst-captcha-hostname.patch`:
  - hostname sa prijme, ak je to doména stránky alebo jej nadradená doména (`psst.pro` pre `chat.psst.pro`;
    holá TLD ani cudzia doména nie — unit test v CI),
  - hostname testovacích kľúčov („dummy-key-pass“) len pri oficiálnom testovacom sitekey,
  - dôvod zamietnutia CAPTCHA sa zapíše do logu (WARN) — doteraz sa zahadzoval.
- Binárka: CI `mas-build.yml` (oficiálny Dockerfile MAS), release `mas-1.29.0-psst1`, SHA-256 pripnutý v gite;
  obraz `psst-mas:1.29.0-psst1` = oficiálny obraz + táto binárka. Nasadené (`mas-cli v1.29.0-psst1`).
- Pred výmenou: záloha DB MAS `/opt/psst/server/backups/mas-pre-d91-20261120T1650Z.dump` (root, 600).

## Overenie
- Produkcia, testovacie kľúče na menej ako 1 minútu (07:07–07:08 UTC): registrácia **cez webový formulár v
  prehliadači** (app.psst.pro → Create account → meno, heslo, súhlas 18+, hCaptcha → zobrazované meno) →
  appka prihlásená; účet `qa-d91a` vznikol so súhlasom s podmienkami → deaktivovaný.
- **Ostré kľúče sú späť** — hash site key aj secret v configu MAS a v `secrets/mas/` = `~/psst-keys/hcaptcha.txt`;
  testové kľúče ani dočasná záloha configu nikde.
- Iné formuláre s CAPTCHA: MAS ju používa len pri registrácii; obnova hesla je vypnutá
  (`password_recovery_enabled: false`).
- Server smoke (CI) má nový test 1.3: celá registrácia s testovacími kľúčmi a zapnutou captcha.

## Neoverené
- Registrácia s **ostrým** tokenom od skutočného človeka po oprave — vyriešiť hCaptcha musí človek (automat
  dostal obrázkovú výzvu a CAPTCHA neobchádzam). Ak by zlyhala, MAS teraz zapíše presný dôvod do logu.

## Čo spraviť ty
1. Skús registráciu na iPhone / v prehliadači (https://app.psst.pro → Create account). Testovací účet potom zmaž
   (Nastavenia → Manage account → Delete account) alebo mi daj meno a deaktivujem ho.
2. V dashboarde hCaptcha môže ostať psst.pro v Domain allowlist (pokrýva chat.psst.pro).
