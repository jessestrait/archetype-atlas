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

SRC = "llm_archetypes.json"
OUT = "data_output.json"
TOP_N = 35

# key, name, glyph, color (matches index.html's ARCHETYPES.color / CSS --*-hi vars),
# blurb (copied verbatim from ARCHETYPES.desc), and the primary-label variants
# seen (or plausible) in LLM output that should map to this archetype.
ARCHETYPES = [
    dict(key="shadow", name="Shadow", glyph="●", color="#c06090",
         blurb="The repressed and unconscious self. Dark, brooding, emotionally complex music that confronts what we usually keep hidden.",
         variants=["shadow"]),
    dict(key="healer", name="Wounded Healer", glyph="✚", color="#60c090",
         blurb="Transformation through pain. Vulnerable, acoustic, introspective tracks that hold sorrow and resilience simultaneously.",
         variants=["wounded healer", "healer"]),
    dict(key="trickster", name="Trickster", glyph="♦", color="#c09040",
         blurb="The rule-breaker and shapeshifter. Syncopated, genre-bending, unpredictable music that refuses to be categorized.",
         variants=["trickster"]),
    dict(key="lover", name="Lover / Anima", glyph="♥", color="#c04080",
         blurb="Connection, longing, and beauty. High-valence or deeply felt tracks centered on intimacy, romance, and emotional warmth.",
         variants=["lover / anima", "lover/anima", "lover", "anima"]),
    dict(key="sage", name="Sage", glyph="◉", color="#6090c0",
         blurb="Clarity and contemplation. Ambient, instrumental, or lyrically dense tracks that invite reflection and sustained attention.",
         variants=["sage"]),
    dict(key="warrior", name="Warrior", glyph="⚔", color="#c06060",
         blurb="Drive, discipline, and intensity. High-energy, fast-tempo tracks that propel forward motion and focused aggression.",
         variants=["warrior"]),
    dict(key="puer", name="Puer Aeternus", glyph="☆", color="#9060c0",
         blurb="The eternal child — wonder, idealism, and escape. Dreamy, ethereal, or euphoric music that floats free of gravity.",
         variants=["puer aeternus", "puer"]),
    dict(key="explorer", name="Explorer", glyph="⬡", color="#40b0b0",
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

    archetypes_out = []
    for a in ARCHETYPES:
        bucket = buckets[a["key"]]
        count = len(bucket)
        pct = round(count / total * 100, 1) if total else 0
        top = sorted(bucket, key=lambda t: t.get("confidence", 0), reverse=True)[:TOP_N]
        tracks_out = [
            {"n": t.get("track", ""), "a": t.get("artist", ""),
             "s": t.get("confidence", 0), "r": t.get("reason", "")}
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

    print(f"Total tracks: {total}\n")
    print(f"{'Archetype':<18} {'count':>6} {'pct':>7}")
    for a in archetypes_out:
        print(f"{a['name']:<18} {a['count']:>6} {a['pct']:>6}%")

    if flagged:
        print(f"\n{len(flagged)} track(s) with unrecognized primary archetype:")
        for t in flagged:
            print(f"  - {t.get('track')!r} by {t.get('artist')!r}: primary={t.get('primary')!r}")
    else:
        print("\nAll tracks matched a known archetype — none flagged.")

if __name__ == "__main__":
    main()
