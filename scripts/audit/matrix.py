#!/usr/bin/env python3
"""PSST: build docs/FEATURE-MATRIX.md from the audit results.

  scripts/audit/matrix.py <out.md> web=<web-result.json> windows=<...> macos=<...> android=<...> ios=<...>

Each result file is a JSON list of {"id", "status", "note"} (status: ok | fail | upstream | na), as written by
web-audit.mjs / desktop-audit.mjs, or by hand for Android (emulator) and iOS (simulator; from ios-result.txt).
The last result for an id wins, so a re-test appended later replaces the first one.
"""
import json
import sys
from datetime import date

ROWS = [
    ("Účet a prihlásenie", [
        ("register", "Registrácia pozývacím tokenom"),
        ("login", "Prihlásenie (MAS)"),
        ("logout", "Odhlásenie"),
        ("qr_login", "QR prihlásenie nového zariadenia"),
        ("verify_emoji", "Overenie zariadenia — emoji"),
        ("verify_qr", "Overenie zariadenia — QR"),
        ("verify_unverified_state", "Neoverené zariadenie je zablokované, kým sa neoverí"),
        ("recovery", "Obnovovací kľúč a záloha kľúčov"),
        ("key_backup_restore", "Prihlásenie s obnovovacím kľúčom → obnovená história"),
        ("history_new_device", "História na novom (overenom) zariadení"),
        ("password", "Zmena hesla"),
        ("sessions", "Správa relácií"),
    ]),
    ("Správy a miestnosti", [
        ("dm", "1:1 správy (šifrované)"),
        ("group", "Skupiny (šifrované, 3 členovia)"),
        ("public", "Verejné kanály (adresár, pripojenie)"),
        ("invite", "Pozvánky do miestností"),
        ("file", "Súbory"),
        ("image", "Obrázky"),
        ("video", "Video"),
        ("voice", "Hlasové správy"),
        ("reply", "Odpovede"),
        ("reaction", "Reakcie"),
        ("edit", "Úprava správ"),
        ("delete", "Mazanie správ"),
        ("mention", "Zmienky"),
        ("search", "Vyhľadávanie v šifrovaných miestnostiach"),
        ("search_public", "Vyhľadávanie v nešifrovanom kanáli"),
        ("receipts", "Potvrdenia o prečítaní"),
        ("typing", "Indikátor písania"),
    ]),
    ("Notifikácie", [
        ("notif_open", "Appka otvorená (iná miestnosť)"),
        ("notif_background", "Appka na pozadí / minimalizovaná"),
        ("notif_closed", "Appka zatvorená"),
        ("notif_lock", "Zamknutá obrazovka"),
    ]),
    ("Hovory", [
        ("call_voice", "1:1 hlasový hovor"),
        ("call_video", "1:1 video hovor"),
        ("call_group", "Skupinový hovor"),
        ("screenshare", "Zdieľanie obrazovky"),
        ("call_udp_blocked", "Hovor zo siete s blokovaným UDP"),
    ]),
    ("Profil a správa", [
        ("profile", "Zmena profilu a avatara"),
        ("block", "Blokovanie používateľa"),
        ("leave", "Opustenie miestnosti"),
        ("members", "Správa členov a práv"),
        ("admin", "Admin stránka (app.macet.eu/admin)"),
        ("download_page", "Stránka na stiahnutie"),
        ("update_check", "Kontrola novej verzie"),
    ]),
    ("Upozornenia, overenie a inštalácia (dávky 12–13)", [
        ("alerts_settings", "Nastavenia → Upozornenia a hovory (prepínače so skutočným stavom, test upozornenia a zvonenia)"),
        ("setup_after_update", "Chýbajúce povolenia sa vyžiadajú po inštalácii aj po aktualizácii"),
        ("wake_screen", "Rozsvietenie obrazovky pri novej správe"),
        ("notif_diag", "Diagnostika upozornení (export do súboru)"),
        ("verify_wakeup", "Upozornenie na žiadosť o overenie (appka zatvorená)"),
        ("verify_other_device", "Overenie „Použiť iné zariadenie“: výzva, odpočet, Poslať znova"),
        ("admin_password", "Admin: nastaviť nové heslo členovi"),
        ("install_clean", "Stiahnutý build sa nainštaluje a otvorí bez varovania"),
    ]),
    # Android-only section: the other platforms show "–" and are not counted
    ("Android: vyhľadávanie v správach (dávka 14, D80)", [
        ("search_global", "Hľadanie vo všetkých konverzáciách (hlavná obrazovka → Hľadať → Správy)"),
        ("search_room", "Hľadanie v jednej konverzácii (lupa v konverzácii / Detail → Hľadať v správach)"),
        ("search_types", "Šifrovaná 1:1, šifrovaná skupina aj nešifrovaný verejný kanál"),
        ("search_result", "Výsledok: odosielateľ, miestnosť, dátum, úryvok so zvýraznením; ťuknutie otvorí správu"),
        ("search_folding", "Bez ohľadu na veľkosť písmen a diakritiku („cislo“ → „číslo“), aj začiatok slova"),
        ("search_history", "Staršie správy: index sa dopĺňa z histórie na pozadí, stav indexovania viditeľný"),
        ("search_live", "Nová prijatá aj odoslaná správa hneď v indexe; úprava a zmazanie sa prejavia"),
        ("search_privacy", "Index šifrovaný v telefóne, nič na server, zmazaný pri odhlásení"),
        ("search_speed", "Rýchlosť hľadania a indexovania, záťaž"),
        ("search_lifecycle", "Po reštarte appky, po aktualizácii zo staršieho buildu, po odhlásení a novom prihlásení"),
    ], ("android",)),
]
PLATFORMS = [("web", "Web"), ("windows", "Windows"), ("macos", "macOS"), ("android", "Android"), ("ios", "iOS")]
LABEL = {"ok": "✅ funguje", "fail": "❌ nefunguje", "upstream": "🟠 nefunguje — upstream", "na": "⚪ nedá sa tu overiť"}


