import json
import datetime
import os
import argparse

import re
from collections import Counter
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LOG_FILE = "weekly_log.jsonl"

def publish_to_linear(title, content):
    """
    Publish the report to Linear as an Issue.
    Requires LINEAR_API_KEY environment variable.
    """
    api_key = os.getenv("LINEAR_API_KEY")
    if not api_key:
        print("Error: LINEAR_API_KEY environment variable not set. Skipping Linear publication.")
        return

    url = "https://api.linear.app/graphql"
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }

    # 1. Get the first Team ID (Assuming user wants to post to the first available team)
    # In a real app, this should be configurable.
    team_query = """
    query {
      teams(first: 1) {
        nodes {
          id
          name
        }
      }
    }
    """
    
    try:
        response = httpx.post(url, headers=headers, json={"query": team_query})
        response.raise_for_status()
        data = response.json()
        
        teams = data.get("data", {}).get("teams", {}).get("nodes", [])
        if not teams:
            print("Error: No Linear teams found. Cannot create issue.")
            return
            
        team_id = teams[0]['id']
        team_name = teams[0]['name']
        print(f"Found Linear Team: {team_name} ({team_id})")
        
    except Exception as e:
        print(f"Error fetching Linear teams: {e}")
        return

    # 2. Create Issue
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          title
          url
        }
      }
    }
    """
    
    variables = {
        "input": {
            "title": title,
            "description": content,
            "teamId": team_id
        }
    }
    
    try:
        response = httpx.post(url, headers=headers, json={"query": mutation, "variables": variables})
        response.raise_for_status()
        result = response.json()
        
        if result.get("data", {}).get("issueCreate", {}).get("success"):
            issue = result["data"]["issueCreate"]["issue"]
            print(f"Successfully published to Linear! Issue URL: {issue['url']}")
        else:
            print(f"Failed to create Linear issue: {result}")
            
    except Exception as e:
        print(f"Error creating Linear issue: {e}")


def extract_topics_and_cluster(logs):
    """
    Extract topics from filenames and group files by these topics.
    Returns a list of (Topic, Count, Files) tuples.
    """
    all_filenames = [os.path.basename(log['rel_path']) for log in logs]
    
    # 1. Tokenize and count
    words = []
    ignore_words = {'md', 'the', 'in', 'of', 'a', 'to', 'for', 'on', 'and', 'with', 'by', 'is', 'at', 'md', 'txt', 'file', 'new', 'update', 'untitled', '0', '1', '2', '3', 'review', 'planning', 'dev'}
    
    file_tokens = {}
    
    for name in all_filenames:
        # Simple splitting by non-alphanumeric chars (matches English words and separate Chinese chars/words if spaced)
        # Improvement: Match specific known high-value keywords (English or Chinese)
        # Or just split by standard delimiters
        clean_name = os.path.splitext(name)[0]
        tokens = re.split(r'[\s\-_,\.，。：]+', clean_name)
        
        valid_tokens = []
        for token in tokens:
            token_clean = token.strip()
            if len(token_clean) > 1 and token_clean.lower() not in ignore_words:
                valid_tokens.append(token_clean)
                words.append(token_clean)
        
        file_tokens[name] = valid_tokens

    if not words:
        return []

    # 2. Find top keywords
    counter = Counter(words)
    most_common = counter.most_common(5) # Top 5 keywords
    
    clusters = []
    processed_files = set()
    
    for keyword, count in most_common:
        # Find files containing this keyword
        related_files = []
        for name, tokens in file_tokens.items():
            if keyword in tokens and name not in processed_files:
                related_files.append(name)
                processed_files.add(name)
        
        if related_files:
            clusters.append((keyword, len(related_files), related_files))
            
    return clusters

def generate_report(output_path, publish_linear=False):
    print(f"Reading logs from {LOG_FILE}...")
    
    if not os.path.exists(LOG_FILE):
        print("No logs found. Run daily_summary.py first.")
        return

    logs = []
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    
    if not logs:
        print("Log file is empty.")
        return

    print(f"Found {len(logs)} activities. Generating report context...")
    
    # Analyze Topics
    clusters = extract_topics_and_cluster(logs)
    
    # Generate "Work Focus" section
    focus_summary = []
    if clusters:
        for keyword, count, files in clusters:
            # Simulate "Insightful Expansion"
            # In a real LLM scenario, we would pass the file contents/summaries of these files to the LLM
            # and ask it to write a sentence connecting them.
            
            # Heuristic expansion for prototype:
            top_files = ", ".join([f"*{f}*" for f in files[:2]])
            if len(files) > 2:
                top_files += f" 等 {len(files)} 个文件"
            
            sentence = f"**{keyword}**: 本周重点关注领域，产出 {count} 篇文档。主要涉及 {top_files}。"
            focus_summary.append(sentence)
    else:
        focus_summary.append("**General**: 零散更新，未发现明显聚集的主题。")

    # Generate "Outputs" section (Grouped by folder for reference)
    grouped_logs = {}
    for log in logs:
        folder = os.path.dirname(log['rel_path']).split(os.sep)[0]
        if not folder or folder == ".":
            folder = "Uncategorized"
        if folder not in grouped_logs:
            grouped_logs[folder] = []
        grouped_logs[folder].append(log)

    outputs_section = ""
    for folder, folder_logs in grouped_logs.items():
        outputs_section += f"\n### {folder}\n"
        filenames = sorted(list(set([os.path.basename(log['rel_path']) for log in folder_logs])))
        for filename in filenames:
            outputs_section += f"- {filename}\n"
            
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    week_num = datetime.datetime.now().strftime('%Y-W%W')

    # Calculate date range from logs for the title
    log_dates = []
    for log in logs:
        try:
            # Parse date_str "YYYY-MM-DD HH:MM:SS"
            dt = datetime.datetime.strptime(log['date_str'], '%Y-%m-%d %H:%M:%S')
            log_dates.append(dt)
        except ValueError:
            continue
    
    if log_dates:
        start_date_str = min(log_dates).strftime('%m%d')
        end_date_str = max(log_dates).strftime('%m%d')
        report_title_text = f"Obsidian Weekly Review: {start_date_str}-{end_date_str}"
    else:
        report_title_text = f"Obsidian Weekly Review: {week_num}"

    report_content = f"""*Generated by AIC Agent on {current_date}*

