#!/usr/bin/env python3
"""
build_data.py

Transforms llm_archetypes.json (1071 LLM-scored tracks) into the DATA
constant shape consumed by index.html's static demo:

    { totalTracks, archetypes: [ { key, name, glyph, color, blurb,
      count, pct, tracks: [ {n, a, s, r} ] } ] }

Glyph/color/blurb are fixed per-archetype metadata (copied from the
existing ARCHETYPES config in index.html). count/pct/tracks are
recomputed from llm_archetypes.json.
"""
import json
import re
import time
import urllib.error
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SRC = "llm_archetypes.json"
OUT = "data_output.json"
TOP_N = 35
OEMBED_URL = "https://open.spotify.com/oembed"

# key, name, glyph, color (matches index.html's ARCHETYPES.color / CSS --*-hi vars),
# blurb (copied verbatim from ARCHETYPES.desc), and the primary-label variants
# seen (or plausible) in LLM output that should map to this archetype.
ARCHETYPES = [
    dict(key="shadow", name="Shadow", glyph="●", color="#a97c54",
         blurb="The repressed and unconscious self. Dark, brooding, emotionally complex music that confronts what we usually keep hidden.",
         variants=["shadow"]),
    dict(key="healer", name="Wounded Healer", glyph="✚", color="#92a35c",
         blurb="Transformation through pain. Vulnerable, acoustic, introspective tracks that hold sorrow and resilience simultaneously.",
         variants=["wounded healer", "healer"]),
    dict(key="trickster", name="Trickster", glyph="♦", color="#d1a23e",
         blurb="The rule-breaker and shapeshifter. Syncopated, genre-bending, unpredictable music that refuses to be categorized.",
         variants=["trickster"]),
    dict(key="lover", name="Lover / Anima", glyph="♥", color="#d97a52",
         blurb="Connection, longing, and beauty. High-valence or deeply felt tracks centered on intimacy, romance, and emotional warmth.",
         variants=["lover / anima", "lover/anima", "lover", "anima"]),
    dict(key="sage", name="Sage", glyph="◉", color="#7fa3b8",
         blurb="Clarity and contemplation. Ambient, instrumental, or lyrically dense tracks that invite reflection and sustained attention.",
         variants=["sage"]),
    dict(key="warrior", name="Warrior", glyph="⚔", color="#c1452b",
         blurb="Drive, discipline, and intensity. High-energy, fast-tempo tracks that propel forward motion and focused aggression.",
         variants=["warrior"]),
    dict(key="puer", name="Puer Aeternus", glyph="☆", color="#cbce85",
         blurb="The eternal child — wonder, idealism, and escape. Dreamy, ethereal, or euphoric music that floats free of gravity.",
         variants=["puer aeternus", "puer"]),
    dict(key="explorer", name="Explorer", glyph="⬡", color="#4fa39a",
         blurb="Restlessness and discovery. Tracks with global or eclectic influences that evoke travel and the unfamiliar.",
         variants=["explorer"]),
]

def normalize(label):
    s = label.strip().lower()
    s = re.sub(r"\s*/\s*", "/", s)  # "lover / anima" -> "lover/anima"
    s = re.sub(r"\s+", " ", s)
    return s

VARIANT_TO_KEY = {}
for a in ARCHETYPES:
    for v in a["variants"]:
        VARIANT_TO_KEY[normalize(v)] = a["key"]

def fetch_thumbnail(uri, retries=4):
    if not uri:
        return None
    url = OEMBED_URL + "?" + urllib.parse.urlencode({"url": uri})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get("thumbnail_url")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception:
            time.sleep(1)
    return None

def fetch_thumbnails(uris):
    unique = [u for u in dict.fromkeys(uris) if u]
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for uri, thumb in zip(unique, pool.map(fetch_thumbnail, unique)):
            results[uri] = thumb
    return results

def main():
    with open(SRC) as f:
        tracks = json.load(f)

    total = len(tracks)
    buckets = {a["key"]: [] for a in ARCHETYPES}
    flagged = []

    for t in tracks:
        raw = t.get("primary", "")
        norm = normalize(raw)
        key = VARIANT_TO_KEY.get(norm)
        if key is None:
            flagged.append(t)
            continue
        buckets[key].append(t)

    tops = {}
    for a in ARCHETYPES:
        bucket = buckets[a["key"]]
        tops[a["key"]] = sorted(bucket, key=lambda t: t.get("confidence", 0), reverse=True)[:TOP_N]

    all_top_uris = [t.get("uri") for top in tops.values() for t in top]
    print(f"Fetching album thumbnails for {len(set(all_top_uris))} tracks...")
    thumbnails = fetch_thumbnails(all_top_uris)

    archetypes_out = []
    for a in ARCHETYPES:
        bucket = buckets[a["key"]]
        count = len(bucket)
        pct = round(count / total * 100, 1) if total else 0
        top = tops[a["key"]]
        tracks_out = [
            {"n": t.get("track", ""), "a": t.get("artist", ""),
             "s": t.get("confidence", 0), "r": t.get("reason", ""),
             "img": thumbnails.get(t.get("uri")) or ""}
            for t in top
        ]
        archetypes_out.append({
            "key": a["key"], "name": a["name"], "glyph": a["glyph"],
            "color": a["color"], "blurb": a["blurb"],
            "count": count, "pct": pct, "tracks": tracks_out,
        })

    data = {"totalTracks": total, "archetypes": archetypes_out}

    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)

    missing_thumbs = sum(1 for a in archetypes_out for t in a["tracks"] if not t["img"])

    print(f"Total tracks: {total}\n")
    print(f"{'Archetype':<18} {'count':>6} {'pct':>7}")
    for a in archetypes_out:
        print(f"{a['name']:<18} {a['count']:>6} {a['pct']:>6}%")
    print(f"\nMissing thumbnails: {missing_thumbs} / {sum(len(a['tracks']) for a in archetypes_out)}")

    if flagged:
        print(f"\n{len(flagged)} track(s) with unrecognized primary archetype:")
        for t in flagged:
            print(f"  - {t.get('track')!r} by {t.get('artist')!r}: primary={t.get('primary')!r}")
    else:
        print("\nAll tracks matched a known archetype — none flagged.")

if __name__ == "__main__":
    main()
