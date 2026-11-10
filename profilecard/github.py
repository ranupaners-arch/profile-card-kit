"""GitHub GraphQL helpers: profile stats and per-repo lines of code (cached)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.github.com/graphql"


def token() -> str:
    """Read the token from the environment. It is never written to disk."""
    t = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        sys.exit("ERROR: set ACCESS_TOKEN (a PAT) or GITHUB_TOKEN in the environment.")
    return t


def gql(query: str, variables: dict, attempts: int = 3) -> dict:
    """POST a GraphQL query. Retries network errors and 5xx (large repos often 502 once)."""
    problem = "unknown error"
    for attempt in range(attempts):
        try:
            r = requests.post(API, json={"query": query, "variables": variables},
                              headers={"Authorization": f"bearer {token()}"}, timeout=60)
        except requests.RequestException as e:
            problem = f"network error: {e}"
        else:
            if r.status_code == 401:
                raise RuntimeError("GitHub rejected the token (401). Check ACCESS_TOKEN / GITHUB_TOKEN.")
            if r.status_code != 200 and r.status_code < 500:
                raise RuntimeError(f"GraphQL {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                data = r.json()
                if data.get("errors"):
                    raise RuntimeError(f"GraphQL: {json.dumps(data['errors'])[:200]}")
                return data["data"]
            problem = f"HTTP {r.status_code}"
        if attempt + 1 < attempts:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GitHub API request failed after {attempts} attempts ({problem}).")


def user_info(username: str) -> dict:
    q = """query($login: String!) { user(login: $login) {
        id followers { totalCount }
        owned: repositories(ownerAffiliations: OWNER) { totalCount }
    } }"""
    u = gql(q, {"login": username})["user"]
    return {"id": u["id"], "followers": u["followers"]["totalCount"], "repos": u["owned"]["totalCount"]}


def all_repos(username: str, affiliations: str) -> list[dict]:
    q = """query($login: String!, $cursor: String) { user(login: $login) {
        repositories(first: 100, after: $cursor, ownerAffiliations: %s) {
          pageInfo { hasNextPage endCursor }
          nodes { nameWithOwner stargazerCount
                  defaultBranchRef { target { ... on Commit { oid history { totalCount } } } } }
    } } }""" % affiliations
    repos, cursor = [], None
    while True:
        page = gql(q, {"login": username, "cursor": cursor})["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos
        cursor = page["pageInfo"]["endCursor"]


def repo_loc(name: str, author_id: str) -> tuple[int, int, int]:
    """(additions, deletions, commits) by the author on the repo's default branch."""
    owner, repo = name.split("/", 1)
    q = """query($owner: String!, $repo: String!, $id: ID!, $cursor: String) {
      repository(owner: $owner, name: $repo) { defaultBranchRef { target { ... on Commit {
        history(first: 100, after: $cursor, author: {id: $id}) {
          totalCount pageInfo { hasNextPage endCursor } nodes { additions deletions }
    } } } } } }"""
    add = dele = commits = 0
    cursor = None
    while True:
        ref = gql(q, {"owner": owner, "repo": repo, "id": author_id, "cursor": cursor})["repository"]["defaultBranchRef"]
        if not ref:
            return 0, 0, 0
        h = ref["target"]["history"]
        commits = h["totalCount"]
        for n in h["nodes"]:
            add += n["additions"]
            dele += n["deletions"]
        if not h["pageInfo"]["hasNextPage"]:
            return add, dele, commits
        cursor = h["pageInfo"]["endCursor"]


def loc_query(username: str, repos: list[dict], author_id: str, cache_dir: Path) -> tuple[int, int, int]:
    """Total (+, -, commits). A repo is recounted only when its HEAD changed.

    The cache is keyed by hashed repo name, so private repo names never reach the file.
    """
    cache_dir.mkdir(exist_ok=True)
    path = cache_dir / (hashlib.sha256(username.encode()).hexdigest() + ".json")
    cache = json.loads(path.read_text()) if path.exists() else {}
    fresh = {}
    for r in repos:
        ref = r.get("defaultBranchRef")
        if not ref or not ref.get("target"):
            continue
        name, oid = r["nameWithOwner"], ref["target"]["oid"]
        h = hashlib.sha256(name.encode()).hexdigest()
        hit = cache.get(h)
        if hit and hit["oid"] == oid:
            fresh[h] = hit
            continue
        try:
            a, d, c = repo_loc(name, author_id)
        except RuntimeError as e:
            print(f"skipping {h[:8]}: {e}")
            continue
        fresh[h] = {"oid": oid, "additions": a, "deletions": d, "commits": c}
    path.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    return (sum(x["additions"] for x in fresh.values()),
            sum(x["deletions"] for x in fresh.values()),
            sum(x["commits"] for x in fresh.values()))


def contribution_calendar(username: str) -> dict:
    """{date: contribution count} for the last year, as GitHub draws the graph."""
    import datetime as dt
    q = """query($login: String!) { user(login: $login) { contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }"""
    weeks = gql(q, {"login": username})["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {dt.date.fromisoformat(d["date"]): d["contributionCount"]
            for w in weeks for d in w["contributionDays"]}
