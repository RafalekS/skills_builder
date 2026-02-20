"""
GitHub Client - GitHub API wrapper with rate limit awareness and SQLite caching
"""

import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class RateLimit:
    def __init__(self, remaining: int, limit: int, reset_at: datetime):
        self.remaining = remaining
        self.limit     = limit
        self.reset_at  = reset_at

    def __str__(self) -> str:
        return f"API: {self.remaining}/{self.limit}"


class GitHubClient:

    def __init__(self, token: str = "", timeout: int = 10,
                 cache_hours: int = 24, db=None):
        self._token       = token
        self._timeout     = timeout
        self._cache_hours = cache_hours
        self._db          = db
        self.rate_limit: RateLimit | None = None

    @property
    def _headers(self) -> dict:
        h = {
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            h["Authorization"] = f"token {self._token}"
        return h

    def _update_rate_limit(self, resp: requests.Response):
        try:
            remaining = int(resp.headers.get("X-RateLimit-Remaining", -1))
            limit     = int(resp.headers.get("X-RateLimit-Limit", 60))
            reset_ts  = int(resp.headers.get("X-RateLimit-Reset", 0))
            reset_at  = datetime.fromtimestamp(reset_ts) if reset_ts else datetime.utcnow()
            self.rate_limit = RateLimit(remaining, limit, reset_at)
        except Exception:
            pass

    # ── Core GET ─────────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict | None = None,
             use_cache: bool = True) -> dict | list | None:
        """GET a GitHub API URL. Returns parsed JSON or None on error."""
        # Build cache key from url + sorted params
        cache_key = url
        if params:
            cache_key += "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))

        if use_cache and self._db:
            cached = self._db.cache_get(cache_key, self._cache_hours)
            if cached:
                try:
                    return json.loads(cached)
                except Exception:
                    pass

        try:
            resp = requests.get(
                url, headers=self._headers, params=params, timeout=self._timeout
            )
            self._update_rate_limit(resp)

            if resp.status_code == 403:
                logger.warning("GitHub 403 — rate limit or auth issue: %s", resp.text[:200])
                return None
            if resp.status_code == 404:
                return None
            resp.raise_for_status()

            data = resp.json()
            if self._db:
                self._db.cache_set(cache_key, json.dumps(data))
            return data

        except requests.Timeout:
            logger.error("Timeout fetching %s", url)
            return None
        except requests.RequestException as e:
            logger.error("GitHub API error for %s: %s", url, e)
            return None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_rate_limit(self) -> RateLimit | None:
        data = self._get(f"{GITHUB_API}/rate_limit", use_cache=False)
        if data and "rate" in data:
            r = data["rate"]
            self.rate_limit = RateLimit(
                r.get("remaining", 0),
                r.get("limit", 60),
                datetime.fromtimestamp(r.get("reset", 0)),
            )
        return self.rate_limit

    def get_repo(self, owner: str, repo: str) -> dict | None:
        return self._get(f"{GITHUB_API}/repos/{owner}/{repo}")

    def get_contents(self, owner: str, repo: str, path: str = "") -> list | dict | None:
        return self._get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")

    def get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        data = self._get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
        if not data or not isinstance(data, dict):
            return None
        if data.get("encoding") == "base64":
            try:
                return base64.b64decode(
                    data["content"].replace("\n", "")
                ).decode("utf-8")
            except Exception as e:
                logger.error("Failed to decode %s: %s", path, e)
                return None
        return data.get("content")

    def get_readme(self, owner: str, repo: str) -> str | None:
        return self.get_file_content(owner, repo, "README.md")

    def list_skills_in_repo(self, owner: str, repo: str,
                             skills_prefix: str = "skills/") -> list[dict]:
        """Scan a repo directory for subdirs containing SKILL.md."""
        prefix   = skills_prefix.rstrip("/") if skills_prefix else ""
        contents = self.get_contents(owner, repo, prefix)
        if not contents or not isinstance(contents, list):
            return []

        repo_info = self.get_repo(owner, repo) or {}
        stars     = repo_info.get("stargazers_count", 0)

        skills = []
        for entry in contents:
            if entry.get("type") != "dir":
                continue
            skill_name = entry["name"]
            skill_path = entry["path"] + "/SKILL.md"
            content = self.get_file_content(owner, repo, skill_path)
            if content is None:
                continue
            skills.append({
                "name":        skill_name,
                "description": self._extract_description(content),
                "content":     content,
                "url":         entry.get("html_url", ""),
                "stars":       stars,
                "owner":       owner,
                "repo":        repo,
            })
        return skills

    def _extract_description(self, skill_md_content: str) -> str:
        try:
            import yaml
            lines = skill_md_content.split("\n")
            if lines[0].strip() == "---":
                end = lines.index("---", 1)
                fm = yaml.safe_load("\n".join(lines[1:end]))
                if fm and isinstance(fm, dict):
                    return str(fm.get("description", ""))
        except Exception:
            pass
        return ""

    def extract_skill_repos_from_readme(self, readme: str) -> list[dict]:
        """
        Parse markdown links from README, extract GitHub repo URLs.
        Returns list of {owner, repo, label}.
        """
        repos = []
        seen  = set()
        pattern = re.compile(
            r'\[([^\]]+)\]\(https://github\.com/([^/\s)]+)/([^/\s)#]+)[^)]*\)'
        )
        for match in pattern.finditer(readme):
            label = match.group(1)
            owner = match.group(2)
            repo  = match.group(3).rstrip("/.")
            key   = f"{owner}/{repo}"
            if key in seen:
                continue
            seen.add(key)
            repos.append({"owner": owner, "repo": repo, "label": label})
        return repos

    def search_code(self, query: str, per_page: int = 30) -> list[dict]:
        """Search GitHub code for SKILL.md files matching query."""
        full_q  = f"filename:SKILL.md {query}"
        data    = self._get(
            f"{GITHUB_API}/search/code",
            params={"q": full_q, "per_page": per_page},
        )
        if not data or "items" not in data:
            return []
        results = []
        for item in data["items"]:
            repo_info = item.get("repository", {})
            full_name = repo_info.get("full_name", "/")
            owner, _, repo = full_name.partition("/")
            results.append({
                "skill_name":  item.get("name", "SKILL.md"),
                "owner":       owner,
                "repo":        repo,
                "description": repo_info.get("description", ""),
                "url":         item.get("html_url", ""),
                "stars":       repo_info.get("stargazers_count", 0),
            })
        return results

    def fetch_skill_from_url(self, url: str) -> dict | None:
        """
        Fetch a skill from a GitHub URL.
        Accepts:
          - github.com/owner/repo/blob/branch/path/SKILL.md
          - raw.githubusercontent.com/owner/repo/branch/path/SKILL.md
        """
        # github.com blob URL
        blob_pat = re.compile(
            r'github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)'
        )
        m = blob_pat.search(url)
        if m:
            owner, repo, _branch, path = m.groups()
            content = self.get_file_content(owner, repo, path)
            if content:
                return {
                    "content": content,
                    "owner":   owner,
                    "repo":    repo,
                    "name":    Path(path).parent.name,
                    "url":     url,
                }

        # raw.githubusercontent.com
        raw_pat = re.compile(
            r'raw\.githubusercontent\.com/([^/]+)/([^/]+)/[^/]+/(.+)'
        )
        m = raw_pat.search(url)
        if m:
            owner, repo, path = m.groups()
            try:
                resp = requests.get(url, timeout=self._timeout)
                resp.raise_for_status()
                return {
                    "content": resp.text,
                    "owner":   owner,
                    "repo":    repo,
                    "name":    Path(path).parent.name,
                    "url":     url,
                }
            except Exception as e:
                logger.error("Failed to fetch raw URL %s: %s", url, e)

        return None
