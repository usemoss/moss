#!/bin/zsh
# Local benchmark helper (macOS). See LOCAL_BENCHMARKS.md.
# Escape hatch for any run: pkill -9 -f 'benchmarks/.venv/bin/python'
set -u
HERE=${0:A:h}
cd $HERE
PY=$HERE/.venv/bin/python
export BENCH_RESULTS=${BENCH_RESULTS:-$HERE/results}

usage() {
  cat <<'EOF'
usage: ./run_local.sh <command>
  setup                 create .venv from uv.lock (exact pins) and download the fastembed model
  fetch-arxiv           download the 12 arXiv PDFs into data/arxiv/ and verify their sha256
  list                  show every benchmark, its arguments and what it needs
  run <name> [args]     run one benchmark under the watchdog; log in results/<name>-<args>.log
  smoke                 run every benchmark at small sizes (outputs in results/smoke/)
  memory-repro          headline memory result: moss_mem 100 vs 1000 docs per call (asks first)
Moss runs need MOSS_ENV_FILE=/path/to/.env (or MOSS_PROJECT_ID and MOSS_PROJECT_KEY exported).
EOF
}

list() {
  cat <<'EOF'
name                args                                                 creds+metered  peak RSS / time (M5 Max)
bench_local         lancedb|lancedb-hnsw|chroma|chroma-unpadded|qdrant   no             ~2.5 GB, 30-45 s
bench_local         moss                                                 yes            ~11 GB (HEAVY), ~30 s
bench_embed         -                                                    no             ~0.5 GB, ~15 s
bench_embed_tuning  -                                                    no             ~1.5 GB, ~40 s
doc_chunk_builtin   prep   (needs fetch-arxiv; run before the next three) no             small, seconds
batch_padding       -                                                    no             ~1 GB, ~30 s
moss_mem            <docs_per_call> [n_docs]                             yes            1000: ~22 GB (HEAVY); 100: ~2.2 GB
doc_chunk_builtin   run moss|chroma|chroma-reuse|chroma-unpadded paper|small <n>
                                                                         moss only      moss paper 1000: ~14.5 GB (HEAVY)
doc_chunk_builtin   ramp [max_n]                                         yes            up to ~14.5 GB (HEAVY)
moss_scale          <n_docs> [docs_per_call]                             yes            one call: ~1.1 MB per doc
moss_ramp           [max_docs]                                           yes            full ramp reached ~70 GB (HEAVY), ~5 min
moss_persist        build, then restore | restore-fake                   yes (not fake) ~1.1 GB, ~20 s
doc_chunk_eval      prep, then query-embed | run moss|chroma paper|small moss only      needs Ollama qwen3, ~11 GB (HEAVY)
EOF
}

has_creds() { [[ -f ${MOSS_ENV_FILE:-} ]] || [[ -n ${MOSS_PROJECT_ID:-} && -n ${MOSS_PROJECT_KEY:-} ]] }

needs_creds() {
  case "$*" in
    "moss_persist restore-fake"*) return 1 ;;
    moss_*|*" moss"*|"doc_chunk_builtin ramp"*) return 0 ;;
  esac
  return 1
}

run() {
  local name=$1; shift
  [[ -x $PY ]] || { echo "no .venv: run ./run_local.sh setup first"; return 2 }
  [[ -f $name.py ]] || { echo "unknown benchmark: $name (see ./run_local.sh list)"; return 2 }
  if needs_creds $name "$@" && ! has_creds; then
    echo "$name $*: needs MOSS_ENV_FILE (or MOSS_PROJECT_ID and MOSS_PROJECT_KEY)"; return 2
  fi
  mkdir -p $BENCH_RESULTS
  local tag=${(j:-:)@}
  local log=$BENCH_RESULTS/$name${tag:+-$tag}.log
  echo "== $name $* (log: $log)"
  ./watchdog.sh $log $PY $name.py "$@"
  local rc=$?
  cat $log
  return $rc
}

setup() {
  command -v uv >/dev/null || { echo "install uv first: https://docs.astral.sh/uv/"; return 1 }
  uv sync --locked || return 1
  $PY -c 'from fastembed import TextEmbedding; TextEmbedding("sentence-transformers/all-MiniLM-L6-v2", cache_dir=".fastembed_cache")'
}

fetch_arxiv() {
  mkdir -p data/arxiv
  local sum f
  while read -r sum f; do
    [[ -f data/arxiv/$f ]] && continue
    echo "fetching https://arxiv.org/pdf/${f%.pdf}"
    curl -fsSL -o data/arxiv/$f https://arxiv.org/pdf/${f%.pdf} || { rm -f data/arxiv/$f; return 1 }
    sleep 3  # arXiv asks for spacing between automated requests
  done < arxiv.sha256
  (cd data/arxiv && shasum -a 256 -c ../../arxiv.sha256)
}

fails=()
step() { run "$@" || fails+=("$*") }

smoke() {
  export BENCH_RESULTS=$HERE/results/smoke BENCH_DOCS=1000
  step bench_embed
  step bench_embed_tuning
  for db in lancedb lancedb-hnsw chroma chroma-unpadded qdrant; do step bench_local $db; done
  fetch_arxiv || fails+=(fetch-arxiv)
  step doc_chunk_builtin prep
  step batch_padding
  for s in chroma-reuse chroma-unpadded; do step doc_chunk_builtin run $s paper 125; done
  if has_creds; then
    step bench_local moss
    step moss_ramp 2000
    step moss_mem 100 250
    step moss_persist build
    step moss_persist restore
    step moss_persist restore-fake
    step doc_chunk_builtin ramp 250
  else
    echo "SKIPPED Moss runs: no credentials"
  fi
  echo "SKIPPED doc_chunk_eval: needs Ollama and ~11 GB (see LOCAL_BENCHMARKS.md)"
  (( ${#fails} )) && { print -l "SMOKE FAILED:" $fails; return 1 }
  echo "SMOKE PASSED: outputs in $BENCH_RESULTS"
}

memory_repro() {
  cat <<EOF
Runs moss_mem.py 100, then moss_mem.py 1000, on 1,000 paper chunks (Moss credentials, metered).
Expected peak RSS: ~2.2 GB (100 per call); ~22 GB (1,000 per call, including the re-ingest).
This machine has $(( $(sysctl -n hw.memsize) / 2**30 )) GB RAM. The watchdog kills a run on memory pressure.
Escape hatch: pkill -9 -f 'benchmarks/.venv/bin/python'
EOF
  read -q "?Continue? [y/N] " || { echo; return 1 }
  echo
  if [[ ! -f $BENCH_RESULTS/docchunk/builtin-paper-docs.json ]]; then
    fetch_arxiv && run doc_chunk_builtin prep || return 1
  fi
  run moss_mem 100 && run moss_mem 1000
}

cmd=${1:-help}
(( $# )) && shift
case $cmd in
  setup) setup ;;
  fetch-arxiv) fetch_arxiv ;;
  list) list ;;
  run) (( $# )) || { usage; exit 2 }; run "$@" ;;
  smoke) smoke ;;
  memory-repro) memory_repro ;;
  *) usage ;;
esac
