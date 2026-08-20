ARG BUILD_FROM

# ezstream 1.0.2 (the latest tagged release, and what Alpine packages) has a
# confirmed upstream bug: it passes an invalid "usage" value of 0 to
# shout_set_content_format() for every format except Ogg, so libshout
# rejects MP3/WebM/Matroska streams with "This libshout doesn't support the
# requested option" (https://gitlab.xiph.org/xiph/ezstream/-/issues/2271).
# Fixed on the git default branch (commit c9426f2373, "Set usage flags for
# each format") but never included in a tagged release, so we build from
# source instead of using the packaged binary.
FROM $BUILD_FROM AS ezstream-builder

RUN apk add --no-cache \
      git build-base autoconf automake libtool pkgconfig \
      libshout-dev libxml2-dev taglib-dev gettext-dev check-dev libbsd-dev

RUN git clone --depth 1 https://gitlab.xiph.org/xiph/ezstream.git /src/ezstream \
 && cd /src/ezstream \
 && ./autogen.sh \
 && CPPFLAGS='-I/usr/include/bsd -DLIBBSD_OVERLAY' LIBS='-lbsd' ./configure --prefix=/usr \
 && make -j"$(nproc)" \
 && make install DESTDIR=/out

FROM $BUILD_FROM

RUN apk add --no-cache icecast libshout libxml2 taglib libbsd jq

COPY --from=ezstream-builder /out/usr/bin/ezstream /usr/bin/ezstream

COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
