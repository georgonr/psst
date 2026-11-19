"""psst — právne stránky na psst.pro (DECISIONS D87): /privacy, /terms, /delete-account, slovensky aj anglicky.

Obsah sa riadi play-listing/FACTS.md (overené fakty z buildu a servera). Pravidlá: nič nesľubovať, čo nie je
pravda (žiadna anonymita), prevádzkovateľ a kontakt len podľa OPERATOR (bez ulice, telefónu a mena osoby).
Generuje ich server/www/build.py.
"""

OPERATOR = {
    "name": "MACET, s.r.o.",
    "id_sk": "IČO 35953781",
    "id_en": "Company ID (IČO) 35953781",
    "country_sk": "Slovenská republika",
    "country_en": "Slovak Republic",
    "email": "psst@psst.pro",
}
EFFECTIVE = {"sk": "19. 11. 2026", "en": "19 November 2026"}
HOSTING = {"sk": "Hetzner Online GmbH, dátové centrum Helsinki, Fínsko (EÚ)",
           "en": "Hetzner Online GmbH, data centre in Helsinki, Finland (EU)"}

MAIL = f'<a href="mailto:{OPERATOR["email"]}">{OPERATOR["email"]}</a>'
OP_SK = f'{OPERATOR["name"]}, {OPERATOR["id_sk"]}, {OPERATOR["country_sk"]}'
OP_EN = f'{OPERATOR["name"]}, {OPERATOR["id_en"]}, {OPERATOR["country_en"]}'
ACCOUNT = "https://chat.psst.pro/auth/account/"

