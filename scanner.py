import os
import time
import datetime
import argparse

def scan_vault(vault_path, days=7):
    """
    Scans the Obsidian vault for markdown files modified in the last N days.
    """
    print(f"Scanning vault: {vault_path}")
    print(f"Time window: Last {days} days")
    
    now = time.time()
    cutoff_time = now - (days * 86400)
    
    modified_files = []
    
    for root, dirs, files in os.walk(vault_path):
        # Ignore .git or .obsidian folders
        if '.git' in dirs:
            dirs.remove('.git')
        if '.obsidian' in dirs:
            dirs.remove('.obsidian')
            
        for file in files:
            if not file.endswith('.md'):
                continue
                
            file_path = os.path.join(root, file)
            try:
                stat = os.stat(file_path)
                mtime = stat.st_mtime
                ctime = stat.st_ctime
                
                if mtime > cutoff_time:
                    modified_files.append({
                        'path': file_path,
                        'rel_path': os.path.relpath(file_path, vault_path),
                        'mtime': mtime,
                        'ctime': ctime
                    })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    # Sort by modification time, newest first
    modified_files.sort(key=lambda x: x['mtime'], reverse=True)
    
    return modified_files

def generate_report_context(files):
    """
    Generates a context string for the AI prompt.
    """
    context = []
    for f in files:
        mtime_str = datetime.datetime.fromtimestamp(f['mtime']).strftime('%Y-%m-%d %H:%M:%S')
        action = "Created" if abs(f['mtime'] - f['ctime']) < 60 else "Modified"
        
        # Read content snippet (first 500 chars)
        content = ""
        for encoding in ['utf-8', 'utf-16', 'gbk', 'latin-1']:
            try:
                with open(f['path'], 'r', encoding=encoding) as file:
                    content = file.read(500).strip()
                    # Remove empty lines
                    content = "\n".join([line for line in content.splitlines() if line.strip()])
                break
            except UnicodeError:
                continue
            except Exception as e:
                content = f"[Error reading content: {e}]"
                break
        
        if not content:
             content = "[Error: Unable to decode file content]"
            
        context.append(f"### [{action}] {f['rel_path']} ({mtime_str})")
        context.append(f"Content Snippet:\n{content}\n")
        
    return "\n".join(context)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obsidian Weekly Scanner')
    parser.add_argument('--vault', type=str, default='.', help='Path to Obsidian Vault')
    parser.add_argument('--days', type=int, default=7, help='Days to look back')
    
    args = parser.parse_args()
    
    files = scan_vault(args.vault, args.days)
    print(f"Found {len(files)} modified files.")
    
    if files:
        print("\n--- Context for AI ---\n")
        context = generate_report_context(files)
        print(context)
        
        # In a real app, we would send 'context' to an LLM here.
        print("\n--- End Context ---")
        print("\n[Mock] Sending to AI... Done.")
        print(f"[Mock] Generating report for {len(files)} notes.")
    else:
        print("No files modified in the specified period.")
