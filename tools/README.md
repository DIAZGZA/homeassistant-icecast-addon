# add_album.py

Adds one new album to the right station's playlist and makes that station pick it
up immediately — no add-on restart, and no effect on the other stations.

Runs on the **host** (or wherever your media library and Docker are), not inside the
add-on container. It needs:

- `docker` on `PATH`, with access to the add-on's container (default assumed name:
  `app_local_icecast` — matches Supervisor's naming for a local add-on installed as
  `local_icecast`; change `DOCKER_CONTAINER` at the top of the script if yours differs).
- `ffprobe` on `PATH` (ships with `ffmpeg`) — used to read the ID3 `genre` tag.
- Filesystem access to the same media folder the add-on reads from, and to the
  directory holding your `playlists/*.txt` files.

## Usage

```sh
python3 add_album.py "/path/to/your/media/Artist - Album Name"
```

That's it for the common case. It will:

1. **Generate a `.m3u`** for the album if one doesn't already exist (sorted `*.mp3`
   glob, one filename per line).
2. **Work out which station it belongs on**, in order:
   - Read the ID3 `genre` tag off the first track and look it up in `BUCKETS`.
   - If that tag is missing/junk, check `ARTIST_OVERRIDE` for the artist (parsed as
     everything before the first `" - "` in the folder name).
   - If neither hits, fall back to a **same-artist majority vote**: scan the existing
     playlists for other albums by the same artist and use whichever station most of
     them are already filed under.
   - If none of that resolves anything, it exits and asks you to pass `--genre`
     explicitly.
3. **Append the album's tracks** to `<PLAYLIST_DIR>/<slug>.txt`, as absolute paths
   using the container-side prefix (`MEDIA_CONTAINER_PREFIX`), one per line.
4. **Reload just that one station.** It finds the running `ezstream` process for that
   station's mount inside the container (`docker exec <container> ps -ef`) and sends
   it `SIGHUP`. ezstream's own signal handler logs "playlist re-read scheduled" and
   re-reads the file from the top on its next loop — the stream never drops and no
   other station is touched. This is documented behavior in ezstream's source
   (`src/ezstream.c`/`src/playlist.c`), not a hack, and has been tested live with zero
   playback interruption.

Force a specific station instead of auto-detecting:

```sh
python3 add_album.py "/path/to/media/Some Obscure Artist - Debut" --genre "Metal"
```

`--genre` must be one of the bucket names in `BUCKETS` (i.e. a *bucket*, like `"Rock"`
or `"Hip-Hop & R&B"` — not a raw ID3 tag string).

## Setting it up for your own library

Everything under the `EDIT THESE for your own setup` header at the top of the script
is a starting point, not a fixed taxonomy:

- `MEDIA_BASE` / `MEDIA_CONTAINER_PREFIX` — the host path to your library, and the
  same folder as it's mapped inside the add-on container (via `map: ["media:ro", ...]`
  in `config.json` — `/media/...` if you used the `media` map, `/share/...` if `share`).
- `PLAYLIST_DIR` — where your `<slug>.txt` playlist files live. Each `<slug>` must
  match a station's `mount` in the add-on's `stations` option.
- `DOCKER_CONTAINER` — the running add-on container's name.
- `BUCKETS` — maps raw ID3 genre tag strings to your own bucket/station names. The
  set shipped here reflects one real ~750-album MP3 library's tags and is a reasonable
  starting point, but ID3 genre tagging is inconsistent across rips — expect to add a
  few of your own over time as you hit tags that aren't covered.
- `SLUG_MAP` — maps each bucket name to its playlist/mount slug.
- `ARTIST_OVERRIDE` — artists whose *entire* catalog lacks a usable genre tag, so the
  same-artist fallback has nothing to vote from. Add entries here as you hit them.

If you only run one or two stations, this is overkill — just append the album's
tracks to the right `.txt` file yourself and send `SIGHUP` by hand (see the main
`README.md`). This script exists for libraries big enough that doing that by hand
every time gets old.
