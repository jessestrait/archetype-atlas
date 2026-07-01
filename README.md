# Archetype Atlas

A single-page web app that connects to your Spotify Liked Songs library and maps your listening history onto eight Jungian archetypes — rendered as an interactive mandala you can explore track by track.

**Live demo:** [jessestrait.com](https://jessestrait.com) *(coming soon)*

---

## What it does

1. Authenticates with Spotify via PKCE (no backend required — tokens never leave your browser)
2. Fetches up to 500 of your Liked Songs and their audio features (valence, energy, tempo, mode, acousticness, instrumentalness)
3. Scores every track against each archetype using a weighted feature formula
4. Renders a mandala wheel where each slice's radius reflects how strongly that archetype is represented in your library
5. Tap any slice to read the archetype description and see which of your tracks scored highest for it

---

## How archetype scoring works

Each track is scored against all eight archetypes using a weighted linear combination of Spotify's audio features:

| Feature | What it captures |
|---|---|
| `valence` | Musical positivity (0 = dark, 1 = euphoric) |
| `energy` | Intensity and activity level |
| `mode` | Major (1) vs minor (0) key |
| `tempo_norm` | Tempo normalized to [0–1] over a 60–200 BPM range |
| `instrumentalness` | Absence of vocals |
| `acousticness` | Acoustic vs electronic character |

Each archetype has a fixed weight vector across those features. For example:

- **Shadow** weights `valence` and `mode` negatively — dark, minor-key tracks score high
- **Warrior** weights `energy` and `tempo_norm` positively — fast, intense tracks score high
- **Sage** weights `instrumentalness` heavily — ambient and instrumental music scores high
- **Wounded Healer** weights `acousticness` positively and `energy` negatively — quiet, vulnerable tracks score high

Raw scores are min-max normalized per archetype across your entire library so the mandala reflects *relative* distribution within your own collection, not an absolute threshold.

---

## The eight archetypes

| Archetype | Musical signature |
|---|---|
| **Shadow** | Dark, brooding, minor-key — what we repress |
| **Wounded Healer** | Acoustic, introspective, tender vulnerability |
| **Trickster** | Syncopated, unpredictable, genre-bending |
| **Lover / Anima** | Warm, major-key, intimate and romantic |
| **Sage** | Ambient, instrumental, slow and contemplative |
| **Warrior** | High-energy, fast-tempo, driven intensity |
| **Puer Aeternus** | Dreamy, ethereal, weightless wonder |
| **Explorer** | Eclectic, mid-energy, globally influenced |

---

## Setup

This is a plain HTML/CSS/JS file — no build step, no dependencies, no server.

**To use with your own Spotify library:**

1. Create an app at [developer.spotify.com](https://developer.spotify.com/dashboard)
2. Add your site's URL (or `http://localhost:8080`) as a Redirect URI
3. Replace `YOUR_SPOTIFY_CLIENT_ID` near the top of `index.html` with your app's Client ID
4. Open `index.html` in a browser (or serve it from any static host)

**To explore without Spotify:** click "Try demo data" on the landing screen.

---

## Deployment

Any static host works — GitHub Pages, Netlify, Vercel, Cloudflare Pages. No server-side code required.

---

## Stack

- Vanilla HTML / CSS / JS — zero dependencies, zero build tooling
- Spotify Web API (PKCE OAuth 2.0 flow)
- SVG mandala drawn programmatically at runtime
