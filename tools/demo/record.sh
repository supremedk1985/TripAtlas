#!/usr/bin/env bash
# Records the documentation videos and screenshots (docs/videos, docs/images) from a fresh demo instance.
#
#   tools/demo/record.sh            # both languages
#   tools/demo/record.sh de         # one language
#
# Needs: Docker, the demo data (python3 tools/demo/build_demo.py), the image tripatlas:dev
# (docker build -f docker/Dockerfile -t tripatlas:dev .). Uses the Playwright image for the browser and an ffmpeg
# image for the conversion; nothing is installed on the host.
set -u
cd "$(dirname "$0")"
DEMO=$PWD
DOCS=$(cd ../../docs && pwd)
NET=tripatlas-demo
PLAYWRIGHT=mcr.microsoft.com/playwright:v1.63.0-noble
LANGS=${1:-"de en"}
WORK=$(mktemp -d)
trap 'docker rm -f ta-demo-traccar ta-demo-immich ta-demo >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; docker run --rm -v "$WORK":/w alpine sh -c "rm -rf /w/*"; rm -rf "$WORK"' EXIT  # files from containers belong to root

docker network create $NET >/dev/null 2>&1
start_fakes() {   # names of vehicles and people follow the language of the recording
  for svc in traccar immich; do
    docker rm -f ta-demo-$svc >/dev/null 2>&1
    docker run -d --name ta-demo-$svc --network $NET --network-alias $svc -v "$DEMO":/demo:ro -w /demo -e DEMO_LANG=$1 \
      python:3.12-slim sh -c "pip -q install fastapi uvicorn pillow >/dev/null 2>&1 && python fake_services.py $svc" >/dev/null
  done
}

# playwright-core for the recorder, once
if [ ! -d "$WORK/node_modules/playwright-core" ]; then
  docker run --rm -v "$WORK":/w -w /w $PLAYWRIGHT sh -c "npm init -y >/dev/null && npm i --silent playwright-core@1.63.0" >/dev/null
fi
cp "$DEMO/record.mjs" "$WORK/"
mkdir -p "$WORK/data" && cp "$DEMO/data/sauerland-weekend.gpx" "$WORK/data/"

for L in $LANGS; do
  echo "== $L: fresh TripAtlas"
  start_fakes $L
  docker rm -f ta-demo >/dev/null 2>&1
  rm -rf "$WORK/tadata" && mkdir -p "$WORK/tadata"
  docker run -d --name ta-demo --network $NET -p 127.0.0.1:8099:8097 -v "$WORK/tadata":/data \
    -e TZ=Europe/Berlin -e TRIPATLAS_SYNC_INTERVAL_MINUTES=2 tripatlas:dev >/dev/null
  until curl -sf http://127.0.0.1:8099/api/health >/dev/null; do sleep 1; done
  sleep 25   # fake services install their packages

  echo "== $L: recording"
  docker run --rm --network host --memory 3g --memory-swap 3g -e LANG_UI=$L -e BASE=http://127.0.0.1:8099 \
    -v "$WORK":/work -w /work $PLAYWRIGHT node record.mjs || echo "recording $L failed"

  docker run --rm -v "$WORK":/w alpine chown -R "$(id -u):$(id -g)" /w/out   # the browser container wrote as root
  echo "== $L: converting"
  mkdir -p "$DOCS/videos/$L" "$DOCS/images/$L"
  # screenshots: lossy palette compression, roughly a third of the size without a visible difference
  docker run --rm -v "$WORK/out/$L/images":/i alpine sh -c \
    "apk add -q pngquant >/dev/null && pngquant --quality 80-95 --speed 1 --strip --force --ext .png /i/*.png; chown -R $(id -u):$(id -g) /i"
  cp "$WORK/out/$L/images/"*.png "$DOCS/images/$L/" 2>/dev/null
  for f in "$WORK/out/$L/videos/"*.webm; do
    name=$(basename "$f" .webm)
    case $name in *-b) continue ;; esac
    if [[ $name == *-a ]]; then   # two parts (admin, then the child signs in): join them
      base=${name%-a}
      printf "file '%s'\nfile '%s'\n" "$(basename "$f")" "$base-b.webm" > "$WORK/out/$L/videos/list.txt"
      docker run --rm -v "$WORK/out/$L/videos":/v -w /v linuxserver/ffmpeg:latest -loglevel error -y \
        -f concat -safe 0 -i list.txt -c:v libx264 -preset slow -crf 30 -pix_fmt yuv420p -movflags +faststart \
        -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "/v/$base.mp4"
      cp "$WORK/out/$L/videos/$base.mp4" "$DOCS/videos/$L/"
      continue
    fi
    docker run --rm -v "$WORK/out/$L/videos":/v -w /v linuxserver/ffmpeg:latest -loglevel error -y -i "$name.webm" \
      -c:v libx264 -preset slow -crf 30 -pix_fmt yuv420p -movflags +faststart \
      -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "/v/$name.mp4"
    cp "$WORK/out/$L/videos/$name.mp4" "$DOCS/videos/$L/"
  done
done
ls -la "$DOCS"/videos/* "$DOCS"/images/*
