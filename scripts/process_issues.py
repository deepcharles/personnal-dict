#!/usr/bin/env python3
"""Process GitHub issues labelled 'dictionary' and add entries to index.html."""
import json
import os
import subprocess
import sys

import anthropic
import requests

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ.get("GITHUB_REPOSITORY", "deepcharles/personnal-dict")
API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

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
        f"{API}/repos/{REPO}/issues",
        params={"state": "open", "labels": "dictionary", "per_page": 100},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def close_issue(number):
    resp = requests.patch(
        f"{API}/repos/{REPO}/issues/{number}",
        json={"state": "closed"},
        headers=HEADERS,
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


def add_entry_to_json(entry):
    with open("entries.json", encoding="utf-8") as f:
        entries = json.load(f)
    entries.append(entry)
    with open("entries.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate():
    with open("entries.json", encoding="utf-8") as f:
        json.load(f)
    print("OK")


def git_push(entry):
    term = entry.get("term", "entry")
    type_ = entry.get("type", "entry")
    subprocess.run(["git", "add", "entries.json"], check=True)
    subprocess.run(["git", "commit", "-m", f"Add {type_}: {term}"], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)


def main():
    issues = get_issues()
    if not issues:
        print("No pending dictionary issues.")
        sys.exit(0)

    for issue in issues:
        print(f"Processing #{issue['number']}: {issue['title']}")
        try:
            entry = format_entry(issue["title"])
            add_entry_to_json(entry)
            validate()
            git_push(entry)
            close_issue(issue["number"])
            print(f"  Added {entry['type']}: {entry['term']}")
        except Exception as e:
            print(f"  Failed: {e}", file=sys.stderr)
            subprocess.run(["git", "checkout", "index.html"])
            sys.exit(1)


if __name__ == "__main__":
    main()
