"""Run the whole project with one command.

    python -m src.pipeline              # everything
    python -m src.pipeline --step build # just one step: load | build | test | analyze | export

Add ECOM_ENV=sample in front to use the synthetic test data instead.
"""
import argparse
import sys
import time

from src import build, clv, config, data_tests, experiment, export_dashboard_data, load_data, rca

STEPS = ["load", "build", "test", "analyze", "export"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", choices=STEPS, help="run only this step")
    args = ap.parse_args()
    steps = [args.step] if args.step else STEPS

    print(f"=== Running on {'SAMPLE (synthetic)' if config.SAMPLE else 'FULL'} data ===")
    t0 = time.time()
    for step in steps:
        print(f"\n--- {step} ---")
        if step == "load":
            load_data.run()
        elif step == "build":
            build.run()
        elif step == "test":
            if not data_tests.run():
                sys.exit("Data tests failed - fix them before running the analyses.")
        elif step == "analyze":
            rca.run()
            print()
            clv.run()
            print()
            experiment.run()
        elif step == "export":
            export_dashboard_data.run()
    print(f"\n=== Done in {time.time() - t0:,.0f}s ===")


if __name__ == "__main__":
    main()
