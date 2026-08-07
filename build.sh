#!/usr/bin/env bash
# build.sh – Baut und pusht die modelarkapi Backend- und Frontend-Images.
# Erwartet: DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, optional DOCKERHUB_ORG.
set -euo pipefail

log_i(){ printf '[INFO] %s\n' "$1" >&2; }
log_w(){ printf '[WARN] %s\n' "$1" >&2; }
log_e(){ printf '[ERROR] %s\n' "$1" >&2; }

export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"

IMAGE_NAME="modelarkapi"
DEFAULT_ANSWER=""
IMG_VERSION=""

usage(){
  cat >&2 <<EOF
Usage: $(basename "$0") [--version X.Y.Z] [--default-answer y|n] [--help]

Options:
  -v, --version [X.Y.Z]        Image-Version (z. B. 0.0.01).
  -d, --default-answer [y|n]   Überschreiben ohne Rückfrage.
  -h, --help                   Diese Hilfe.

Umgebungsvariablen:
  DOCKERHUB_USERNAME   (Pflicht)
  DOCKERHUB_TOKEN      (Pflicht)
  DOCKERHUB_ORG        (Optional, überschreibt Username als Namespace)
EOF
}

parse_args(){
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -v|--version)
        [[ $# -ge 2 ]] || { log_e "Option $1 erfordert eine Version"; exit 2; }
        IMG_VERSION="$2"; shift 2;;
      --version=*)
        IMG_VERSION="${1#*=}"; shift;;
      -d|--default-answer)
        [[ $# -ge 2 ]] || { log_e "Option $1 erfordert [y|n]"; exit 2; }
        DEFAULT_ANSWER="$2"; shift 2;;
      --default-answer=*)
        DEFAULT_ANSWER="${1#*=}"; shift;;
      -h|--help) usage; exit 0;;
      *) log_w "Ignoriere unbekannte Option: $1"; shift;;
    esac
  done

  if [[ -n "$DEFAULT_ANSWER" ]]; then
    case "$DEFAULT_ANSWER" in
      y|Y) DEFAULT_ANSWER="y";;
      n|N) DEFAULT_ANSWER="n";;
      *) log_e "--default-answer erwartet 'y' oder 'n'"; exit 2;;
    esac
    log_i "Default-Antwort Überschreiben: '$DEFAULT_ANSWER'"
  fi
}

find_root(){
  if [[ -n "${ROOT_DIR:-}" && -d "$ROOT_DIR" ]]; then echo "$ROOT_DIR"; return; fi
  if command -v git >/dev/null 2>&1; then
    if root=$(git rev-parse --show-toplevel 2>/dev/null); then
      [[ -d "$root" ]] && { echo "$root"; return; }
    fi
  fi
  echo "$PWD"
}

need_env(){
  local name="$1"
  [[ -n "${!name:-}" ]] || { log_e "$name ist nicht gesetzt!"; exit 1; }
}

namespace(){
  if [[ -n "${DOCKERHUB_ORG:-}" ]]; then echo "$DOCKERHUB_ORG"; else echo "$DOCKERHUB_USERNAME"; fi
}

dockerhub_login(){
  log_i "Login bei Docker Hub…"
  echo "$DOCKERHUB_TOKEN" | docker login --username "$DOCKERHUB_USERNAME" --password-stdin >/dev/null
  log_i "Login ok."
}

confirm_overwrite_if_exists(){
  local ref="$1"
  log_i "Prüfe, ob ${ref} bereits existiert…"
  if docker manifest inspect "$ref" >/dev/null 2>&1; then
    log_w "Tag existiert bereits: $ref"
    if [[ -n "$DEFAULT_ANSWER" ]]; then
      [[ "$DEFAULT_ANSWER" == "y" ]] && { log_i "Überschreibe ohne Rückfrage."; return; }
      log_i "Kein Überschreiben (--default-answer n). Abbruch."
      exit 0
    fi
    read -r -p "Vorhandenes Image überschreiben? (y/N): " answer
    [[ "$answer" =~ ^[Yy]$ ]] || { log_i "Abgebrochen."; exit 0; }
  else
    log_i "Tag nicht vorhanden. Baue neu."
  fi
}

build_and_push(){
  local tag_prefix="$1"
  local context="$2"
  local dockerfile="$3"
  local image_namespace="$4"
  local version="$5"

  local ref_versioned="${image_namespace}/${IMAGE_NAME}:${tag_prefix}-${version}"
  local ref_latest="${image_namespace}/${IMAGE_NAME}:${tag_prefix}-latest"

  log_i "--- ${tag_prefix} ---"
  confirm_overwrite_if_exists "$ref_versioned"

  log_i "Baue ${ref_versioned}…"
  docker build \
    --build-arg IMG_VERSION="${version}" \
    -t "$ref_versioned" \
    -f "$dockerfile" \
    "$context"

  log_i "Push ${ref_versioned}…"
  docker push "$ref_versioned"

  log_i "Tag + Push ${ref_latest}…"
  docker tag "$ref_versioned" "$ref_latest"
  docker push "$ref_latest"

  log_i "${tag_prefix} fertig: ${ref_versioned}"
}

main(){
  parse_args "$@"

  need_env DOCKERHUB_USERNAME
  need_env DOCKERHUB_TOKEN

  local root
  root="$(find_root)"
  cd "$root"

  local backend_dockerfile="${BACKEND_DOCKERFILE:-$root/Dockerfile}"
  local frontend_dockerfile="${FRONTEND_DOCKERFILE:-$root/ui/Dockerfile}"
  [[ -f "$backend_dockerfile" ]] || { log_e "Backend-Dockerfile nicht gefunden: $backend_dockerfile"; exit 1; }
  [[ -f "$frontend_dockerfile" ]] || { log_e "Frontend-Dockerfile nicht gefunden: $frontend_dockerfile"; exit 1; }

  if [[ -z "$IMG_VERSION" ]]; then
    read -r -p "Image-Version (z. B. 0.0.01): " IMG_VERSION
    [[ -n "$IMG_VERSION" ]] || { log_e "Keine Version angegeben."; exit 1; }
  fi

  local image_namespace
  image_namespace="$(namespace)"

  log_i "Projekt-Root:        $root"
  log_i "Backend-Dockerfile:  $backend_dockerfile"
  log_i "Frontend-Dockerfile: $frontend_dockerfile"
  log_i "Namespace:           $image_namespace"
  log_i "Version:             $IMG_VERSION"

  dockerhub_login

  build_and_push "backend" "$root" "$backend_dockerfile" "$image_namespace" "$IMG_VERSION"
  build_and_push "frontend" "$root" "$frontend_dockerfile" "$image_namespace" "$IMG_VERSION"

  log_i "================================================"
  log_i "Fertig."
  log_i "  backend:  ${image_namespace}/${IMAGE_NAME}:backend-${IMG_VERSION}"
  log_i "  frontend: ${image_namespace}/${IMAGE_NAME}:frontend-${IMG_VERSION}"
}

main "$@"