def load(path):
    data = json.load(open(path))
    out = {}
    for r in data:
        out[r["id"]] = r
    return out


def main():
    out_md = sys.argv[1]
    res = {}
    for arg in sys.argv[2:]:
        k, v = arg.split("=", 1)
        res[k] = load(v)
    counts = {s: 0 for s in LABEL}
    lines = []
    for section, rows, *only in ROWS:
        only = only[0] if only else None
        lines.append(f"\n## {section}\n")
        lines.append("| Funkcia | " + " | ".join(n for _, n in PLATFORMS) + " |")
        lines.append("|---|" + "---|" * len(PLATFORMS))
        for rid, name in rows:
            cells = []
            for p, _ in PLATFORMS:
                if only and p not in only:
                    cells.append("–")
                    continue
                r = res.get(p, {}).get(rid)
                if r is None:
                    cells.append("⚪ nedá sa tu overiť — netestované")
                    counts["na"] += 1
                    continue
                counts[r["status"]] += 1
                note = r["note"].replace("|", "/").replace("\n", " ")
                cells.append(f"{LABEL[r['status']]} — {note}")
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
    total = sum(counts.values())
    head = [
        "# PSST — matica funkcií",
        "",
        f"Stav k {date.today().isoformat()}, testované na produkčnom serveri chat.macet.eu výhradne na testovacích účtoch "
        "(po teste deaktivované). Postup a skripty: `scripts/audit/` (DECISIONS D64), podrobnosti v REPORT.md.",
        "",
        "- **Web**: Element Web app.macet.eu v Chromiu (Playwright), partner = ďalšia webová relácia.",
        "- **Windows / macOS**: nainštalované MSI / DMG na GitHub runneroch (windows-latest, macos-latest), riadené cez CDP.",
        "- **Android**: APK v emulátore (API 34, Google APIs = Google Play services, FCM), ovládané cez adb/uiautomator.",
        "- **iOS**: simulátor na GitHub runneri (XCUITest `PsstAuditTests`), nepodpísaný build — bez APNs, kamery a mikrofónu.",
        "",
        f"**Súhrn ({total} buniek):** ✅ {counts['ok']} funguje · ❌ {counts['fail']} nefunguje · "
        f"🟠 {counts['upstream']} nefunguje kvôli upstreamu · ⚪ {counts['na']} nedá sa tu overiť",
        "",
        "Legenda: ✅ funguje (skutočne otestované) · ❌ nefunguje · 🟠 nefunguje, obmedzenie upstreamu (nie náš fork/server) · "
        "⚪ nedá sa v tomto prostredí overiť (dôvod v bunke) · – riadok sa týka len inej platformy (nepočíta sa).",
    ]
    open(out_md, "w").write("\n".join(head + lines) + "\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
