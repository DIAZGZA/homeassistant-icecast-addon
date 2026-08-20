# Changelog

## 1.0.0

- Initial release: Icecast + a from-source-built `ezstream` (fixes the upstream
  MP3/WebM/Matroska passthrough bug present in every packaged 1.0.2 release), configured
  via a `stations` list in the add-on options.
- `tools/add_album.py`: starter script for genre-tag-based playlist assignment and
  live (no-restart) playlist reload via `SIGHUP`.
