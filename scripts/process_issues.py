#!/usr/bin/env python3
"""Process GitLab issues labelled 'dictionary' and add entries to index.html."""
import json
import os
import re
import subprocess
import sys

import anthropic
import requests

GITLAB_URL = os.environ.get("CI_SERVER_URL", "https://plmlab.math.cnrs.fr")
PROJECT_ID = os.environ["CI_PROJECT_ID"]
GITLAB_TOKEN = os.environ["GITLAB_TOKEN"]

SYSTEM_PROMPT = """You convert dictionary issue titles into JSON entry objects for a personal dictionary.

Schema rules:
- type: "word" | "idiom" | "quote" (required)
- term: headword or phrase (required, lowercase unless proper noun)
- lang: "en" | "fr" | "ar" (required for words/idioms)
- meaning: short definition (words & idioms only)
- example: an example sentence showing the term in use (optional)
- Words additionally get:
    pronunciation: IPA in slashes, e.g. /ɪˈfem.ər.əl/
    cambridge: URL following https://dictionary.cambridge.org/pronunciation/english/<term>
               (or /french-english/<term> for French words)
- Quotes use attribution (who said/wrote it) instead of meaning

Rules:
- Words get pronunciation AND cambridge. Idioms and quotes do NOT.
- Return ONLY the raw JSON object — no markdown fences, no explanation."""


def get_issues():
    resp = requests.get(
        f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues",
        params={"state": "opened", "labels": "dictionary", "per_page": 100},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
    )
    resp.raise_for_status()
    return resp.json()


def close_issue(iid):
    resp = requests.put(
        f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues/{iid}",
        params={"state_event": "close"},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
    )
    resp.raise_for_status()


def format_entry(issue_title):
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": issue_title}],
    )
    return json.loads(message.content[0].text)


def add_entry_to_html(entry):
    with open("index.html", encoding="utf-8") as f:
        content = f.read()
    indented = "\n".join(
        "  " + line
        for line in json.dumps(entry, ensure_ascii=False, indent=2).splitlines()
    )
    new_content = re.sub(r"\n\];", f",\n{indented}\n];", content, count=1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_content)


def validate():
    result = subprocess.run(
        ["python3", "-c",
         "import json,re; s=open('index.html',encoding='utf-8').read(); "
         r"json.loads(re.search('\nENTRIES = (\[[\s\S]*?\n\]);', s).group(1)); print('OK')"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr)


def git_push(entry):
    term = entry.get("term", "entry")
    type_ = entry.get("type", "entry")
    subprocess.run(["git", "add", "index.html"], check=True)
    subprocess.run(["git", "commit", "-m", f"Add {type_}: {term} [skip ci]"], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)


def main():
    issues = get_issues()
    if not issues:
        print("No pending dictionary issues.")
        sys.exit(0)

    subprocess.run(["git", "config", "user.email", "claude.ai.engine796@passmail.net"], check=True)
    subprocess.run(["git", "config", "user.name", "deepcharles"], check=True)

    for issue in issues:
        print(f"Processing #{issue['iid']}: {issue['title']}")
        try:
            entry = format_entry(issue["title"])
            add_entry_to_html(entry)
            validate()
            git_push(entry)
            close_issue(issue["iid"])
            print(f"  Added {entry['type']}: {entry['term']}")
        except Exception as e:
            print(f"  Failed: {e}", file=sys.stderr)
            subprocess.run(["git", "checkout", "index.html"])
            sys.exit(1)


if __name__ == "__main__":
    main()
