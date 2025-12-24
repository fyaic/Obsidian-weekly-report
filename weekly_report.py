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
    # NOTE: This uses Linear GraphQL API. If you use Jira/Trello, replace this query with their respective REST/GraphQL calls.
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


def extract_topics(filenames):
    """
    Simple heuristic to extract topics from a list of filenames.
    It splits by non-alphanumeric chars, filters small words, and returns top keywords.
    In a real AI scenario, the LLM would summarize these.
    """
    words = []
    ignore_words = {'md', 'the', 'in', 'of', 'a', 'to', 'for', 'on', 'and', 'with', 'by', 'is', 'at', 'md', 'txt', 'file', 'new', 'update', 'untitled', '0', '1', '2', '3'}
    
    for name in filenames:
        # Remove extension
        name = os.path.splitext(name)[0]
        # Split by non-word characters (including Chinese punctuation if possible, but basic regex here)
        # Using a simple regex to catch English words and potentially Chinese sequences if we treat them as blocks
        # For simplicity in this prototype, let's just split by spaces and common punctuation
        tokens = re.split(r'[\s\-_,\.，。：]+', name)
        
        for token in tokens:
            token_clean = token.strip().lower()
            if len(token_clean) > 1 and token_clean not in ignore_words:
                words.append(token) # Keep original case for display if needed, or just use original token
    
    if not words:
        return "Miscellaneous"
        
    # Count frequency
    counter = Counter(words)
    # Get top 3 common words/phrases
    most_common = counter.most_common(3)
    
    topics = [word for word, count in most_common]
    return ", ".join(topics)

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

    # Group by date (optional) or just list them
    print(f"Found {len(logs)} activities. Generating report context...")
    
    # Create the prompt context (Simulation of what we send to AI)
    context = "Here are the summaries of the notes modified this week:\n\n"
    grouped_logs = {}
    for log in logs:
        # Group by top-level folder as "Category"
        folder = os.path.dirname(log['rel_path']).split(os.sep)[0]
        if not folder or folder == ".":
            folder = "Uncategorized"
        
        if folder not in grouped_logs:
            grouped_logs[folder] = []
        grouped_logs[folder].append(log)
        
        context += f"- **{log['rel_path']}** ({log['date_str']}): {log['summary']}\n"
    
    # Mock AI Generation - Constructing response based on new template
    # In a real scenario, this string would be the prompt sent to LLM, and the LLM would return the markdown below.
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    week_num = datetime.datetime.now().strftime('%Y-W%W')
    
    # Simulate "Work Focus" based on most active folders and their topics
    sorted_folders = sorted(grouped_logs.keys(), key=lambda k: len(grouped_logs[k]), reverse=True)
    
    focus_summary = []
    for folder in sorted_folders[:3]: # Top 3 folders
        folder_logs = grouped_logs[folder]
        filenames = [os.path.basename(log['rel_path']) for log in folder_logs]
        topics = extract_topics(filenames)
        count = len(grouped_logs[folder])
        focus_summary.append(f"**{folder}** ({count} files): Focused on *{topics}*")
    
    focus_areas_str = ", ".join(focus_summary)
    
    # Simulate "Outputs" section - Simplified (File names only)
    outputs_section = ""
    for folder, folder_logs in grouped_logs.items():
        outputs_section += f"\n### {folder}\n"
        
        # Get unique filenames
        filenames = sorted(list(set([os.path.basename(log['rel_path']) for log in folder_logs])))
        
        for filename in filenames:
            outputs_section += f"- {filename}\n"

    report_content = f"""# Weekly Review: {week_num}
*Generated by Obsidian AI Assistant on {current_date}*

## 本周工作重心
本周共产生/修改了 **{len(logs)}** 个文件。主要兴趣点集中在：
- {os.linesep.join(['- ' + s for s in focus_summary])}

## 新增/修改内容清单
{outputs_section}

## 知识增量总结
*注：此部分未来将由 AI 阅读上述文件后自动生成，概括核心知识点。*
- **{sorted_folders[0] if sorted_folders else 'General'}**: 本周在此领域投入了最大精力。
- **效率提升**: 通过自动化脚本快速梳理了本周的知识产出。
"""

    # Write Report
    output_file = os.path.join(output_path, f"Weekly_Report_{datetime.datetime.now().strftime('%Y-W%W')}.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"Report generated: {output_file}")

    if publish_linear:
        print("Publishing to Linear...")
        report_title = f"Weekly Review: {week_num}"
        publish_to_linear(report_title, report_content)
    
    # Archive logs (Optional: Rename LOG_FILE to archive/...)
    # os.rename(LOG_FILE, f"logs/archive/weekly_log_{int(time.time())}.jsonl")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Weekly Report Generator')
    parser.add_argument('--output', type=str, default='.', help='Output directory for the report')
    parser.add_argument('--publish-linear', action='store_true', help='Publish the report to Linear')
    args = parser.parse_args()
    
    generate_report(args.output, publish_linear=args.publish_linear)
