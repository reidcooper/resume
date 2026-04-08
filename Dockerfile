FROM alpine:3.21

RUN apk add --no-cache \
    texlive texlive-luatex texmf-dist-latexextra texmf-dist-fontsrecommended \
    pandoc

WORKDIR /data
VOLUME ["/data"]
