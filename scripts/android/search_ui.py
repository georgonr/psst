#!/usr/bin/env python3
"""PSST (DECISIONS.md D84): phone side of the Android message-search release check (scripts/android/search-gate.sh).

  search_ui.py <query> [timeout_s] [rows]
        from the psst chat list: Search → type the query → "Messages" tab, then count the distinct corpus tags "(sgNN)"
        among the results (scripts/android/search_check.py). With "rows": count distinct result rows ("sender: snippet",
        for corpora without tags, e.g. scripts/audit/search-partner.mjs). Scrolls through all results.
        Prints JSON {"query", "count", "tags"}; waits until the count is stable.
Needs adb (one device, or ANDROID_SERIAL) and psst on the chat list screen. Queries must be ASCII (adb input text).
"""
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import sys
import time


def adb(*a: str) -> str:
    return subprocess.run(["adb", *a], capture_output=True, text=True).stdout


LAST_XML = ""


def messages_tab_selected(xml: str) -> bool:
    """The "Messages"/"Správy" segment is selected: its nearest checkable ancestor is checked."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return False

    def walk(n, path):
        if (n.get("text") or "") in ("Messages", "Správy"):
            for a in reversed(path):
                if a.get("checkable") == "true":
                    return a.get("checked") == "true"
        return any(walk(c, path + [n]) for c in n)

    return walk(root, [])


def nodes() -> list[dict]:
    global LAST_XML
    adb("shell", "uiautomator", "dump", "/sdcard/psst-sg.xml")
    xml = adb("shell", "cat", "/sdcard/psst-sg.xml")
    LAST_XML = xml
    out = []
    for n in re.findall(r"<node [^>]*>", xml):
        g = lambda k: (re.search(k + r'="([^"]*)"', n) or [None, ""])[1]  # noqa: E731
        b = list(map(int, re.findall(r"\d+", g("bounds")))) or [0, 0, 0, 0]
        out.append({"text": g("text"), "desc": g("content-desc"), "cls": g("class"),
                    "c": ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)})
    return out


def tap(label: str, ns: list[dict]) -> bool:
    for n in ns:
        if label.lower() in (n["text"].lower(), n["desc"].lower()):
            adb("shell", "input", "tap", *map(str, n["c"]))
            return True
    return False


def to_chat_list() -> None:
    """Back to the psst chat list (closes an open search screen, so the next query does not append to an old one)."""
    for _ in range(4):
        ns = nodes()
        if any(n["text"] in ("Create room", "Vytvoriť miestnosť") or n["desc"] in ("Create room", "Vytvoriť miestnosť")
               for n in ns) and not any(n["desc"] in ("Clear search field",) for n in ns):
            return
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(1.2)


def main() -> None:
    query = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    if not re.fullmatch(r"[A-Za-z0-9 ]+", query):
        sys.exit("search_ui: ASCII letters, digits and spaces only")
    if "eu.macet.psst" not in adb("shell", "dumpsys", "activity", "activities").split("mResumedActivity", 1)[-1][:300]:
        sys.exit("search_ui: psst is not in the foreground")
    adb("shell", "cmd", "statusbar", "collapse")  # a heads-up notification can cover the search button
    time.sleep(1)
    to_chat_list()
    ns = nodes()
    if not (tap("Search", ns) or tap("Hľadať", ns)):
        sys.exit("search_ui: no Search button (is psst on the chat list?)")
    time.sleep(2)
    adb("shell", "input", "text", query.replace(" ", "%s"))
    time.sleep(2)
    if not (tap("Messages", nodes()) or tap("Správy", nodes())):
        sys.exit("search_ui: no Messages tab")
    rows = len(sys.argv) > 3 and sys.argv[3] == "rows"

    def visible() -> set:
        nonlocal seen_proof
        texts = [n["text"] for n in nodes() if n["text"]]
        seen_proof = seen_proof or any(t in proof for t in texts) or messages_tab_selected(LAST_XML)
        if rows:  # a result row is "sender: snippet"; the room name and time are separate nodes
            return {t for t in texts if re.match(r"^[^:]{1,40}: .{8,}", t) and not t.startswith("There are no")}
        return set(re.findall(r"\(sg(\d\d)\)", " ".join(texts)))

    # The count must come from the Messages tab (D84: a test in batch 16 read the Chats tab — chat NAMES — and took its
    # empty state for a broken message search). Proof: the Messages segment is checked, or the Messages header above
    # results, or the Messages empty state is visible.
    proof = ("From your messages", "Z vašich správ", "No results in the last 3 months", "Za posledné 3 mesiace nič")
    seen_proof = False
    tags, last, stable, end = set(), None, 0, time.time() + timeout
    while time.time() < end:
        tags = visible()
        stable = stable + 1 if tags == last else 0
        last = tags
        if stable >= 2 and (tags or time.time() > end - timeout / 2):
            break
        time.sleep(2)
    # results below the fold: scroll until two swipes bring nothing new
    idle = 0
    while tags and idle < (4 if rows else 2):
        adb("shell", "input", "swipe", "540", "1350", "540", "650", "500")
        time.sleep(1.5)
        more = visible() - tags
        tags |= more
        idle = 0 if more else idle + 1
    if not seen_proof:
        sys.exit("search_ui: not on the Messages tab — count not valid")
    to_chat_list()
    print(json.dumps({"query": query, "count": len(tags), "tags": sorted(tags) if not rows else sorted(tags)[:3]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
