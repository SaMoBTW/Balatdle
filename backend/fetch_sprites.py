"""Download each joker's sprite from the Balatro Wiki into frontend/public/jokers/.

Usage:  python fetch_sprites.py
Run it again after a balance patch adds jokers. Files are named by slug(), which
must match the slug() function in frontend/src/App.jsx.
Joker art is from Balatro by LocalThunk, published by Playstack; sprites via balatrowiki.org.
"""
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROSTER = Path(__file__).with_name("jokers.json")
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "jokers"
API = "https://balatrowiki.org/api.php"
HEADERS = {"User-Agent": "Balatdle class project (sprite fetch, run by hand)"}


def slug(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read()


def main():
    names = [j["name"] for j in json.loads(ROSTER.read_text(encoding="utf-8"))]
    OUT.mkdir(parents=True, exist_ok=True)
    urls = {}
    for i in range(0, len(names), 50):
        query = urllib.parse.urlencode({"action": "query", "format": "json", "redirects": 1,
                                        "prop": "pageimages", "piprop": "original",
                                        "titles": "|".join(names[i:i + 50])})
        data = json.loads(get(API + "?" + query))["query"]
        renamed = {r["to"]: r["from"] for r in data.get("normalized", []) + data.get("redirects", [])}
        for page in data["pages"].values():
            title = renamed.get(page["title"], page["title"])
            if "original" in page:
                urls[title] = page["original"]["source"]
    missing = [n for n in names if n not in urls]
    for name in names:
        if name in urls:
            (OUT / (slug(name) + ".png")).write_bytes(get(urls[name]))
            time.sleep(0.1)  # be polite to the wiki
    print("Saved {} sprites to {}".format(len(names) - len(missing), OUT))
    if missing:
        print("No image found for:", ", ".join(missing))


if __name__ == "__main__":
    main()
