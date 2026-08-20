#!/usr/bin/env python3
"""Add one album to the right station playlist and reload it live.

Runs on the HOST (needs `docker` and `ffprobe`/`ffmpeg` on PATH), not inside
the add-on container - it needs filesystem access to your media library and
the ability to signal the running ezstream processes.

Edit the constants and BUCKETS/ARTIST_OVERRIDE below to match your own
library layout and genre taxonomy; the values here are just an example.

Usage:
    add_album.py "/path/to/media/Artist - Album" [--genre "Rock"]
"""
import argparse
import os
import re
import subprocess
import sys
from collections import Counter

# --- EDIT THESE for your own setup -----------------------------------------

MEDIA_BASE = "/usr/share/hassio/media/MP3"          # host path to your library
MEDIA_CONTAINER_PREFIX = "/media/MP3"                # same folder, as seen inside the add-on
PLAYLIST_DIR = "/usr/share/hassio/share/mopidy/playlists"
DOCKER_CONTAINER = "app_local_icecast"

# raw ID3 genre tag -> your station's playlist slug (must match a station's
# `mount` in the add-on's `stations` option, i.e. PLAYLIST_DIR/<slug>.txt)
BUCKETS = {
    "Metal": {"Gothic Metal","Metal","Heavy Metal","Death Metal","Progressive Metal",
              "Melodic Power Metal","Symphonic Power Metal","Symphonic/Gothic Metal",
              "Rock Metal","Progressive Deathcore","Gothic","Gothic Rock","Darkwave",
              "Black Metal"},
    "Rock": {"Rock","Hard Rock","Rock/Pop","Alternative Rock","Alt. Rock","AlternRock",
             "alternative rock","Alternative-Rock","Classic Rock","New Rock","Rock & Roll",
             "Progressive Rock","Symphonic Rock","Instrumental Rock","Indie Rock","rock",
             "Pop Rock","OST/Rock","Alternative\\Rock"},
    "Punk & Alternative": {"Punk","Punk Rock","Alternative","Grunge",
             "Post-Grunge Alternative Rock","Post-Hardcore","Emo","Indie","Indie Pop"},
    "Hip-Hop & R&B": {"Hip-Hop","Rap","R&B","Rap/R&B","General R&B","Contemporary R&B",
             "Soul","Funk"},
    "Electronic & Dance": {"Electronic","Trance","Techno","Dance","Club Dance","Trip-Hop",
             "Electro","Hardcore Techno","New Wave","Industrial"},
    "Pop": {"Pop"},
    "Acoustic, Jazz & World": {"Blues","Folk","New Age","Classical","Jazz","Acoustic",
             "Latin","International","Celtic","Country","Reggae","World","Instrumental",
             "Vocal","Beat"},
}
SLUG_MAP = {
    "Rock": "rock",
    "Metal": "metal",
    "Punk & Alternative": "punk-alternative",
    "Acoustic, Jazz & World": "acoustic-jazz-world",
    "Hip-Hop & R&B": "hiphop-rnb",
    "Pop": "pop",
    "Electronic & Dance": "electronic-dance",
}
# artists whose whole catalog lacks a usable ID3 genre tag
ARTIST_OVERRIDE = {
    "Moonspell": "Metal", "Deftones": "Metal", "Nemesea": "Metal", "Sinbreed": "Metal",
    "Aerosmith": "Rock", "Boy Hits Car": "Rock", "Garbage": "Rock",
    "Gianluca Grignani": "Rock", "Il Tempio delle Clessidre": "Rock",
    "Jon Bon Jovi": "Rock", "Negroamaro": "Rock", "Noir Desire": "Rock",
    "Red Hot Chili Peppers": "Rock", "Temple of The Dog": "Rock", "U2": "Rock",
    "Vasco Rossi": "Rock", "Bonfire": "Rock", "Jon Spencer Blues Explosion": "Rock",
    "Chemical Vocation": "Rock", "Brand New": "Rock", "Queen": "Rock",
    "50 Cent": "Hip-Hop & R&B", "Black Eyed Peas": "Hip-Hop & R&B",
    "Chingy": "Hip-Hop & R&B", "Eminem Feat. Rihanna": "Hip-Hop & R&B",
    "Gorillaz": "Hip-Hop & R&B",
    "Gwen Stefani": "Pop", "Giorgia": "Pop", "Samuele Bersani": "Pop",
    "ATB": "Electronic & Dance", "Underworld": "Electronic & Dance",
    "Motel Connection": "Electronic & Dance",
    "Celtic": "Acoustic, Jazz & World", "Fabrizio de Andre": "Acoustic, Jazz & World",
    "Michael Buble": "Acoustic, Jazz & World",
}

