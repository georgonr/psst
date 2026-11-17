// psst — výber jazyka (DECISIONS D82). Na koreni (/) presmeruje na /sk/ alebo /en/ podľa uloženej voľby alebo
// jazyka prehliadača; prepínač v hlavičke voľbu uloží. Len localStorage v prehliadači, žiadne cookies.
(function () {
  var KEY = "psst-lang";
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  var path = location.pathname;
  if (path === "/" || path === "/index.html") {
    var pref = get();
    if (pref !== "sk" && pref !== "en") {
      var langs = navigator.languages || [navigator.language || ""];
      pref = "en";
      for (var i = 0; i < langs.length; i++) {
        var l = String(langs[i]).toLowerCase();
        if (l.indexOf("sk") === 0 || l.indexOf("cs") === 0) { pref = "sk"; break; }
        if (l.indexOf("en") === 0) break;
      }
    }
    location.replace("/" + pref + "/");
    return;
  }
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-lang]");
    if (a) set(a.getAttribute("data-lang"));
  });
  var m = path.match(/^\/(sk|en)\//);
  if (m && !get()) set(m[1]);
})();
