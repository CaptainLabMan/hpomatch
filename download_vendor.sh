#!/usr/bin/env bash
set -e

mkdir -p \
    static/vendor/bootstrap \
    static/vendor/jquery \
    static/vendor/autocomplete

download() {
    if [ ! -f "$2" ]; then
        curl -fL "$1" -o "$2.tmp"
        mv "$2.tmp" "$2"
    fi
}

bootstrap="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist"

download "$bootstrap/css/bootstrap.min.css" \
    "static/vendor/bootstrap/bootstrap.min.css"

download "$bootstrap/js/bootstrap.bundle.min.js" \
    "static/vendor/bootstrap/bootstrap.bundle.min.js"

download "https://code.jquery.com/jquery-3.7.1.min.js" \
    "static/vendor/jquery/jquery.min.js"

download \
    "https://cdn.jsdelivr.net/npm/@tarekraafat/autocomplete.js@10.2.10/dist/autoComplete.min.js" \
    "static/vendor/autocomplete/autoComplete.min.js"