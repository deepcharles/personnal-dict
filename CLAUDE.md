# Personal Dictionary — project guide for Claude Code

This repo is a static personal dictionary website, hosted on GitHub Pages at
`deepcharles.github.io/personnal-dict`. It holds words, idioms, and quotes
in English, French, and Arabic, each with the owner's own example of use.

## Your job

The owner will ask you, in plain language, to add entries (e.g. "add the word
*ephemeral*" or "add this quote from The Wire"). For each request you should:

1. Add the entry/entries to the `ENTRIES` array in `index.html` (see schema + location below).
2. Validate the embedded JSON:
   ```bash
   python3 -c "import json,re; s=open('index.html',encoding='utf-8').read(); json.loads(re.search(r'\nENTRIES = (\[[\s\S]*?\n\]);', s).group(1)); print('OK')"
   ```
3. Commit with a clear message (e.g. `Add word: ephemeral`).
4. Push to the default branch (`main`).

Do these without asking for confirmation on routine additions. Ask only if a
request is ambiguous or would delete/overwrite existing entries.

## Where the data lives

Entries are inlined directly in `index.html` as a JavaScript array assigned to
`ENTRIES` (search for `ENTRIES = [` to locate it). Each element of the array is
a JSON-compatible object following the schema below. Add new entries inside that
array — order within it does not matter.

The switch from `entries.json` to inline data was made to avoid UTF-8 encoding
corruption in the GitLab Pages CI pipeline.

## Entry schema

Every entry is an object with a `type` of `"word"`, `"idiom"`, or `"quote"`.

Common fields:
- `type` — "word" | "idiom" | "quote" (required)
- `term` — the headword, phrase, or quote text (required)
- `lang` — "en" | "fr" | "ar" (required for words/idioms; optional for quotes)
- `meaning` — a short definition (words & idioms)
- `example` — the owner's own sentence showing the term in use (optional but encouraged)

Words additionally get:
- `pronunciation` — IPA in slashes, e.g. `/ɪˈfem.ər.əl/`
- `cambridge` — link to the Cambridge pronunciation entry, e.g.
  `https://dictionary.cambridge.org/pronunciation/english/ephemeral`

Quotes use instead of `meaning`:
- `attribution` — who said/wrote it, e.g. `Slim Charles, The Wire`

Rules:
- WORDS get IPA pronunciation AND a Cambridge link. Idioms and quotes do NOT.
- If the owner gives a respelling (e.g. "un-BLEM-isht"), convert it to proper IPA.
- Lowercase headwords for words/idioms unless a proper noun.
- Verify the Cambridge URL follows the pattern
  `https://dictionary.cambridge.org/pronunciation/english/<word>` (or
  `/french-english/<word>` for French). If unsure a page exists, still follow the
  pattern; the owner can correct dead links.

## Example entries

```json
{
  "type": "word",
  "term": "ephemeral",
  "lang": "en",
  "pronunciation": "/ɪˈfem.ər.əl/",
  "cambridge": "https://dictionary.cambridge.org/pronunciation/english/ephemeral",
  "meaning": "lasting for only a short time",
  "example": "The mural was ephemeral — washed away by the first heavy rain."
}
```
```json
{
  "type": "idiom",
  "term": "the cut of someone's jib",
  "lang": "en",
  "meaning": "the typical way someone behaves or presents themselves",
  "example": "I like the cut of her jib."
}
```
```json
{
  "type": "quote",
  "term": "The game's the same, just got more fierce.",
  "lang": "en",
  "attribution": "Slim Charles, The Wire"
}
```

## Encoding — important

IPA and Arabic characters are multi-byte UTF-8. `index.html` must stay valid
UTF-8. Write IPA and Arabic directly (e.g. `/ʌnˈblem.ɪʃt/`); never let it
get re-encoded to Latin-1 (mojibake like `/ÊŒnËˆblem.ÉªÊƒt/`).

Because the data is now inlined in `index.html`, GitLab Pages serves it
as-is — the CI pipeline no longer processes the data, so runner locale is no
longer a risk. If mojibake ever appears, the source file itself is the culprit;
check with `file index.html` (should report UTF-8) and fix the editor/tool that
corrupted it.

## Deployment

The repo is on GitHub at `github.com/deepcharles/personnal-dict`. Pushing to
`main` triggers GitHub Pages to rebuild the site. After a push, the change will
be live at `deepcharles.github.io/personnal-dict` once the Pages build finishes.

New entries can also be added by opening a GitHub issue with the `dictionary`
label. A scheduled GitHub Actions workflow (`process-issues.yml`) runs hourly,
calls the Anthropic API to format the entry, commits it, and closes the issue.