# -----------------------------------------------------------------------------

LOOKUP = {raw: bucket for bucket, raws in BUCKETS.items() for raw in raws}


def artist_of(album_name):
    return re.split(r"\s+-\s+", album_name, maxsplit=1)[0].strip()


def ffprobe_genre(mp3_path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=genre",
         "-of", "default=noprint_wrappers=1:nokey=1", mp3_path],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return out or None


def guess_bucket(album_dir, artist):
    mp3s = sorted(f for f in os.listdir(album_dir) if f.lower().endswith(".mp3"))
    if not mp3s:
        return None
    raw = ffprobe_genre(os.path.join(album_dir, mp3s[0]))
    if raw and raw in LOOKUP:
        return LOOKUP[raw]
    if artist in ARTIST_OVERRIDE:
        return ARTIST_OVERRIDE[artist]
    # same-artist fallback: look at what other albums by this artist are
    # already filed under
    votes = []
    for slug in SLUG_MAP.values():
        path = os.path.join(PLAYLIST_DIR, f"{slug}.txt")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            if any(f"/{artist} - " in line or line.startswith(f"{MEDIA_CONTAINER_PREFIX}/{artist} -")
                   for line in f):
                votes.append(slug)
    if votes:
        winner_slug = Counter(votes).most_common(1)[0][0]
        for bucket, slug in SLUG_MAP.items():
            if slug == winner_slug:
                return bucket
    return None


def ensure_m3u(album_dir, album_name):
    has_m3u = any(f.lower().endswith(".m3u") for f in os.listdir(album_dir))
    if has_m3u:
        return
    mp3s = sorted(f for f in os.listdir(album_dir) if f.lower().endswith(".mp3"))
    with open(os.path.join(album_dir, album_name + ".m3u"), "w") as f:
        f.write("#EXTM3U\n")
        for name in mp3s:
            f.write(name + "\n")
    print(f"generated {album_name}.m3u ({len(mp3s)} tracks)")


def append_to_playlist(album_dir, slug):
    mp3s = sorted(f for f in os.listdir(album_dir) if f.lower().endswith(".mp3"))
    playlist_path = os.path.join(PLAYLIST_DIR, f"{slug}.txt")
    container_dir = MEDIA_CONTAINER_PREFIX + album_dir[len(MEDIA_BASE):]
    with open(playlist_path, "a") as f:
        for name in mp3s:
            f.write(f"{container_dir}/{name}\n")
    print(f"appended {len(mp3s)} tracks to {playlist_path}")


def reload_station(slug):
    ps = subprocess.run(
        ["docker", "exec", DOCKER_CONTAINER, "ps", "-ef"],
        capture_output=True, text=True,
    ).stdout
    pid = None
    for line in ps.splitlines():
        if f"{slug}.xml" in line:
            pid = line.split()[0]
            break
    if not pid:
        print(f"WARNING: no running ezstream process found for '{slug}' - "
              f"is that station configured and started?")
        return
    subprocess.run(["docker", "exec", DOCKER_CONTAINER, "kill", "-HUP", pid], check=True)
    print(f"sent SIGHUP to ezstream[{pid}] ({slug}) - playlist re-read scheduled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("album_dir", help="path to the album folder, e.g. "
                     f"{MEDIA_BASE}/Artist - Album")
    ap.add_argument("--genre", help="force a bucket name instead of auto-detecting")
    args = ap.parse_args()

    album_dir = os.path.abspath(args.album_dir)
    if not os.path.isdir(album_dir):
        sys.exit(f"not a directory: {album_dir}")
    album_name = os.path.basename(album_dir)
    artist = artist_of(album_name)

    ensure_m3u(album_dir, album_name)

    bucket = args.genre or guess_bucket(album_dir, artist)
    if not bucket:
        sys.exit("could not determine a genre bucket - pass --genre explicitly")
    if bucket not in SLUG_MAP:
        sys.exit(f"unknown bucket '{bucket}' - must be one of {list(SLUG_MAP)}")
    slug = SLUG_MAP[bucket]

    append_to_playlist(album_dir, slug)
    reload_station(slug)


if __name__ == "__main__":
    main()
