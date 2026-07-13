#!/usr/bin/env python3
"""Weekly Google Scholar -> publications.yml sync.

Pulls the lab PI's Scholar profile and opens a review PR on arpg/arpg-site that:
  * ADDS papers missing from data/publications.yml, and
  * UPGRADES entries we hold only as a preprint (arXiv/CoRR) to their published
    version once Scholar shows one (replaces the preprint entry in place).

Designed to run from cron; exits 0 with no side effects when there is nothing to
do or when a sync PR is already open. Pass --dry-run to classify + preview the
resulting file without touching git/GitHub.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

SCHOLAR_ID = "lysFu30AAAAJ"
REPO_DIR = Path.home() / "projects" / "arpg-site"
PUBS_FILE = REPO_DIR / "data" / "publications.yml"
# Only consider NEW papers from the last N years: keeps additions focused and
# bounds slow per-paper fill() calls. (Upgrades are not year-gated — a paper's
# published version can appear well after its preprint.)
LOOKBACK_YEARS = 2
PR_BRANCH_PREFIX = "scholar-sync"

# The review PR is opened by the bot account and requests the PI as reviewer,
# so GitHub emails the PI whenever new pubs are found. (GitHub never notifies
# you about PRs you opened yourself, which is why self-authored sync PRs went
# unnoticed for weeks.) crh-bot has write access to arpg/arpg-site.
BOT_USER = "crh-bot"
REVIEWERS = ["crheckman"]

# Scholar surfaces grant awards and other non-papers. Titles listed here
# (matched normalized) are never proposed; extend this set as noise appears.
IGNORE_TITLES = {
    "CAREER: Radar-based Perception and Navigation in Visually Degraded Environments",
}
# Drop anything whose venue looks like a funding award rather than a venue.
AWARD_VENUE_RE = re.compile(r"NSF Award|Award Number|Directorate for", re.I)
# An entry is a "preprint" (upgradeable) if its venue/url looks like one of these.
PREPRINT_RE = re.compile(r"corr|arxiv|preprint|researchsquare|48550", re.I)


def log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def normalize_title(title):
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def reformat_authors(scholar_author_str):
    """Scholar gives 'John Doe and Jane Smith'; site uses 'John Doe, Jane Smith'."""
    return ", ".join(a.strip() for a in scholar_author_str.split(" and ") if a.strip())


def venue_from_citation(bib):
    for key in ("journal", "conference", "venue", "booktitle"):
        if bib.get(key):
            return bib[key]
    cit = bib.get("citation", "")
    # Strip trailing volume/pages/year noise, e.g. "Auton. Robots 12 (3), 45-67, 2024"
    cit = re.sub(r"[\s,]*\d[\d\s()\-–,:]*$", "", cit).strip()
    return cit or "TBD"


def is_preprint(venue, url):
    """True if this entry is a preprint (arXiv/CoRR/etc.) rather than published."""
    return bool(PREPRINT_RE.search(f"{venue} {url}"))


def build_entry(filled):
    """Turn a filled Scholar publication into a publications.yml entry dict."""
    bib = filled.get("bib", {})
    return {
        "title": bib.get("title", "").strip(),
        "authors": reformat_authors(bib.get("author", "")) or "TBD",
        "venue": venue_from_citation(bib),
        "year": int(bib.get("pub_year")),
        "url": filled.get("pub_url")
            or f"https://scholar.google.com/citations?user={SCHOLAR_ID}",
    }


def fmt_entry(e):
    """Serialize an entry dict to the publications.yml block format (5 lines)."""
    title = e["title"].replace('"', '\\"')
    authors = e["authors"].replace('"', '\\"')
    venue = str(e["venue"]).replace('"', '\\"')
    return (f'- title: "{title}"\n'
            f'  authors: "{authors}"\n'
            f'  venue: "{venue}"\n'
            f'  year: {e["year"]}\n'
            f'  url: {e["url"]}\n')


def split_blocks(text):
    """Split publications.yml into per-entry blocks, preserving exact text so
    that ''.join(blocks) == text. Each entry block starts at a '- title:' line;
    any leading preamble becomes the first (non-entry) block."""
    blocks, cur = [], []
    for ln in text.splitlines(keepends=True):
        if ln.startswith("- title:") and cur:
            blocks.append("".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blocks.append("".join(cur))
    return blocks


def block_field(block, key):
    m = re.search(rf'^\s*-?\s*{re.escape(key)}:\s*"?(.*?)"?\s*$', block, re.M)
    return m.group(1) if m else ""


def apply_updates(text, additions, upgrades):
    """Return new file text: each block whose title is in `upgrades` is replaced
    by that entry's published version (extra copies of an upgraded title are
    dropped); `additions` are prepended. Unchanged blocks are kept byte-for-byte.

    upgrades: {normalized_title: entry_dict}
    additions: [entry_dict, ...]
    """
    out, done = [], set()
    for b in split_blocks(text):
        nt = normalize_title(block_field(b, "title"))
        if nt and nt in upgrades:
            if nt in done:
                continue  # drop any extra preprint copies of an upgraded title
            done.add(nt)
            trailing = "\n" * (len(b) - len(b.rstrip("\n")))  # preserve separators
            out.append(fmt_entry(upgrades[nt]).rstrip("\n") + trailing)
        else:
            out.append(b)
    prefix = "".join(fmt_entry(e).rstrip("\n") + "\n\n" for e in additions)
    return prefix + "".join(out)


def run(cmd, **kw):
    log("+ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def bot_env():
    """Env that makes `gh` authenticate as the bot account, so the review PR is
    authored by the bot and GitHub will email the PI on the review request."""
    token = subprocess.run(
        ["gh", "auth", "token", "--user", BOT_USER],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    env["GH_HOST"] = "github.com"
    return env


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    this_year = datetime.date.today().year
    cutoff = this_year - LOOKBACK_YEARS

    # Dedup against origin/main — the exact ref the PR is branched from — NOT the
    # local working copy. After a sync PR merges on GitHub, nobody pulls the local
    # repo, so a local read goes stale and re-proposes already-merged papers.
    run(["git", "-C", str(REPO_DIR), "fetch", "origin", "main"])
    base_text = run(["git", "-C", str(REPO_DIR), "show",
                     "origin/main:data/publications.yml"]).stdout
    existing = yaml.safe_load(base_text)

    known = {normalize_title(p["title"]) for p in existing}
    ignore_norm = {normalize_title(t) for t in IGNORE_TITLES}

    # A title is "upgradeable" if every existing entry for it is a preprint (no
    # published version yet). Those are the ones we watch to swap in the
    # published version when Scholar shows it.
    by_title = defaultdict(list)
    for p in existing:
        by_title[normalize_title(p["title"])].append(p)
    upgradeable = {
        nt for nt, ps in by_title.items()
        if all(is_preprint(p.get("venue", ""), p.get("url", "")) for p in ps)
    }
    log(f"{len(existing)} existing publications loaded from origin/main "
        f"({len(upgradeable)} preprint-only, watched for upgrades)")

    from scholarly import scholarly

    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["publications"])
    pubs = author["publications"]
    log(f"{len(pubs)} publications on Scholar profile")

    add_pubs, upgrade_pubs, skipped_old = [], [], 0
    for pub in pubs:
        bib = pub.get("bib", {})
        title = bib.get("title", "").strip()
        year = bib.get("pub_year")
        if not title or not year:
            continue
        n = normalize_title(title)
        year = int(year)
        if n in ignore_norm:
            log(f"ignored (non-paper/grant): {title[:70]}")
            continue
        if n in upgradeable:
            upgrade_pubs.append(pub)          # existing copy is preprint-only
            continue
        if n in known:
            continue                          # already have a published version
        if year < cutoff:
            skipped_old += 1
            continue
        add_pubs.append(pub)

    log(f"{len(add_pubs)} new candidate(s), {len(upgrade_pubs)} upgrade candidate(s); "
        f"{skipped_old} older unmatched entries ignored")
    if not add_pubs and not upgrade_pubs:
        log("Nothing to do.")
        return 0

    # If a previous sync PR is still open, bail before the expensive fill() calls.
    # Match on the head branch (scholar-sync-*), NOT a fuzzy text search — an
    # unrelated PR that merely mentions "scholar sync" must not block the run.
    gh = None
    if not dry_run:
        gh = bot_env()
        open_json = run(["gh", "pr", "list", "--repo", "arpg/arpg-site",
                         "--state", "open", "--json", "number,headRefName"], env=gh).stdout
        open_sync = [p for p in json.loads(open_json or "[]")
                     if p["headRefName"].startswith(PR_BRANCH_PREFIX + "-")]
        if open_sync:
            log(f"A scholar-sync PR is already open (#{open_sync[0]['number']}); "
                "skipping until it is resolved.")
            return 0

    def safe_fill(pub):
        try:
            return scholarly.fill(pub)
        except Exception as e:  # noqa: BLE001 - per-paper fill is best-effort
            log(f"fill() failed for '{pub['bib'].get('title')}': {e}")
            return pub

    # --- Additions: genuinely new papers ---
    additions, seen = [], set()
    for pub in add_pubs:
        e = build_entry(safe_fill(pub))
        if AWARD_VENUE_RE.search(str(e["venue"])):
            log(f"ignored (award-like venue '{e['venue'][:40]}'): {e['title'][:55]}")
            continue
        n = normalize_title(e["title"])
        if n in seen:
            log(f"dropped duplicate title within this batch: {e['title'][:55]}")
            continue
        seen.add(n)
        additions.append(e)
        log(f"new: {e['year']} | {e['title'][:70]}")

    # --- Upgrades: preprint-only entries that Scholar now shows as published ---
    upgrades = {}
    for pub in upgrade_pubs:
        e = build_entry(safe_fill(pub))
        if AWARD_VENUE_RE.search(str(e["venue"])):
            continue
        if is_preprint(e["venue"], e["url"]):
            log(f"still preprint on Scholar, no upgrade yet: {e['title'][:55]}")
            continue
        nt = normalize_title(e["title"])
        upgrades[nt] = e
        old = by_title[nt][0]
        log(f"upgrade: {e['title'][:50]} | {old.get('venue')} -> {e['venue']} ({e['year']})")

    if not additions and not upgrades:
        log("All candidates filtered out; nothing to do.")
        return 0

    new_text = apply_updates(base_text, additions, upgrades)
    yaml.safe_load(new_text)  # validate before writing/pushing

    # Human-readable summary for commit + PR.
    parts = []
    if additions:
        parts.append(f"add {len(additions)}")
    if upgrades:
        parts.append(f"upgrade {len(upgrades)} preprint→published")
    summary = ", ".join(parts)

    if dry_run:
        preview = Path("/tmp/scholar_sync_preview.yml")
        preview.write_text(new_text)
        log(f"[dry-run] would open PR: Scholar sync: {summary}")
        for e in additions:
            log(f"[dry-run]   NEW      {e['year']} {e['title'][:60]} ({e['venue']})")
        for nt, e in upgrades.items():
            log(f"[dry-run]   UPGRADE  {by_title[nt][0].get('venue')} -> "
                f"{e['venue']} | {e['title'][:55]}")
        log(f"[dry-run] resulting file written to {preview} "
            f"({len(existing)} -> {len(yaml.safe_load(new_text))} entries)")
        return 0

    branch = f"{PR_BRANCH_PREFIX}-{datetime.date.today():%Y%m%d}"
    # origin/main already fetched at the top (same ref the base_text came from).
    run(["git", "-C", str(REPO_DIR), "worktree", "add", "-B", branch,
         f"/tmp/{branch}", "origin/main"])
    try:
        wt_pubs = Path(f"/tmp/{branch}") / "data" / "publications.yml"
        wt_pubs.write_text(new_text)

        run(["git", "-C", f"/tmp/{branch}", "add", "data/publications.yml"])
        run(["git", "-C", f"/tmp/{branch}", "commit", "-m",
             f"Scholar sync: {summary}"])
        run(["git", "-C", f"/tmp/{branch}", "push", "-f", "origin", branch])

        lines = []
        if additions:
            lines.append(f"**{len(additions)} new publication(s):**")
            lines += [f"- **{e['year']}** {e['title']} ({e['venue']})" for e in additions]
        if upgrades:
            lines.append(f"\n**{len(upgrades)} preprint(s) upgraded to published version:**")
            for nt, e in upgrades.items():
                old_venue = by_title[nt][0].get("venue")
                lines.append(f"- {e['title']} — {old_venue} → **{e['venue']}** ({e['year']})")
        body = (
            "Automated Google Scholar sync.\n\n"
            + "\n".join(lines)
            + "\n\nScholar metadata is noisy - please check authors/venue/url before "
            "merging. Merging deploys the site automatically.\n\n"
            f"_Opened by @{BOT_USER}; {', '.join('@'+r for r in REVIEWERS)} "
            "requested as reviewer so this lands in your inbox._"
        )
        run(["gh", "pr", "create", "--repo", "arpg/arpg-site",
             "--head", branch, "--base", "main",
             "--title", f"Scholar sync: {summary}",
             "--body", body,
             "--reviewer", ",".join(REVIEWERS)], env=gh)
        log(f"PR opened by {BOT_USER}; review requested from {', '.join(REVIEWERS)}.")
    finally:
        subprocess.run(["git", "-C", str(REPO_DIR), "worktree", "remove",
                        "--force", f"/tmp/{branch}"], capture_output=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
