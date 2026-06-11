#!/usr/bin/env python3
"""Weekly Google Scholar -> publications.yml sync.

Pulls the lab PI's Scholar profile, diffs recent papers against
data/publications.yml, and opens a PR on arpg/arpg-site with any missing
entries. Designed to run from cron; exits 0 with no side effects when
there is nothing new or when a sync PR is already open.
"""

import datetime
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import yaml

SCHOLAR_ID = "lysFu30AAAAJ"
REPO_DIR = Path.home() / "projects" / "arpg-site"
PUBS_FILE = REPO_DIR / "data" / "publications.yml"
# Only consider papers from the last N years: keeps the diff focused on
# genuinely new work and bounds the number of slow per-paper fill() calls.
LOOKBACK_YEARS = 2
PR_BRANCH_PREFIX = "scholar-sync"


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


def run(cmd, **kw):
    log("+ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main():
    this_year = datetime.date.today().year
    cutoff = this_year - LOOKBACK_YEARS

    existing = yaml.safe_load(PUBS_FILE.read_text())
    known = {normalize_title(p["title"]) for p in existing}
    log(f"{len(existing)} existing publications loaded")

    from scholarly import scholarly

    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["publications"])
    pubs = author["publications"]
    log(f"{len(pubs)} publications on Scholar profile")

    candidates = []
    skipped_old = 0
    for pub in pubs:
        bib = pub.get("bib", {})
        title = bib.get("title", "").strip()
        year = bib.get("pub_year")
        if not title or not year:
            continue
        year = int(year)
        if normalize_title(title) in known:
            continue
        if year < cutoff:
            skipped_old += 1
            continue
        candidates.append(pub)

    log(f"{len(candidates)} new candidate(s) since {cutoff}; "
        f"{skipped_old} older unmatched entries ignored")
    if not candidates:
        log("Nothing to do.")
        return 0

    # Bail out if a previous sync PR is still open, instead of stacking PRs.
    open_prs = run(["gh", "pr", "list", "--repo", "arpg/arpg-site",
                    "--state", "open", "--search", PR_BRANCH_PREFIX,
                    "--json", "number"]).stdout
    if open_prs.strip() not in ("", "[]"):
        log("A scholar-sync PR is already open; skipping until it is resolved.")
        return 0

    new_entries = []
    for pub in candidates:
        try:
            filled = scholarly.fill(pub)
        except Exception as e:  # noqa: BLE001 - per-paper fill is best-effort
            log(f"fill() failed for '{pub['bib'].get('title')}': {e}")
            filled = pub
        bib = filled.get("bib", {})
        entry = {
            "title": bib.get("title", "").strip(),
            "authors": reformat_authors(bib.get("author", "")) or "TBD",
            "venue": venue_from_citation(bib),
            "year": int(bib.get("pub_year")),
            "url": filled.get("pub_url")
                or f"https://scholar.google.com/citations?user={SCHOLAR_ID}",
        }
        new_entries.append(entry)
        log(f"new: {entry['year']} | {entry['title'][:70]}")

    # Prepend new entries (site template groups by year, order is cosmetic).
    def fmt(e):
        title = e["title"].replace('"', '\\"')
        authors = e["authors"].replace('"', '\\"')
        venue = str(e["venue"]).replace('"', '\\"')
        return (f'- title: "{title}"\n'
                f'  authors: "{authors}"\n'
                f'  venue: "{venue}"\n'
                f'  year: {e["year"]}\n'
                f'  url: {e["url"]}\n')

    block = "\n".join(fmt(e) for e in new_entries)
    branch = f"{PR_BRANCH_PREFIX}-{datetime.date.today():%Y%m%d}"

    run(["git", "-C", str(REPO_DIR), "fetch", "origin", "main"])
    run(["git", "-C", str(REPO_DIR), "worktree", "add", "-B", branch,
         f"/tmp/{branch}", "origin/main"])
    try:
        wt_pubs = Path(f"/tmp/{branch}") / "data" / "publications.yml"
        wt_pubs.write_text(block + "\n" + wt_pubs.read_text())
        # Validate the result parses before pushing.
        yaml.safe_load(wt_pubs.read_text())

        run(["git", "-C", f"/tmp/{branch}", "add", "data/publications.yml"])
        run(["git", "-C", f"/tmp/{branch}", "commit", "-m",
             f"Add {len(new_entries)} publication(s) from Google Scholar sync"])
        run(["git", "-C", f"/tmp/{branch}", "push", "-f", "origin", branch])

        titles = "\n".join(f"- **{e['year']}** {e['title']} ({e['venue']})"
                           for e in new_entries)
        body = (f"Automated weekly Google Scholar sync found "
                f"{len(new_entries)} publication(s) not in `publications.yml`:\n\n"
                f"{titles}\n\n"
                "Scholar metadata is noisy - please check authors/venue/url "
                "before merging. Merging deploys the site automatically.")
        run(["gh", "pr", "create", "--repo", "arpg/arpg-site",
             "--head", branch, "--base", "main",
             "--title", f"Scholar sync: {len(new_entries)} new publication(s)",
             "--body", body])
        log("PR opened.")
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