PAGES = {
    # ------------------------------------------------------------------------------------------------ privacy
    "privacy": {
        "sk": {
            "title": "Zásady ochrany súkromia",
            "desc": "Aké údaje služba psst spracúva, čo je šifrované medzi zariadeniami, čo vidí server, ako dlho údaje uchovávame a aké máte práva.",
            "body": f"""
<p class="meta">Platné od {EFFECTIVE["sk"]} · služba psst (aplikácie pre Android, iPhone, Windows, macOS a web)</p>

<h2 id="sk-operator">1. Kto údaje spracúva</h2>
<p>Prevádzkovateľ: <strong>{OP_SK}</strong>. Kontakt pre všetky otázky o súkromí a vaše žiadosti: {MAIL}.</p>

<h2 id="sk-short">2. Stručne</h2>
<ul>
<li>Priame správy a súkromné skupiny sú <strong>šifrované medzi zariadeniami</strong> (end-to-end). Ich obsah server nevidí.</li>
<li>Server <strong>vidí metadáta</strong>: kto ste, v ktorých miestnostiach ste, s kým a kedy komunikujete a z akej IP adresy. psst <strong>nie je anonymná služba</strong>.</li>
<li>Všetko beží na <strong>vlastnom serveri v EÚ</strong>. Tretie strany dostávajú len technické údaje na doručenie upozornení (Google, Apple), nikdy obsah správ.</li>
<li>Žiadna reklama, analytika, sledovanie ani hlásenia o pádoch. Údaje nepredávame.</li>
<li>Služba je <strong>len na pozvánku</strong> a určená <strong>osobám od 18 rokov</strong>.</li>
</ul>

<h2 id="sk-e2ee">3. Čo je šifrované medzi zariadeniami a čo vidí server</h2>
<p><strong>Šifrované end-to-end</strong> (kľúče majú len zariadenia účastníkov): text správ, odpovede a úpravy, súbory, obrázky, videá a hlasové správy v priamych správach a súkromných skupinách. Hovory v týchto miestnostiach sú tiež šifrované medzi zariadeniami. Ak si zapnete zálohu kľúčov, server uloží kľúče zašifrované vaším kľúčom na obnovenie, ktorý server nepozná.</p>
<p><strong>Nie je šifrované end-to-end</strong> a server to vidí:</p>
<ul>
<li>obsah <strong>verejných kanálov</strong> (kanály sú predvolene nešifrované, aby noví členovia videli históriu; tvorca môže šifrovanie zapnúť);</li>
<li>názov, téma a obrázok miestnosti, zoznam členov, pozvánky, vstupy a odchody, oprávnenia;</li>
<li>vaše zobrazované meno a profilový obrázok;</li>
<li>kto poslal udalosť do ktorej miestnosti a kedy, veľkosť šifrovaných správ a súborov, potvrdenia o prečítaní, indikátor písania a <strong>reakcie</strong> (emoji pri správe);</li>
<li>IP adresa a typ zariadenia pri pripojení.</li>
</ul>
<p>Všetka komunikácia so serverom je navyše šifrovaná pri prenose (TLS).</p>

<h2 id="sk-data">4. Aké údaje spracúvame a prečo</h2>
<ul>
<li><strong>Účet:</strong> používateľské meno, zobrazované meno, profilový obrázok (ak ho nastavíte), heslo len ako bezpečný hash, e-mail len ak ho sami pridáte, zoznam vašich zariadení a prihlásení. Účel: poskytovanie služby.</li>
<li><strong>Obsah:</strong> správy a súbory, ktoré pošlete (v šifrovaných miestnostiach len v zašifrovanej podobe). Účel: doručenie ostatným účastníkom.</li>
<li><strong>Technické údaje:</strong> IP adresa, typ zariadenia a čas posledného pripojenia k zariadeniu, technické záznamy servera. Účel: prevádzka a bezpečnosť služby, ochrana pred zneužitím.</li>
<li><strong>Hovory:</strong> server hovorov (LiveKit) vidí, kto a kedy sa pripojil k hovoru a z akej IP adresy.</li>
<li><strong>Nahlásenia:</strong> ak nahlásite správu alebo miestnosť (alebo používateľa), uložíme kto, čo, kedy a dôvod, ktorý napíšete. Správca nevidí obsah šifrovaných správ, len to, čo do nahlásenia sami napíšete.</li>
<li><strong>Upozornenia (push):</strong> identifikátor zariadenia na doručovanie upozornení (push token), pozri bod 5.</li>
</ul>
<p>Nespracúvame kontakty z telefónu, polohu, reklamný identifikátor ani údaje o používaní aplikácie.</p>
<p><strong>Právny základ:</strong> plnenie zmluvy, teda poskytovanie služby, o ktorú ste požiadali registráciou (čl. 6 ods. 1 písm. b GDPR); pri technických záznamoch a riešení nahlásení oprávnený záujem na bezpečnosti služby (čl. 6 ods. 1 písm. f GDPR); a plnenie zákonných povinností (čl. 6 ods. 1 písm. c GDPR).</p>

<h2 id="sk-where">5. Kde sú údaje a kto ich ešte dostane</h2>
<p>Údaje sú na serveri prevádzkovateľa: {HOSTING["sk"]}. Hetzner prevádzkuje hardvér ako sprostredkovateľ a k obsahu nemá prístup.</p>
<p><strong>Upozornenia:</strong> náš server posiela doručovacej službe len <strong>identifikátor udalosti a miestnosti a počet neprečítaných</strong>, nikdy text ani odosielateľa. Aplikácia si správu potom stiahne z nášho servera a dešifruje ju v zariadení. Na Androide upozornenia doručuje <strong>Google (Firebase Cloud Messaging)</strong>, na iPhone <strong>Apple (Apple Push Notification service)</strong>. Tieto firmy tak vidia push token vášho zariadenia, čas upozornenia a spomenuté identifikátory a môžu ich spracúvať aj mimo EÚ podľa vlastných zmluvných záruk. Iné služby Google ani Apple (analytiku, hlásenia o pádoch) aplikácia nepoužíva.</p>
<p>Inak údaje tretím stranám neposkytujeme, okrem prípadov, keď to vyžaduje zákon.</p>

<h2 id="sk-retention">6. Ako dlho údaje uchovávame</h2>
<ul>
<li><strong>Účet</strong> do jeho zmazania.</li>
<li><strong>Správy a súbory</strong>, kým ich nevymažete alebo kým existuje miestnosť. Správy, ktoré už dostali iní, ostávajú v ich konverzáciách.</li>
<li><strong>IP adresa a typ zariadenia</strong> pri každom zariadení najviac 28 dní. Technické záznamy servera majú obmedzenú veľkosť a priebežne sa prepisujú.</li>
<li><strong>Nahlásenia</strong> a záznam o ich vybavení, kým sú potrebné na ochranu služby.</li>
<li><strong>Zálohy:</strong> server sa denne zálohuje. Zálohy sú šifrované (AES-256), uložené u toho istého poskytovateľa v EÚ a postupne sa mažú: denné po 7 dňoch, týždenné po 4 týždňoch, mesačné po 6 mesiacoch. Zmazané údaje preto zo záloh zmiznú najneskôr <strong>do 6 mesiacov</strong>. Zálohy používame len na obnovu služby po poruche.</li>
</ul>

<h2 id="sk-delete">7. Zmazanie účtu</h2>
<p>Účet zmažete sami v aplikácii alebo na webe, alebo o to požiadate e-mailom na {MAIL} bez prihlásenia. Postup a čo sa zmaže: <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2 id="sk-rights">8. Vaše práva</h2>
<p>Podľa GDPR máte právo na prístup k údajom, ich opravu, vymazanie, obmedzenie spracúvania, prenosnosť a právo namietať. Uplatníte ich e-mailom na {MAIL}. Aby sme údaje nevydali niekomu inému, môžeme vás požiadať o overenie, že účet je váš (napríklad potvrdením v aplikácii). Odpovieme bez zbytočného odkladu, najneskôr do jedného mesiaca. Máte tiež právo podať sťažnosť dozornému orgánu, na Slovensku Úradu na ochranu osobných údajov SR (<a href="https://dataprotection.gov.sk">dataprotection.gov.sk</a>).</p>

<h2 id="sk-age">9. Vek a prístup</h2>
<p>psst je určený osobám od 18 rokov. Účet si môže vytvoriť len ten, kto dostal pozvánku. Ak zistíme, že účet patrí mladšej osobe, zrušíme ho.</p>

<h2 id="sk-cookies">10. Cookies a úložisko v prehliadači</h2>
<p>Webová aplikácia ukladá prihlásenie a šifrovacie kľúče v úložisku prehliadača a prihlasovacia stránka používa nevyhnutný cookie relácie. Reklamné ani analytické cookies nepoužívame. Táto stránka si v prehliadači pamätá len zvolený jazyk.</p>

<h2 id="sk-changes">11. Zmeny</h2>
<p>O podstatných zmenách týchto zásad vás vopred upozorníme v aplikácii alebo na tejto stránke.</p>
""",
        },
        "en": {
            "title": "Privacy Policy",
            "desc": "What data the psst service processes, what is end-to-end encrypted, what the server sees, how long we keep data and what your rights are.",
            "body": f"""
<p class="meta">Effective {EFFECTIVE["en"]} · psst service (apps for Android, iPhone, Windows, macOS and the web)</p>

<h2 id="en-operator">1. Who processes the data</h2>
<p>Operator (controller): <strong>{OP_EN}</strong>. Contact for all privacy questions and requests: {MAIL}.</p>

<h2 id="en-short">2. In short</h2>
<ul>
<li>Direct messages and private groups are <strong>end-to-end encrypted</strong>. The server cannot see their content.</li>
<li>The server <strong>does see metadata</strong>: who you are, which rooms you are in, with whom and when you communicate, and from which IP address. psst is <strong>not an anonymous service</strong>.</li>
<li>Everything runs on <strong>our own server in the EU</strong>. Third parties only receive technical data needed to deliver notifications (Google, Apple), never message content.</li>
<li>No ads, analytics, tracking or crash reporting. We do not sell data.</li>
<li>The service is <strong>invitation only</strong> and intended for <strong>people aged 18 and over</strong>.</li>
</ul>

<h2 id="en-e2ee">3. What is end-to-end encrypted and what the server sees</h2>
<p><strong>End-to-end encrypted</strong> (only the participants' devices hold the keys): message text, replies and edits, files, images, videos and voice messages in direct messages and private groups. Calls in these rooms are end-to-end encrypted as well. If you turn on key backup, the server stores your keys encrypted with your recovery key, which the server does not know.</p>
<p><strong>Not end-to-end encrypted</strong>, visible to the server:</p>
<ul>
<li>the content of <strong>public channels</strong> (channels are unencrypted by default so new members can read the history; the creator can turn encryption on);</li>
<li>room name, topic and avatar, member list, invites, joins and leaves, permissions;</li>
<li>your display name and avatar;</li>
<li>who sent an event to which room and when, the size of encrypted messages and files, read receipts, typing indicators and <strong>reactions</strong> (emoji on a message);</li>
<li>your IP address and device type when you connect.</li>
</ul>
<p>All communication with the server is additionally encrypted in transit (TLS).</p>

<h2 id="en-data">4. What data we process and why</h2>
<ul>
<li><strong>Account:</strong> username, display name, avatar (if you set one), password only as a secure hash, e-mail only if you add one, your devices and sessions. Purpose: providing the service.</li>
<li><strong>Content:</strong> messages and files you send (in encrypted rooms only in encrypted form). Purpose: delivering them to the other participants.</li>
<li><strong>Technical data:</strong> IP address, device type and last-seen time per device, server logs. Purpose: operating and securing the service, preventing abuse.</li>
<li><strong>Calls:</strong> the call server (LiveKit) sees who joined a call, when, and from which IP address.</li>
<li><strong>Reports:</strong> if you report a message or room (or a user), we store who reported what, when, and the reason you write. The administrator cannot see the content of encrypted messages, only what you write in the report.</li>
<li><strong>Push notifications:</strong> a device identifier for delivering notifications (push token), see section 5.</li>
</ul>
<p>We do not process your phone contacts, location, advertising ID or app usage data.</p>
<p><strong>Legal basis:</strong> performance of a contract, i.e. providing the service you requested by registering (Art. 6(1)(b) GDPR); for technical logs and handling reports, our legitimate interest in keeping the service secure (Art. 6(1)(f) GDPR); and compliance with legal obligations (Art. 6(1)(c) GDPR).</p>

<h2 id="en-where">5. Where the data is and who else receives it</h2>
<p>The data is stored on the operator's server: {HOSTING["en"]}. Hetzner operates the hardware as a processor and has no access to the content.</p>
<p><strong>Notifications:</strong> our server sends the delivery service only the <strong>event and room identifiers and the unread count</strong>, never the text or the sender. The app then fetches the message from our server and decrypts it on the device. On Android, notifications are delivered by <strong>Google (Firebase Cloud Messaging)</strong>, on iPhone by <strong>Apple (Apple Push Notification service)</strong>. These companies therefore see your device's push token, the time of the notification and those identifiers, and may process them outside the EU under their own contractual safeguards. The app uses no other Google or Apple services (no analytics, no crash reporting).</p>
<p>We do not share data with any other third party, except where required by law.</p>

<h2 id="en-retention">6. How long we keep data</h2>
<ul>
<li><strong>Account:</strong> until you delete it.</li>
<li><strong>Messages and files:</strong> until you delete them or the room is removed. Messages already delivered to others stay in their conversations.</li>
<li><strong>IP address and device type:</strong> at most 28 days per device. Server logs are size-limited and continuously overwritten.</li>
<li><strong>Reports</strong> and the record of how they were handled: as long as needed to protect the service.</li>
<li><strong>Backups:</strong> the server is backed up daily. Backups are encrypted (AES-256), stored with the same provider in the EU and deleted on a rolling basis: daily backups after 7 days, weekly after 4 weeks, monthly after 6 months. Deleted data therefore disappears from backups <strong>within 6 months</strong> at the latest. Backups are used only to restore the service after a failure.</li>
</ul>

<h2 id="en-delete">7. Deleting your account</h2>
<p>You can delete your account yourself in the app or on the web, or ask us by e-mail at {MAIL} without signing in. Steps and what gets deleted: <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2 id="en-rights">8. Your rights</h2>
<p>Under the GDPR you have the right of access, rectification, erasure, restriction of processing, data portability and the right to object. To exercise them, e-mail {MAIL}. So that we do not hand your data to someone else, we may ask you to confirm that the account is yours (for example in the app). We reply without undue delay and within one month at the latest. You also have the right to lodge a complaint with a supervisory authority; in Slovakia this is the Office for Personal Data Protection (<a href="https://dataprotection.gov.sk">dataprotection.gov.sk</a>).</p>

<h2 id="en-age">9. Age and access</h2>
<p>psst is intended for people aged 18 and over. Only people who received an invitation can create an account. If we learn that an account belongs to a younger person, we close it.</p>

<h2 id="en-cookies">10. Cookies and browser storage</h2>
<p>The web app keeps your sign-in and encryption keys in your browser's storage, and the sign-in page uses a strictly necessary session cookie. We use no advertising or analytics cookies. This website only remembers your chosen language in your browser.</p>

<h2 id="en-changes">11. Changes</h2>
<p>We will announce material changes to this policy in advance in the app or on this page.</p>
""",
        },
    },
    # ------------------------------------------------------------------------------------------------ terms
    "terms": {
        "sk": {
            "title": "Podmienky používania",
            "desc": "Podmienky používania komunikačnej služby psst.",
            "body": f"""
<p class="meta">Platné od {EFFECTIVE["sk"]} · prevádzkovateľ: {OP_SK} · kontakt: {MAIL}</p>

<h2>1. Služba</h2>
<p>psst je komunikačná služba na správy, skupiny, kanály, súbory a hlasové a video hovory, postavená na otvorenom protokole Matrix a prevádzkovaná na vlastnom serveri prevádzkovateľa. Server nie je prepojený s inými Matrix servermi. Služba je bezplatná.</p>

<h2>2. Kto ju môže používať</h2>
<ul>
<li>Účet si môže vytvoriť len ten, kto dostal <strong>pozvánku</strong>. Pozvánka je určená jednej osobe, neposúvajte ju ďalej.</li>
<li>Služba je určená <strong>osobám od 18 rokov</strong>.</li>
<li>Za svoj účet, heslo a kľúč na obnovenie šifrovania zodpovedáte vy. Prevádzkovateľ nevie obnoviť šifrované správy.</li>
</ul>

<h2>3. Pravidlá: nulová tolerancia</h2>
<p>Na neprijateľný obsah a zneužívanie platí <strong>nulová tolerancia</strong>. Je zakázané najmä:</p>
<ul>
<li>šíriť materiály zobrazujúce sexuálne zneužívanie detí alebo akýkoľvek obsah, ktorý ohrozuje deti;</li>
<li>vyhrážať sa, obťažovať, šikanovať, šíriť nenávisť alebo podnecovať k násiliu;</li>
<li>podvádzať, vydávať sa za iného, šíriť spam alebo škodlivý softvér;</li>
<li>šíriť obsah, ktorý porušuje zákon, autorské práva alebo súkromie iných;</li>
<li>útočiť na server alebo iných používateľov.</li>
</ul>

<h2>4. Nahlásenie a blokovanie</h2>
<p>Každú správu aj miestnosť môžete v aplikácii <strong>nahlásiť</strong> prevádzkovateľovi a každého používateľa <strong>zablokovať</strong>, takže jeho správy už neuvidíte. Používateľa nahlásite nahlásením jeho správy alebo e-mailom na {MAIL}. Nahlásenia preveríme spravidla <strong>do 24 hodín</strong>. Keďže obsah šifrovaných miestností je šifrovaný, prevádzkovateľ ho bežne nevidí a koná podľa nahlásení a metadát.</p>

<h2>5. Zásahy prevádzkovateľa</h2>
<p>Prevádzkovateľ môže nahlásený obsah odstrániť a zablokovať alebo zrušiť účet, ktorý porušuje tieto podmienky alebo ohrozuje službu, a odstrániť miestnosť. Pri závažnej trestnej činnosti môže informovať orgány činné v trestnom konaní.</p>

<h2>6. Zrušenie účtu</h2>
<p>Účet môžete kedykoľvek zmazať v aplikácii, na webe alebo e-mailom, postup je na <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2>7. Dostupnosť a zodpovednosť</h2>
<p>Služba sa poskytuje „tak, ako je“, bez záruky nepretržitej dostupnosti. Server sa denne zálohuje, napriek tomu môže dôjsť k výpadku alebo strate údajov. Prevádzkovateľ nezodpovedá za obsah, ktorý si používatelia posielajú. Tým nie sú dotknuté práva, ktoré vám nemožno zmluvne obmedziť.</p>

<h2>8. Súkromie</h2>
<p>Aké údaje spracúvame, popisujú <a href="/privacy">Zásady ochrany súkromia</a>.</p>

<h2>9. Softvér</h2>
<p>Aplikácie psst sú upravené verzie open-source klientov Element, šírené pod licenciou AGPL-3.0. Zdrojový kód: <a href="https://github.com/georgonr/psst">github.com/georgonr/psst</a>.</p>

<h2>10. Zmeny a rozhodné právo</h2>
<p>Podmienky sa môžu zmeniť, o podstatných zmenách vás vopred upozorníme. Platí právo Slovenskej republiky.</p>
""",
        },
        "en": {
            "title": "Terms of Use",
            "desc": "Terms of use of the psst messaging service.",
            "body": f"""
<p class="meta">Effective {EFFECTIVE["en"]} · operator: {OP_EN} · contact: {MAIL}</p>

<h2>1. The service</h2>
<p>psst is a messaging service for messages, groups, channels, files and voice and video calls, built on the open Matrix protocol and run on the operator's own server. The server is not connected to other Matrix servers. The service is free of charge.</p>

<h2>2. Who may use it</h2>
<ul>
<li>Only people who received an <strong>invitation</strong> can create an account. An invitation is meant for one person; do not pass it on.</li>
<li>The service is intended for <strong>people aged 18 and over</strong>.</li>
<li>You are responsible for your account, password and encryption recovery key. The operator cannot recover encrypted messages.</li>
</ul>

<h2>3. Rules: zero tolerance</h2>
<p>There is <strong>zero tolerance</strong> for objectionable content and abusive users. In particular, you must not:</p>
<ul>
<li>share child sexual abuse material or any content that endangers children;</li>
<li>threaten, harass or bully others, spread hate or incite violence;</li>
<li>commit fraud, impersonate others, send spam or malware;</li>
<li>share content that breaks the law or infringes copyright or other people's privacy;</li>
<li>attack the server or other users.</li>
</ul>

<h2>4. Reporting and blocking</h2>
<p>In the app you can <strong>report</strong> any message or room to the operator and <strong>block</strong> any user so you no longer see their messages. To report a user, report one of their messages or e-mail {MAIL}. We review reports, as a rule, <strong>within 24 hours</strong>. Because the content of encrypted rooms is encrypted, the operator normally cannot see it and acts on reports and metadata.</p>

<h2>5. Action by the operator</h2>
<p>The operator may remove reported content, suspend or close accounts that break these terms or endanger the service, and remove rooms. In cases of serious crime the operator may inform law enforcement.</p>

<h2>6. Closing your account</h2>
<p>You can delete your account at any time in the app, on the web or by e-mail; see <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2>7. Availability and liability</h2>
<p>The service is provided “as is”, without a guarantee of uninterrupted availability. The server is backed up daily, but outages or data loss may still occur. The operator is not responsible for content users send each other. This does not limit rights that cannot be limited by contract.</p>

<h2>8. Privacy</h2>
<p>What data we process is described in the <a href="/privacy">Privacy Policy</a>.</p>

<h2>9. Software</h2>
<p>The psst apps are modified versions of the open-source Element clients, distributed under the AGPL-3.0 licence. Source code: <a href="https://github.com/georgonr/psst">github.com/georgonr/psst</a>.</p>

<h2>10. Changes and governing law</h2>
<p>These terms may change; we will announce material changes in advance. The laws of the Slovak Republic apply.</p>
""",
        },
    },
    # ------------------------------------------------------------------------------------------------ delete account
    "delete-account": {
        "sk": {
            "title": "Zmazanie účtu psst",
            "desc": "Ako zmazať účet v aplikácii psst secure chat: v aplikácii, na webe alebo e-mailom bez prihlásenia.",
            "body": f"""
<p class="meta">Aplikácia <strong>psst secure chat</strong> · prevádzkovateľ {OPERATOR["name"]} · {MAIL}</p>

<p class="callout">Účet psst zmažete sami <strong>v aplikácii</strong> alebo <strong>na webe</strong>. Ak sa nemôžete prihlásiť, napíšte na <a href="mailto:{OPERATOR["email"]}?subject=Zmazanie%20%C3%BA%C4%8Dtu%20psst">{OPERATOR["email"]}</a>, prihlásenie nie je potrebné.</p>

<h2>V aplikácii (Android, iPhone)</h2>
<ol>
<li>Ťuknite na svoj profilový obrázok vľavo hore a otvorte <strong>Nastavenia</strong>.</li>
<li>Zvoľte <strong>Manage account &amp; devices</strong> (Android) alebo <strong>Manage account</strong> (iPhone). Tieto položky sú v aplikácii po anglicky.</li>
<li>Otvorí sa stránka účtu. Zvoľte <strong>Zmazať účet</strong> (Delete account) a potvrďte.</li>
</ol>

<h2>Na webe a v aplikácii pre počítač</h2>
<ol>
<li>Otvorte <a href="{ACCOUNT}">chat.psst.pro/auth/account</a> a prihláste sa (alebo v aplikácii: Nastavenia → Účet → Spravovať účet).</li>
<li>Zvoľte <strong>Zmazať účet</strong> (Delete account) a potvrďte.</li>
</ol>

<h2>E-mailom, bez prihlásenia</h2>
<p>Napíšte na {MAIL} s predmetom „Zmazanie účtu“ a uveďte svoje používateľské meno (napr. <code>@meno:psst.pro</code>). Aby účet nezmazal niekto cudzí, overíme, že je váš (napríklad potvrdením v aplikácii alebo z e-mailu, ktorý máte pri účte). Účet zmažeme do 30 dní a potvrdíme vám to.</p>

<h2>Čo sa zmaže</h2>
<ul>
<li>účet sa natrvalo zruší a nedá sa obnoviť ani sa doň znova prihlásiť;</li>
<li>zobrazované meno, profilový obrázok a e-mail;</li>
<li>všetky prihlásenia, zariadenia a ich šifrovacie kľúče, nastavenia upozornení a push tokeny;</li>
<li>členstvo vo všetkých miestnostiach a záznam v adresári členov;</li>
<li>vaše správy sa označia ako vymazané a noví členovia miestností ich už neuvidia.</li>
</ul>

<h2>Čo ostane a ako dlho</h2>
<ul>
<li><strong>Správy, ktoré už dostali iní</strong>, ostávajú v ich konverzáciách (v šifrovaných miestnostiach na serveri len v zašifrovanej podobe).</li>
<li><strong>Súbory, ktoré ste nahrali</strong>, ostávajú dostupné tým, s ktorými ste ich zdieľali. Ak chcete, aby sme ich zo servera odstránili, napíšte na {MAIL}; odstránime ich do 30 dní.</li>
<li><strong>Používateľské meno</strong> sa už nedá znova použiť, aby sa nikto nemohol vydávať za vás.</li>
<li><strong>Zálohy:</strong> údaje ostávajú v šifrovaných zálohách servera, kým sa zálohy nezmažú, najneskôr <strong>6 mesiacov</strong>.</li>
<li><strong>Nahlásenia</strong> a záznam o zásahoch správcu, kým sú potrebné na ochranu služby.</li>
</ul>
<p>Viac v <a href="/privacy">Zásadách ochrany súkromia</a>.</p>
""",
        },
        "en": {
            "title": "Delete your psst account",
            "desc": "How to delete your account in the psst secure chat app: in the app, on the web, or by e-mail without signing in.",
            "body": f"""
<p class="meta">App <strong>psst secure chat</strong> · operator {OPERATOR["name"]} · {MAIL}</p>

<p class="callout">You can delete your psst account yourself <strong>in the app</strong> or <strong>on the web</strong>. If you cannot sign in, e-mail <a href="mailto:{OPERATOR["email"]}?subject=Delete%20my%20psst%20account">{OPERATOR["email"]}</a>; no sign-in is needed.</p>

<h2>In the app (Android, iPhone)</h2>
<ol>
<li>Tap your avatar in the top left corner and open <strong>Settings</strong>.</li>
<li>Choose <strong>Manage account &amp; devices</strong> (Android) or <strong>Manage account</strong> (iPhone).</li>
<li>Your account page opens. Choose <strong>Delete account</strong> and confirm.</li>
</ol>

<h2>On the web and in the desktop app</h2>
<ol>
<li>Open <a href="{ACCOUNT}">chat.psst.pro/auth/account</a> and sign in (or in the app: Settings → Account → Manage account).</li>
<li>Choose <strong>Delete account</strong> and confirm.</li>
</ol>

<h2>By e-mail, without signing in</h2>
<p>E-mail {MAIL} with the subject “Delete account” and include your username (e.g. <code>@name:psst.pro</code>). So that nobody else can delete your account, we will check that it is yours (for example by a confirmation in the app or from the e-mail address on your account). We delete the account within 30 days and confirm it to you.</p>

<h2>What is deleted</h2>
<ul>
<li>the account is closed permanently; it cannot be restored or signed in to again;</li>
<li>your display name, avatar and e-mail address;</li>
<li>all sessions, devices and their encryption keys, notification settings and push tokens;</li>
<li>your membership in all rooms and your entry in the member directory;</li>
<li>your messages are marked as erased and new room members will no longer see them.</li>
</ul>

<h2>What is kept, and for how long</h2>
<ul>
<li><strong>Messages others have already received</strong> stay in their conversations (in encrypted rooms the server only holds them in encrypted form).</li>
<li><strong>Files you uploaded</strong> stay available to those you shared them with. If you want us to remove them from the server, e-mail {MAIL}; we remove them within 30 days.</li>
<li><strong>Your username</strong> cannot be used again, so nobody can impersonate you.</li>
<li><strong>Backups:</strong> data remains in the server's encrypted backups until they are deleted, <strong>6 months</strong> at the latest.</li>
<li><strong>Reports</strong> and the record of administrator actions, as long as needed to protect the service.</li>
</ul>
<p>More in the <a href="/privacy">Privacy Policy</a>.</p>
""",
        },
    },    # ------------------------------------------------------------------------------------------------ support
    "support": {
        "sk": {
            "title": "Pomoc a kontakt",
            "desc": "Pomoc s aplikáciou psst secure chat a kontakt na prevádzkovateľa.",
            "body": f"""
<p class="meta">Aplikácia <strong>psst secure chat</strong> · prevádzkovateľ {OP_SK}</p>
<p class="callout">Kontakt: {MAIL}. Odpovedáme spravidla do 2 pracovných dní, na nahlásenia zneužitia do 24 hodín.</p>

<h2>Ako získam účet?</h2>
<p>psst je len na pozvánku. Pozývací kód dostanete od niekoho, kto službu používa, alebo od prevádzkovateľa. V aplikácii zvoľte <strong>Create account</strong> (Vytvoriť účet) a zadajte kód.</p>

<h2>Kde stiahnem aplikáciu?</h2>
<p>Android, Windows a macOS: <a href="https://app.psst.pro/download/">app.psst.pro/download</a>. Na webe: <a href="https://app.psst.pro/">app.psst.pro</a>.</p>

<h2>Nové zariadenie a staré správy</h2>
<p>Pri prihlásení na novom zariadení potvrďte svoju identitu iným prihláseným zariadením alebo kľúčom na obnovenie. Bez neho sa staršie šifrované správy nedajú prečítať, ani prevádzkovateľom.</p>

<h2>Nahlásenie a blokovanie</h2>
<p>Správu nahlásite podržaním prsta na správe → <strong>Nahlásiť</strong>. Miestnosť nahlásite v jej detaile → <strong>Nahlásiť miestnosť</strong>. Používateľa zablokujete v jeho profile → <strong>Zablokovať</strong>.</p>

<h2>Zmazanie účtu</h2>
<p>Postup je na <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2>Súkromie a podmienky</h2>
<p><a href="/privacy">Zásady ochrany súkromia</a> · <a href="/terms">Podmienky používania</a></p>
""",
        },
        "en": {
            "title": "Help and contact",
            "desc": "Help with the psst secure chat app and how to contact the operator.",
            "body": f"""
<p class="meta">App <strong>psst secure chat</strong> · operator {OP_EN}</p>
<p class="callout">Contact: {MAIL}. We usually reply within 2 working days, and to abuse reports within 24 hours.</p>

<h2>How do I get an account?</h2>
<p>psst is invitation only. You get an invitation code from someone who uses the service or from the operator. In the app choose <strong>Create account</strong> and enter the code.</p>

<h2>Where can I download the app?</h2>
<p>Android, Windows and macOS: <a href="https://app.psst.pro/download/">app.psst.pro/download</a>. On the web: <a href="https://app.psst.pro/">app.psst.pro</a>.</p>

<h2>New device and older messages</h2>
<p>When you sign in on a new device, confirm your identity with another signed-in device or with your recovery key. Without it, older encrypted messages cannot be read, not even by the operator.</p>

<h2>Reporting and blocking</h2>
<p>To report a message, touch and hold it → <strong>Report</strong>. To report a room, open its details → <strong>Report room</strong>. To block a user, open their profile → <strong>Block</strong>.</p>

<h2>Deleting your account</h2>
<p>See <a href="/delete-account">psst.pro/delete-account</a>.</p>

<h2>Privacy and terms</h2>
<p><a href="/privacy">Privacy Policy</a> · <a href="/terms">Terms of Use</a></p>
""",
        },
    },
}
