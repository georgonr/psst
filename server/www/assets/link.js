// psst (D111): landing page of psst links — /u/@user:server, /r/%23alias:server, /r/!roomid:server[/$event][?via=…]
// (also the fragment form /r/#alias:server[/$event]). Shows the user / room and the buttons in Slovak or English
// (saved choice from the home page, otherwise the browser language). Only the room's public summary is fetched from
// the psst homeserver (no token, nothing is stored); user profiles are not public on psst, so only the ID is shown.
// All text goes through textContent; identifiers are validated before they are used in any link.
(function () {
  "use strict";
  var T = {
    sk: {
      user: "Pozvánka na rozhovor v psst", room: "Miestnosť v psst", event: "Správa v psst", bad: "Neplatný odkaz",
      leadUser: "Otvorte odkaz v aplikácii psst a začnite rozhovor. Ak aplikáciu ešte nemáte, stiahnite si ju.",
      leadRoom: "Otvorte odkaz v aplikácii psst a pripojte sa. Ak aplikáciu ešte nemáte, stiahnite si ju.",
      leadEvent: "Otvorte odkaz v aplikácii psst. Správu uvidíte, len ak ste v tejto miestnosti.",
      leadBad: "Tento odkaz psst nie je úplný alebo je poškodený. Požiadajte odosielateľa o nový.",
      roomName: "Miestnosť", members: function (n) { return n === 1 ? "1 člen" : (n >= 2 && n <= 4 ? n + " členovia" : n + " členov"); },
      open: "Otvoriť v psst", ios: "Stiahnuť pre iPhone", android: "Android", web: "Otvoriť na webe",
      note: "Odkaz neobsahuje správy. Obsah rozhovorov je šifrovaný medzi zariadeniami.",
      privacy: "Súkromie", terms: "Podmienky", title: "psst — pozvánka na rozhovor"
    },
    en: {
      user: "Invitation to chat on psst", room: "Room on psst", event: "Message on psst", bad: "Invalid link",
      leadUser: "Open the link in the psst app to start a conversation. If you don't have the app yet, download it.",
      leadRoom: "Open the link in the psst app to join. If you don't have the app yet, download it.",
      leadEvent: "Open the link in the psst app. You will see the message only if you are in this room.",
      leadBad: "This psst link is incomplete or damaged. Ask the sender for a new one.",
      roomName: "Room", members: function (n) { return n === 1 ? "1 member" : n + " members"; },
      open: "Open in psst", ios: "Download for iPhone", android: "Android", web: "Open on the web",
      note: "The link contains no messages. Conversations are encrypted between devices.",
      privacy: "Privacy", terms: "Terms", title: "psst — invitation to chat"
    }
  };

  function lang() {
    try { var s = localStorage.getItem("psst-lang"); if (s === "sk" || s === "en") return s; } catch (e) {}
    var langs = navigator.languages || [navigator.language || ""];
    for (var i = 0; i < langs.length; i++) {
      var l = String(langs[i]).toLowerCase();
      if (l.indexOf("sk") === 0 || l.indexOf("cs") === 0) return "sk";
      if (l.indexOf("en") === 0) return "en";
    }
    return "en";
  }

  var SERVER = "(?::[A-Za-z0-9.\\-]+(?::[0-9]{1,5})?)";
  var RE = {
    user: new RegExp("^@[A-Za-z0-9._=\\-/+]+" + SERVER + "$"),
    alias: new RegExp("^#[^\\s:/#?]+" + SERVER + "$"),
    roomId: new RegExp("^![A-Za-z0-9._~+/=\\-]+" + SERVER + "?$"),
    event: /^\$[A-Za-z0-9._~+\/=\-]+(?::[A-Za-z0-9.\-]+)?$/
  };

  function dec(s) { try { return decodeURIComponent(s); } catch (e) { return null; } }

  // → {kind: "user"|"room"|"event", user, room, event, via: []} or null
  function parse() {
    var path = location.pathname, hash = location.hash.replace(/^#/, ""), parts, m;
    var via = [];
    (location.search.replace(/^\?/, "").split("&")).forEach(function (kv) {
      var p = kv.split("="); if (p[0] === "via" && p[1]) { var v = dec(p[1]); if (v && /^[A-Za-z0-9.\-]+(:[0-9]{1,5})?$/.test(v)) via.push(v); }
    });
    if ((m = path.match(/^\/u\/([^/]+)\/?$/))) {
      var u = dec(m[1]);
      return u && RE.user.test(u) ? { kind: "user", user: u, via: via } : null;
    }
    if (path.indexOf("/r/") !== 0) return null;
    var rest = path.slice(3);
    if (rest === "" && hash) {                      // fragment form /r/#alias:server[/$event]
      var q = hash.indexOf("?");
      if (q >= 0) { hash = hash.slice(0, q); }
      parts = hash.split("/"); parts[0] = "#" + (dec(parts[0]) || "");
    } else {
      parts = rest.split("/").map(dec);
    }
    if (parts.length && parts[parts.length - 1] === "") parts.pop();
    if (parts.length < 1 || parts.length > 2 || parts.some(function (p) { return p === null; })) return null;
    var room = parts[0], ev = parts[1];
    if (!(RE.alias.test(room) || RE.roomId.test(room))) return null;
    if (ev !== undefined && !RE.event.test(ev)) return null;
    return { kind: ev ? "event" : "room", room: room, event: ev, via: via };
  }

  function enc(s) { return encodeURIComponent(s).replace(/%3A/gi, ":").replace(/%40/g, "@").replace(/%21/g, "!").replace(/%24/g, "$"); }

  // canonical https link (the form the apps generate) — used for the Android intent
  function canonicalPath(t) {
    if (t.kind === "user") return "/u/" + enc(t.user);
    var p = "/r/" + enc(t.room) + (t.event ? "/" + enc(t.event) : "");
    return p + (t.via.length ? "?" + t.via.map(function (v) { return "via=" + encodeURIComponent(v); }).join("&") : "");
  }

  // matrix: URI (MSC2312) — psst for iOS registers the "matrix" scheme
  function matrixUri(t) {
    var e = function (s) { return encodeURIComponent(s).replace(/%3A/gi, ":"); };
    var via = t.via.length ? "?" + t.via.map(function (v) { return "via=" + encodeURIComponent(v); }).join("&") : "";
    if (t.kind === "user") return "matrix:u/" + e(t.user.slice(1)) + "?action=chat";
    var base = t.room.charAt(0) === "#" ? "matrix:r/" + e(t.room.slice(1)) : "matrix:roomid/" + e(t.room.slice(1));
    return base + (t.event ? "/e/" + e(t.event.slice(1)) : "") + via;
  }

  function webLink(t) {
    if (t.kind === "user") return "https://app.psst.pro/#/user/" + t.user;
    return "https://app.psst.pro/#/room/" + t.room + (t.event ? "/" + t.event : "");
  }

  function $(id) { return document.getElementById(id); }
  function text(id, s) { var el = $(id); if (el) el.textContent = s; }

  var L = lang(), t = T[L], target = parse();
  document.documentElement.lang = L;
  document.title = t.title;
  text("ios", t.ios); text("android", t.android); text("web", t.web); text("open", t.open);
  text("note", t.note); text("privacy", t.privacy); text("terms", t.terms);

  if (!target) {
    text("kicker", t.bad); text("name", "psst"); text("mxid", ""); text("lead", t.leadBad);
    $("open").hidden = true; $("web").hidden = true;
    return;
  }

  var ua = navigator.userAgent || "";
  var isAndroid = /Android/i.test(ua);
  if (isAndroid) {
    $("open").href = "intent://psst.pro" + canonicalPath(target) + "#Intent;scheme=https;package=eu.macet.psst;S.browser_fallback_url=" +
      encodeURIComponent("https://app.psst.pro/download/") + ";end";
  } else {
    $("open").href = matrixUri(target);
  }
  $("web").href = webLink(target);

  if (target.kind === "user") {
    text("kicker", t.user); text("name", target.user); text("mxid", ""); text("lead", t.leadUser);
    return;
  }
  text("kicker", target.kind === "event" ? t.event : t.room);
  text("name", target.room.charAt(0) === "#" ? target.room : t.roomName);
  text("mxid", target.room.charAt(0) === "#" ? "" : target.room);
  text("lead", target.kind === "event" ? t.leadEvent : t.leadRoom);

  // public room summary (MSC3266) — only public / world-readable rooms answer without a token
  if (!window.fetch) return;
  fetch("/.well-known/matrix/client", { credentials: "omit" }).then(function (r) { return r.json(); }).then(function (wk) {
    var base = wk && wk["m.homeserver"] && wk["m.homeserver"].base_url;
    if (!base || !/^https:\/\/[A-Za-z0-9.\-]+\/?$/.test(base)) return null;
    var via = target.via.length ? target.via : ["psst.pro"];
    return fetch(base.replace(/\/$/, "") + "/_matrix/client/v1/room_summary/" + encodeURIComponent(target.room) + "?" +
      via.map(function (v) { return "via=" + encodeURIComponent(v); }).join("&"), { credentials: "omit", referrerPolicy: "no-referrer" });
  }).then(function (r) { return r && r.ok ? r.json() : null; }).then(function (s) {
    if (!s) return;
    if (typeof s.name === "string" && s.name.trim()) {
      text("name", s.name.trim().slice(0, 120));
      text("mxid", (s.canonical_alias || target.room) + (typeof s.num_joined_members === "number" ? " · " + t.members(s.num_joined_members) : ""));
    } else if (typeof s.num_joined_members === "number") {
      text("mxid", (target.room.charAt(0) === "#" ? "" : target.room + " · ") + t.members(s.num_joined_members));
    }
  }).catch(function () {});
})();
