#!/usr/bin/env python3
"""Parallel batch runner: Execute all airgaps in independent background jobs."""

import argparse
import subprocess
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from common_config import load_config


def main():
    parser = argparse.ArgumentParser(description="Run magnetic field analysis across all airgaps in parallel")
    parser.add_argument("config", help="Config YAML file")
    parser.add_argument("--max-jobs", type=int, default=4, help="Max concurrent jobs (default: 4)")
    parser.add_argument("--verbose", action="store_true", help="Show job output")
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}")
        sys.exit(1)

    cfg = load_config(str(config_path))

    # Generate airgap values
    airgap_min = cfg.get("airgap_min_mm", 0.5)
    airgap_max = cfg.get("airgap_max_mm", 8.0)
    airgap_steps = cfg.get("airgap_steps", 16)
    airgaps = np.linspace(airgap_min, airgap_max, airgap_steps)

    print(f"Running analysis for {len(airgaps)} airgaps (max {args.max_jobs} parallel)...")
    print(f"Airgaps: {', '.join(f'{ag:.2f}' for ag in airgaps)}")
    print()

    # Track background processes
    processes = {}
    completed = 0

    for idx, ag in enumerate(airgaps):
        # Wait if we've reached max parallel jobs
        while len(processes) >= args.max_jobs:
            # Check for completed processes
            for ag_key, proc in list(processes.items()):
                if proc.poll() is not None:
                    if proc.returncode == 0:
                        print(f"[{time.strftime('%H:%M:%S')}] ✓ airgap {ag_key:.2f} mm completed")
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] ✗ airgap {ag_key:.2f} mm failed (exit code {proc.returncode})")
                    del processes[ag_key]
                    completed += 1
            time.sleep(0.5)

        # Start new job
        cmd = [
            sys.executable,
            "scripts/analyze_magnet_signal.py",
            "--config", str(config_path),
            "--airgap", f"{ag:.2f}"
        ]
        
        log_file = Path("/tmp") / f"airgap_{ag:.2f}.log"
        print(f"[{time.strftime('%H:%M:%S')}] Starting airgap {ag:.2f} mm ({idx+1}/{len(airgaps)})...")
        
        with open(log_file, "w") as logf:
            proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        
        processes[ag] = proc

    # Wait for all remaining processes
    print()
    print("Waiting for all jobs to complete...")
    
    while processes:
        for ag_key, proc in list(processes.items()):
            if proc.poll() is not None:
                if proc.returncode == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] ✓ airgap {ag_key:.2f} mm completed")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] ✗ airgap {ag_key:.2f} mm failed (exit code {proc.returncode})")
                del processes[ag_key]
                completed += 1
        if processes:
            time.sleep(1)

    print()
    print(f"✓ All {len(airgaps)} airgaps completed!")
    print(f"Generated plots: examples/plots/compare_methods_*.png")
    print(f"Summary: {cfg.get('summary_path', 'examples/plots/summary.json')}")


if __name__ == "__main__":
    main()
