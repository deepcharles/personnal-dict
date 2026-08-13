#!/usr/bin/env python3
"""Process a GitHub dictionary issue and add the entry to entries.json."""
import json
import os
import subprocess
import sys
from datetime import date

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


# Arabic letter → IPA mapping (consonants + harakat)
_AR_IPA = {
    'ب':'b','ت':'t','ث':'θ','ج':'dʒ','ح':'ħ','خ':'x','د':'d','ذ':'ð',
    'ر':'r','ز':'z','س':'s','ش':'ʃ','ص':'sˤ','ض':'dˤ','ط':'tˤ','ظ':'ðˤ',
    'ع':'ʕ','غ':'ɣ','ف':'f','ق':'q','ك':'k','ل':'l','م':'m','ن':'n',
    'ه':'h','و':'w','ي':'j','ا':'aː','ى':'aː','ة':'a',
    'أ':'ʔ','إ':'ʔ','آ':'ʔaː','ء':'ʔ','ؤ':'ʔ','ئ':'ʔ',
    'َ':'a','ِ':'i','ُ':'u',  # fatha, kasra, damma
    'ً':'an','ٍ':'in','ٌ':'un',  # tanwin
    'ْ':'',  # sukun
}


def _arabic_to_ipa(text):
    result = []
    for i, c in enumerate(text):
        if c == 'ّ' and result:  # shadda: geminate previous consonant
            result.append(result[-1])
        else:
            result.append(_AR_IPA.get(c, ''))
    ipa = ''.join(result)
    return f'/{ipa}/' if ipa else None


def _english_to_ipa(term):
    try:
        resp = requests.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{term}",
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        for entry in resp.json():
            if entry.get("phonetic"):
                return entry["phonetic"]
            for p in entry.get("phonetics", []):
                if p.get("text"):
                    return p["text"]
    except Exception:
        pass
    return None


def lookup_ipa(term, lang):
    if lang == "en":
        return _english_to_ipa(term)
    if lang == "ar":
        return _arabic_to_ipa(term)
    return None


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
        if not pron:
            pron = lookup_ipa(term, lang) or ""
        if pron:
            entry["pronunciation"] = pron
        if lang == "en":
            slug = term.replace(" ", "-")
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

    entry["date"] = date.today().isoformat()

    return entry


def add_entry(entry):
    with open("entries.json", encoding="utf-8") as f:
        entries = json.load(f)
    entries.append(entry)
    with open("entries.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


LANG_TO_LT = {"en": "en-US", "fr": "fr", "ar": "ar"}


def check_grammar(fields):
    """Run LanguageTool on meaning + example, post findings as issue comment."""
    lang = fields.get("lang", fields.get("language", "en"))
    lt_lang = LANG_TO_LT.get(lang, "en-US")
    targets = {k: fields[k] for k in ("meaning", "example") if fields.get(k)}
    if not targets:
        return

    findings = []
    for field, text in targets.items():
        try:
            resp = requests.post(
                "https://api.languagetool.org/v2/check",
                data={"text": text, "language": lt_lang},
                timeout=10,
            )
            resp.raise_for_status()
            for m in resp.json().get("matches", []):
                o, l = m["offset"], m["length"]
                snippet = text[max(0, o - 10):o + l + 10].strip()
                suggestions = [r["value"] for r in m["replacements"][:3]]
                line = f"- **{field}**: _{m['message']}_ in `{snippet}`"
                if suggestions:
                    line += " → " + ", ".join(f"`{s}`" for s in suggestions)
                findings.append(line)
        except Exception:
            pass

    body = ("**Grammar check** found potential issues:\n\n" + "\n".join(findings)
            if findings else "**Grammar check** ✓ No issues found.")
    requests.post(
        f"{API}/repos/{REPO}/issues/{ISSUE_NUMBER}/comments",
        json={"body": body},
        headers=HEADERS,
    ).raise_for_status()


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
        check_grammar(fields)
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
