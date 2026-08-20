#!/usr/bin/env bash
set -u

CONFIG_PATH=/data/options.json

xml_escape() {
  local s="$1"
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  printf '%s' "$s"
}

mkdir -p /var/log/icecast /etc/ezstream
chmod 777 /var/log/icecast

SOURCE_PASSWORD=$(jq -r '.source_password' "$CONFIG_PATH")
ADMIN_USER=$(jq -r '.admin_user' "$CONFIG_PATH")
ADMIN_PASSWORD=$(jq -r '.admin_password' "$CONFIG_PATH")
STATION_COUNT=$(jq -r '.stations | length' "$CONFIG_PATH")
SOURCES_LIMIT=$((STATION_COUNT + 2))

cat > /etc/icecast.xml <<EOF
<icecast>
    <limits>
        <clients>100</clients>
        <sources>${SOURCES_LIMIT}</sources>
        <queue-size>524288</queue-size>
        <client-timeout>30</client-timeout>
        <header-timeout>15</header-timeout>
        <source-timeout>10</source-timeout>
        <burst-on-connect>1</burst-on-connect>
        <burst-size>65535</burst-size>
    </limits>
    <authentication>
        <source-password>$(xml_escape "${SOURCE_PASSWORD}")</source-password>
        <relay-password>$(xml_escape "${SOURCE_PASSWORD}")</relay-password>
        <admin-user>$(xml_escape "${ADMIN_USER}")</admin-user>
        <admin-password>$(xml_escape "${ADMIN_PASSWORD}")</admin-password>
    </authentication>
    <hostname>localhost</hostname>
    <listen-socket>
        <port>8000</port>
    </listen-socket>
    <fileserve>1</fileserve>
    <paths>
        <basedir>/usr/share/icecast</basedir>
        <logdir>/var/log/icecast</logdir>
        <webroot>/usr/share/icecast/web</webroot>
        <adminroot>/usr/share/icecast/admin</adminroot>
    </paths>
    <logging>
        <accesslog>access.log</accesslog>
        <errorlog>error.log</errorlog>
        <loglevel>3</loglevel>
        <logsize>10000</logsize>
    </logging>
    <security>
        <chroot>0</chroot>
        <changeowner>
            <user>nobody</user>
            <group>nogroup</group>
        </changeowner>
    </security>
</icecast>
EOF

echo "starting icecast"
icecast -c /etc/icecast.xml &
ICECAST_PID=$!

echo "waiting for icecast to accept connections on 8000"
for i in $(seq 1 20); do
  if (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null; then
    exec 3>&-
    break
  fi
  sleep 1
done

for i in $(seq 0 $((STATION_COUNT - 1))); do
  mount=$(jq -r ".stations[$i].mount" "$CONFIG_PATH")
  name=$(jq -r ".stations[$i].name" "$CONFIG_PATH")
  description=$(jq -r ".stations[$i].description // \"\"" "$CONFIG_PATH")
  playlist=$(jq -r ".stations[$i].playlist" "$CONFIG_PATH")

  if [[ ! -f "${playlist}" ]]; then
    echo "skipping station '${mount}': playlist not found at ${playlist}"
    continue
  fi

  cfg="/etc/ezstream/${mount}.xml"
  cat > "${cfg}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<ezstream>
  <servers>
    <server>
      <hostname>127.0.0.1</hostname>
      <port>8000</port>
      <user>source</user>
      <password>$(xml_escape "${SOURCE_PASSWORD}")</password>
    </server>
  </servers>
  <streams>
    <stream>
      <mountpoint>/${mount}</mountpoint>
      <format>MP3</format>
      <public>No</public>
      <stream_name>$(xml_escape "${name}")</stream_name>
      <stream_description>$(xml_escape "${description}")</stream_description>
      <stream_genre>$(xml_escape "${name}")</stream_genre>
    </stream>
  </streams>
  <intakes>
    <intake>
      <type>playlist</type>
      <filename>$(xml_escape "${playlist}")</filename>
      <shuffle>Yes</shuffle>
      <stream_once>No</stream_once>
    </intake>
  </intakes>
  <metadata>
    <format_str>@a@ - @t@</format_str>
    <normalize_strings>Yes</normalize_strings>
  </metadata>
</ezstream>
EOF

  echo "starting ezstream source: ${mount}"
  ezstream -r -c "${cfg}" &
done

wait "${ICECAST_PID}"
