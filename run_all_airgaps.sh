#!/bin/bash
# Parallel batch runner: Execute all airgaps in independent background jobs
# Usage: ./run_all_airgaps.sh <config_file> [max_parallel_jobs]

set -e

CONFIG="${1:?Usage: run_all_airgaps.sh <config> [max_jobs]}"
MAX_JOBS="${2:-4}"

if [ ! -f "$CONFIG" ]; then
    echo "Error: config file not found: $CONFIG"
    exit 1
fi

# Extract airgap parameters from config using Python
read -r AIRGAP_MIN AIRGAP_MAX AIRGAP_STEPS < <(python3 << 'PYSCRIPT'
import sys, yaml, numpy as np
with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f)
ag_min = cfg.get('airgap_min_mm', 0.5)
ag_max = cfg.get('airgap_max_mm', 8.0)
ag_steps = cfg.get('airgap_steps', 16)
print(ag_min, ag_max, ag_steps)
PYSCRIPT
"$CONFIG")

# Generate airgap values
AIRGAPS=($(python3 << 'PYSCRIPT'
import sys, numpy as np
airgap_min = float(sys.argv[1])
airgap_max = float(sys.argv[2])
airgap_steps = int(sys.argv[3])
for ag in np.linspace(airgap_min, airgap_max, airgap_steps):
    print(f"{ag:.2f}")
PYSCRIPT
"$AIRGAP_MIN" "$AIRGAP_MAX" "$AIRGAP_STEPS"))

echo "Running analysis for ${#AIRGAPS[@]} airgaps (max $MAX_JOBS parallel)..."
echo "Airgaps: ${AIRGAPS[@]}"
echo ""

# Track background jobs
PIDS=()
AG_IDX=0

# Start background jobs with concurrency limit
for ag in "${AIRGAPS[@]}"; do
    # Wait if we've reached max parallel jobs
    while [ ${#PIDS[@]} -ge $MAX_JOBS ]; do
        # Remove completed PIDs
        NEW_PIDS=()
        for pid in "${PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                NEW_PIDS+=("$pid")
            fi
        done
        PIDS=("${NEW_PIDS[@]}")
        [ ${#PIDS[@]} -ge $MAX_JOBS ] && sleep 1
    done
    
    AG_IDX=$((AG_IDX + 1))
    echo "[$(date '+%H:%M:%S')] Starting airgap $ag mm ($AG_IDX/${#AIRGAPS[@]})..."
    python scripts/analyze_magnet_signal.py --config "$CONFIG" --airgap "$ag" > /tmp/airgap_${ag}.log 2>&1 &
    PIDS+=("$!")
done

# Wait for all remaining jobs
echo ""
echo "Waiting for all jobs to complete..."
wait

echo ""
echo "✓ All airgaps completed!"
echo "Generated plots: examples/plots/compare_methods_*.png"
echo "Summary: examples/plots/summary_n52_60_fine.json"
