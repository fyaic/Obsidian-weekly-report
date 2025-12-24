import os
import json
import time
import datetime
import argparse

STATE_FILE = "state.json"
LOG_FILE = "weekly_log.jsonl"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"last_scan": 0}

def save_state(last_scan):
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_scan": last_scan}, f)

def mock_ai_summarize(content, filename):
    """
    Mock AI function to summarize content.
    In production, this would call an LLM API.
    """
    # Simple heuristic summary for prototype
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return "Empty note."
    
    summary = f"Note '{filename}' update. "
    if len(lines) > 0:
        summary += f"Main topic seems to be about '{lines[0][:50]}...'. "
    summary += f"Contains {len(lines)} lines of text."
    return summary

def scan_and_summarize(vault_path, days_back=None):
    state = load_state()
    last_scan = state['last_scan']
    current_time = time.time()
    
    # If days_back is specified, override last_scan
    if days_back is not None:
        last_scan = current_time - (days_back * 86400)
        print(f"Manual override: Scanning last {days_back} days.")
    
    print(f"Scanning changes since: {datetime.datetime.fromtimestamp(last_scan)}")
    
    new_logs = []
    
    for root, dirs, files in os.walk(vault_path):
        # Ignore hidden folders
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            # NOTE: Currently supports Markdown files (Obsidian default). 
            # You can add other extensions (e.g., .txt, .org) if you use a different knowledge base system.
            if not file.endswith('.md'):
                continue
                
            file_path = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(file_path)
                
                if mtime > last_scan:
                    # File modified since last scan
                    print(f"Processing: {file}")
                    
                    # Read content
                    content = ""
                    for encoding in ['utf-8', 'utf-16', 'gbk', 'latin-1']:
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read()
                            break
                        except UnicodeError:
                            continue
                    
                    if not content:
                        print(f"  Warning: Could not read {file}")
                        continue
                        
                    # Generate Summary
                    summary = mock_ai_summarize(content, file)
                    
                    # Create log entry
                    log_entry = {
                        "timestamp": current_time,
                        "date_str": datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S'),
                        "file_path": file_path,
                        "rel_path": os.path.relpath(file_path, vault_path),
                        "action": "update", # Simplification
                        "summary": summary
                    }
                    new_logs.append(log_entry)
                    
            except Exception as e:
                print(f"Error processing {file}: {e}")
                
    # Append to log file
    if new_logs:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            for entry in new_logs:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"Logged {len(new_logs)} updates.")
    else:
        print("No changes found.")
        
    # Update state
    save_state(current_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan Obsidian vault for changes and generate daily summaries.")
    parser.add_argument("--vault", required=True, help="Path to Obsidian Vault")
    parser.add_argument("--days", type=int, help="Scan changes from last N days (overrides state)")
    args = parser.parse_args()
    
    scan_and_summarize(args.vault, args.days)
