#!/usr/bin/env python3
"""Malý adb/uiautomator pomocník pre živý test PSST Android.
  ui.py texts                 vypíše texty na obrazovke
  ui.py tap "<text>"          ťukne na prvý prvok s textom (alebo content-desc) obsahujúcim <text>
  ui.py type "<text>"         napíše text do zaostreného poľa
  ui.py tapfield <n>          ťukne na n-té editovateľné pole (0-based)
  ui.py wait "<text>" [s]     čaká, kým sa text objaví
  ui.py shot <file.png>       screenshot"""
import re, subprocess, sys, time
def adb(*a, **k): return subprocess.run(["adb", *a], capture_output=True, **k)
def dump():
    adb("shell", "rm", "-f", "/sdcard/u.xml")   # a failed dump must not return the previous screen
    adb("shell", "uiautomator", "dump", "/sdcard/u.xml")
    return adb("shell", "cat", "/sdcard/u.xml", text=True).stdout
def nodes(xml):
    for m in re.finditer(r"<node [^>]*>", xml):
        n = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', n) or [None, ""])[1]
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", g("bounds")))
        yield {"text": g("text"), "desc": g("content-desc"), "cls": g("class"), "c": ((x1 + x2) // 2, (y1 + y2) // 2)}
cmd, *rest = sys.argv[1:]
if cmd == "texts":
    print([n["text"] or n["desc"] for n in nodes(dump()) if n["text"] or n["desc"]])
elif cmd == "tap":
    ns = list(nodes(dump()))
    exact = [n for n in ns if rest[0].lower() in (n["text"].lower(), n["desc"].lower())]
    for n in exact + ns:
        if rest[0].lower() in (n["text"] + " " + n["desc"]).lower():
            adb("shell", "input", "tap", *map(str, n["c"])); print("tapped", n["text"] or n["desc"]); break
    else: sys.exit(f"not found: {rest[0]}")
elif cmd == "longpress":
    ns = list(nodes(dump()))
    for n in ns:
        if rest[0].lower() in (n["text"] + " " + n["desc"]).lower():
            x, y = map(str, n["c"]); adb("shell", "input", "swipe", x, y, x, y, "900"); print("long-pressed", n["text"] or n["desc"]); break
    else: sys.exit(f"not found: {rest[0]}")
elif cmd == "tapfield":
    f = [n for n in nodes(dump()) if "EditText" in n["cls"]]
    adb("shell", "input", "tap", *map(str, f[int(rest[0])]["c"])); print("tapped field", rest[0], "of", len(f))
elif cmd == "type":
    adb("shell", "input", "text", rest[0].replace(" ", "%s"))
elif cmd == "wait":
    t = time.time() + float(rest[1] if len(rest) > 1 else 60)
    while time.time() < t:
        if rest[0].lower() in dump().lower(): print("found", rest[0]); sys.exit(0)
        time.sleep(2)
    sys.exit(f"timeout waiting for {rest[0]}")
elif cmd == "shot":
    open(rest[0], "wb").write(adb("exec-out", "screencap", "-p").stdout)
