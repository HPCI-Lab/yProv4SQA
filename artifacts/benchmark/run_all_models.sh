#!/usr/bin/env bash
set -euo pipefail

MODELS=("llama3.2" "llama3.1:8b" "llama3.3:70b")
PROV_DOC="./Provenance_documents/interTwin-eu_itwinai_prov_output.json"
PORT=5000
OUT="benchmark/results"

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "========================================================"
    echo "  Switching to model: $MODEL"
    echo "========================================================"

    pkill -f "prov-chat" 2>/dev/null || true
    sleep 2

    prov-chat "$PROV_DOC" --web --port $PORT --model "$MODEL" &
    SERVER_PID=$!
    echo "  Started prov-chat (pid=$SERVER_PID) with model=$MODEL"

    echo -n "  Waiting for server..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:$PORT/api/app-status" >/dev/null 2>&1; then
            echo " ready."
            break
        fi
        sleep 2
        echo -n "."
    done

    echo -n "  Warming up model (may take several minutes for large models)..."
    curl -s -X POST "http://localhost:$PORT/api/chat" \
        -H "Content-Type: application/json" \
        -d '{"question":"How many assessments are in the provenance document?"}' \
        --max-time 600 >/dev/null 2>&1 && echo " done." || echo " (warmup timed out at 600s)"
    curl -sf -X POST "http://localhost:$PORT/api/reset" >/dev/null 2>&1 || true
    sleep 2

    python3 benchmark/run_benchmark_all_repos.py \
        --url "http://localhost:$PORT" \
        --out "$OUT" \
        --model "$MODEL" \
        --timeout 300

    echo "  Done: $MODEL"
done

echo ""
echo "All models complete. Results in $OUT/"
