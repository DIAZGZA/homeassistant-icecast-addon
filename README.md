# Home Assistant Icecast Add-on

Icecast streaming server plus [ezstream](https://gitlab.xiph.org/xiph/ezstream) source
clients, configured as any number of playlist-backed radio stations. Streams your own
MP3 files **as-is** — no transcoding, no quality loss, no duplicate copy of your library.

## Why this exists

Home Assistant / Alpine's packaged `ezstream` (1.0.2, the latest tagged release) has a
confirmed upstream bug: it passes an invalid `usage` value to libshout's
`shout_set_content_format()` for every format except Ogg, so streaming **MP3** (or WebM,
or Matroska) fails outright with:

```
ezstream[...]: stream: default: format: MP3: This libshout doesn't support the requested option
```

This is not a libshout limitation — it's an ezstream bug
([xiph/ezstream#30](https://github.com/xiph/ezstream/issues/30),
[gitlab issue #2271](https://gitlab.xiph.org/xiph/ezstream/-/issues/2271)), fixed on
ezstream's `develop` branch back in 2022 (commit `c9426f2373`, "Set usage flags for each
format") — but **never included in a tagged release**, so every distro package (Alpine,
Debian, ...) still ships the broken version. This add-on builds ezstream from source
instead, picking up the fix.

(The older `ices2` isn't an alternative here — it only ever supported Ogg Vorbis input,
architecturally, regardless of build flags.)

## Configuration

```yaml
source_password: "changeme"
admin_user: "admin"
admin_password: "changeme"
stations:
  - name: "My Station"
    mount: "my-station"
    description: "Whatever you want to call it"
    playlist: "/share/playlists/my-station.txt"
```

- `mount` becomes the Icecast mountpoint (`/my-station`) and the listen URL:
  `http://<host>:8000/my-station`.
- `playlist` is a plain text file, **one absolute path per line**, no `#EXTM3U` header
  needed (blank lines and `#`-prefixed comment lines are ignored). Paths must resolve
  *inside the container* — if your MP3s live in Home Assistant's `/media` or `/share`
  folder, that's already mapped in by this add-on (see `map` in `config.json`), so use
  `/media/...` or `/share/...` paths, not the host path.
- A station with a missing playlist file is skipped at startup (logged, not fatal) —
  useful while you're still building out a station's playlist.

## Live playlist updates — no restart needed

Each station is an independent `ezstream` process. Editing a playlist file and sending
`SIGHUP` to that specific process makes it re-read the file and pick up new tracks —
verified against ezstream's source (`src/ezstream.c`: `SIGHUP` → "playlist re-read
scheduled") and tested live, with zero interruption to the stream. The other stations
are unaffected.

```sh
docker exec <container> ps -ef | grep ezstream      # find the PID for your station
docker exec <container> kill -HUP <pid>
```

See `tools/add_album.py` for a starter script that automates this (genre-tag detection,
appending to the right playlist, sending the signal) — the genre-bucket taxonomy in it
is just an example; edit `BUCKETS`/`ARTIST_OVERRIDE` to match how you want your own
library organized.

## Resource cost

Passthrough means no encoding/decoding at all — just paced disk reads and a loopback
network write. Measured running 7 concurrent stations on real hardware: **0.56% CPU,
12.5MB RAM total**.

## License

MIT, see `LICENSE`.
