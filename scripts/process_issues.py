#!/usr/bin/env python3
"""Process a GitHub dictionary issue and add the entry to entries.json."""
import json
import os
import subprocess
import sys

import requests

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ.get("GITHUB_REPOSITORY", "deepcharles/personnal-dict")
ISSUE_NUMBER = os.environ["ISSUE_NUMBER"]
ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


def fetch_issue():
    """Fetch issue body from API (needed for workflow_dispatch where env var is empty)."""
    if ISSUE_BODY.strip():
        return ISSUE_BODY
    resp = requests.get(f"{API}/repos/{REPO}/issues/{ISSUE_NUMBER}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["body"] or ""


def parse_form(body):
    """Parse GitHub issue form body into a dict of field -> value."""
    sections = {}
    current = None
    for line in body.splitlines():
        if line.startswith("### "):
            current = line[4:].strip().lower()
            sections[current] = []
        elif current is not None:
            stripped = line.strip()
            if stripped and stripped != "_No response_":
                sections[current].append(stripped)
    return {k: " ".join(v) for k, v in sections.items() if v}


def build_entry(fields):
    """Build a dictionary entry object from parsed form fields."""
    type_ = fields.get("type", "word").strip().lower()
    term = fields.get("term", "").strip().lower()
    lang = fields.get("lang", fields.get("language", "en")).strip().lower()

    if not term:
        raise ValueError("Term is required")

    entry = {"type": type_, "term": term, "lang": lang}

    if type_ == "word":
        pron = fields.get("pronunciation (ipa)", fields.get("pronunciation", "")).strip()
        if pron:
            entry["pronunciation"] = pron
        slug = term.replace(" ", "-")
        if lang == "fr":
            entry["cambridge"] = f"https://dictionary.cambridge.org/pronunciation/french-english/{slug}"
        else:
            entry["cambridge"] = f"https://dictionary.cambridge.org/pronunciation/english/{slug}"

    meaning = fields.get("meaning", "").strip()
    if meaning and type_ != "quote":
        entry["meaning"] = meaning

    attribution = fields.get("attribution", "").strip()
    if attribution and type_ == "quote":
        entry["attribution"] = attribution

    example = fields.get("example", "").strip()
    if example:
        entry["example"] = example

    return entry


def add_entry(entry):
    with open("entries.json", encoding="utf-8") as f:
        entries = json.load(f)
    entries.append(entry)
    with open("entries.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


def close_issue():
    requests.patch(
        f"{API}/repos/{REPO}/issues/{ISSUE_NUMBER}",
        json={"state": "closed"},
        headers=HEADERS,
    ).raise_for_status()


def git_push(entry):
    term = entry.get("term", "entry")
    type_ = entry.get("type", "entry")
    subprocess.run(["git", "add", "entries.json"], check=True)
    subprocess.run(["git", "commit", "-m", f"Add {type_}: {term}"], check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)


def main():
    print(f"Processing issue #{ISSUE_NUMBER}")
    try:
        body = fetch_issue()
        fields = parse_form(body)
        entry = build_entry(fields)
        add_entry(entry)
        with open("entries.json", encoding="utf-8") as f:
            json.load(f)  # validate
        git_push(entry)
        close_issue()
        print(f"Added {entry['type']}: {entry['term']}")
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        subprocess.run(["git", "checkout", "entries.json"])
        sys.exit(1)


if __name__ == "__main__":
    main()