## 本周工作重心
本周共产生/修改了 **{len(logs)}** 个文件。通过 AI 分析，主要知识增量集中在以下领域：

{os.linesep.join(['- ' + s for s in focus_summary])}

> *Generated by Mock LLM: (Identifying high-frequency topics from filenames and summarizing)*

## 新增/修改内容清单
{outputs_section}

## 知识增量总结
*注：此部分未来将由 AI 阅读上述文件后自动生成，概括核心知识点。*
- **{clusters[0][0] if clusters else 'General'}**: 本周在此领域投入了最大精力。
- **效率提升**: 通过自动化脚本快速梳理了本周的知识产出。
"""

    # Write Report
    output_file = os.path.join(output_path, f"Weekly_Report_{datetime.datetime.now().strftime('%Y-W%W')}.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"Report generated: {output_file}")

    if publish_linear:
        print("Publishing to Linear...")
        publish_to_linear(report_title_text, report_content)
    
    # Archive logs (Optional: Rename LOG_FILE to archive/...)
    # os.rename(LOG_FILE, f"logs/archive/weekly_log_{int(time.time())}.jsonl")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Weekly Report Generator')
    parser.add_argument('--output', type=str, default='.', help='Output directory for the report')
    parser.add_argument('--publish-linear', action='store_true', help='Publish the report to Linear')
    args = parser.parse_args()
    
    generate_report(args.output, publish_linear=args.publish_linear)
