#!/usr/bin/env python3
"""
llm_archetype_pass.py

Runs every track in a Liked Songs CSV through Claude (via Claude Code's
headless `claude -p` mode) for reasoned Jungian archetype scoring -- the
same 8-archetype system as the rule-based scorer, but with real judgment
instead of keyword matching.

Uses your existing Claude Code login (Pro/Max subscription) via headless
mode. No separate API key needed.

Usage:
    python3 llm_archetype_pass.py Liked_Songs.csv --out llm_archetypes.json

Recommended first run -- test on a small slice before committing to the
whole library:
    python3 llm_archetype_pass.py Liked_Songs.csv --out test.json --limit 24

Options:
    --batch-size N   tracks per Claude call (default 12, matches what we
                      validated manually)
    --limit N        only process the first N tracks (good for testing)
"""
import argparse
import json
import subprocess
import sys
import time
import pandas as pd

ARCHETYPES = """
- Shadow: what got exiled from the conscious self. Low valence, minor key, industrial/darkwave/goth/doom energy -- but genuinely bleak, not just dark-sounding.
- Wounded Healer: pain turned directly into form. Aching-but-driving, cathartic, reaches outward rather than just wallowing.
- Trickster: lives at thresholds, subverts expectation, persona/artifice/masking. Playful or unsettling disruption.
- Lover/Anima: warmth, eros, longing, compassion/relatedness (broader than just romance).
- Sage: withdrawal as method. Contemplative, spacious, observer position -- genuinely reflective, not just "instrumental."
- Warrior: confrontation faced head-on. Armor, display, dominance, real aggression or survival-swagger.
- Puer Aeternus: the eternal child. Nostalgic, warped, longing for an elsewhere or a past that can't be recovered.
- Explorer: movement for its own sake. Restless, forward-leaning momentum with no destination.
""".strip()

GUIDANCE = """
Judgment calls learned from a manual test pass -- apply these:
1. Genre tags are a hint, not a rule. If the audio features (valence, energy,
   mode) contradict the genre's usual vibe, trust the data and your own
   knowledge of the specific track over the genre label.
2. A single genre word can span wildly different emotional registers (e.g.
   "jazz" covers both meditative cool jazz AND physical, communal hard bop).
   Judge the SPECIFIC track and artist, not the genre in the abstract.
3. If you know something real about a track's actual lyrical content, the
   artist's known persona, or the cultural/biographical context behind it,
   use that -- it's more diagnostic than genre or audio features alone.
4. Tempo can occasionally be double- or half-detected (e.g. a 93bpm song
   reading as 186bpm). If tempo seems inconsistent with genre and
   danceability, don't over-weight it.
5. Give an honest confidence score. If a track is genuinely ambiguous or
   blends two archetypes, say so with a lower confidence and name the
   secondary archetype rather than forcing a clean single answer.
""".strip()


def build_prompt(batch):
    track_lines = []
    for i, row in enumerate(batch):
        genres = row.get('Genres')
        genres_str = genres if pd.notna(genres) else 'none listed'
        mode_str = 'major' if row.get('Mode') == 1 else 'minor'
        track_lines.append(
            f"{i+1}. \"{row.get('Track Name')}\" by {row.get('Artist Name(s)')} "
            f"(album: {row.get('Album Name')}, released: {row.get('Release Date')}) "
            f"| genres: {genres_str} "
            f"| valence: {row.get('Valence')}, energy: {row.get('Energy')}, "
            f"mode: {mode_str}, danceability: {row.get('Danceability')}, "
            f"tempo: {row.get('Tempo')}, instrumentalness: {row.get('Instrumentalness')}, "
            f"acousticness: {row.get('Acousticness')}"
        )
    tracks_block = "\n".join(track_lines)

    return f"""You are scoring songs against 8 Jungian archetypes for a music \
personality app. Here are the archetypes:

{ARCHETYPES}

{GUIDANCE}

Score each of these {len(batch)} tracks. For each, give a primary archetype, \
a confidence score 0-100, an optional secondary archetype if it's a genuine \
blend, and a one-sentence reason grounded in the SPECIFIC track (not generic \
genre description).

Tracks:
{tracks_block}

Respond with ONLY a JSON array, no other text, no markdown code fences. Each \
element must look exactly like this:
{{"track": "...", "artist": "...", "primary": "...", "confidence": 0, \
"secondary": null, "reason": "..."}}"""


def run_batch(batch, retries=2):
    prompt = build_prompt(batch)
    uris = [row.get('Track URI') for row in batch]
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True, text=True, timeout=180
            )
        except FileNotFoundError:
            print("ERROR: 'claude' command not found. Is Claude Code installed and on PATH?", file=sys.stderr)
            sys.exit(1)
        except subprocess.TimeoutExpired:
            print(f"  Batch timed out (attempt {attempt+1}), retrying...", file=sys.stderr)
            continue

        if result.returncode != 0:
            # Rate limit / usage cap hit -- retrying immediately won't help,
            # and grinding through remaining batches will just fail the same
            # way while burning time. Stop cleanly; progress so far is saved.
            if "429" in result.stdout or "rate" in result.stdout.lower():
                print("\n=== Hit usage/rate limit (429). ===", file=sys.stderr)
                print("Progress so far is saved. Wait for your usage to reset,", file=sys.stderr)
                print("then re-run the exact same command -- already-scored", file=sys.stderr)
                print("tracks will be skipped automatically.", file=sys.stderr)
                sys.exit(1)

            print(f"  claude -p failed (attempt {attempt+1}): returncode={result.returncode}", file=sys.stderr)
            print(f"  STDOUT: {result.stdout[:500]}", file=sys.stderr)
            print(f"  STDERR: {result.stderr[:500]}", file=sys.stderr)
            time.sleep(2)
            continue

        try:
            envelope = json.loads(result.stdout)
            text = envelope.get("result", "").strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text.strip())
            # Attach the real Track URI by position -- the model returns
            # tracks in the same order it was given them, but we don't trust
            # it to echo back an ID it was never given, so we align by index.
            for idx, item in enumerate(parsed):
                if idx < len(uris):
                    item["uri"] = uris[idx]
            return parsed
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  Failed to parse response (attempt {attempt+1}): {e}", file=sys.stderr)
            time.sleep(2)

    print("  Giving up on this batch after retries -- skipping.", file=sys.stderr)
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--out", default="llm_archetypes.json")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--limit", type=int, default=None,
                         help="only process the first N tracks (for testing)")
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)
    if args.limit:
        df = df.head(args.limit)

    records = df.to_dict("records")

    # --- Resume support: skip tracks already scored in a previous run ---
    all_results = []
    already_done = set()
    try:
        with open(args.out) as f:
            all_results = json.load(f)
        already_done = {r.get("uri") for r in all_results if r.get("uri")}
        print(f"Resuming: found {len(already_done)} already-scored tracks in {args.out}, skipping those.")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    records = [r for r in records if r.get("Track URI") not in already_done]
    print(f"{len(records)} tracks remaining to score.")

    batches = [records[i:i + args.batch_size] for i in range(0, len(records), args.batch_size)]

    for i, batch in enumerate(batches):
        print(f"Batch {i+1}/{len(batches)} ({len(batch)} tracks)...")
        results = run_batch(batch)
        all_results.extend(results)
        # save after every batch so a crash doesn't lose progress
        with open(args.out, "w") as f:
            json.dump(all_results, f, indent=2)
        time.sleep(1)

    print(f"\nDone. {len(all_results)} tracks scored, written to {args.out}")


if __name__ == "__main__":
    main()
