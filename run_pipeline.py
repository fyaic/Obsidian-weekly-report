import os
import argparse
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description="Obsidian AI Weekly Pipeline")
    parser.add_argument("--vault", required=True, help="Path to Obsidian Vault")
    parser.add_argument("--days", type=int, help="Scan changes from last N days")
    parser.add_argument("--publish-linear", action="store_true", help="Publish report to Linear")
    args = parser.parse_args()

    print("=== Step 1: Scanning for changes ===")
    cmd_scan = [sys.executable, "daily_summary.py", "--vault", args.vault]
    if args.days:
        cmd_scan.extend(["--days", str(args.days)])
    
    ret = subprocess.call(cmd_scan)
    if ret != 0:
        print("Error in daily_summary.py")
        sys.exit(ret)
        
    print("\n=== Step 2: Generating Weekly Report ===")
    cmd_report = [sys.executable, "weekly_report.py"]
    if args.publish_linear:
        # Check if API KEY is set
        if "LINEAR_API_KEY" not in os.environ:
            print("Warning: LINEAR_API_KEY not found in environment variables.")
            print("Please set it before running with --publish-linear.")
            # We don't exit here, we let weekly_report.py handle it or fail gracefully
        
        cmd_report.append("--publish-linear")
        
    ret = subprocess.call(cmd_report)
    if ret != 0:
        print("Error in weekly_report.py")
        sys.exit(ret)

    print("\n=== Pipeline Completed Successfully ===")

if __name__ == "__main__":
    main()
