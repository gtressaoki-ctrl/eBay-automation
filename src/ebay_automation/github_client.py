"""Minimal GitHub REST API wrapper used only to open/comment/close the
human-approval issues. Runs with the GitHub Actions-provided GITHUB_TOKEN,
scoped to this repository only.
"""
from __future__ import annotations

import requests

from .config import Config

_API_BASE = "https://api.github.com"


class GithubClient:
    def __init__(self, config: Config):
        self.config = config
        config.require("github_token", "github_repository")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> dict:
        url = f"{_API_BASE}/repos/{self.config.github_repository}/issues"
        resp = requests.post(
            url, headers=self._headers(), json={"title": title, "body": body, "labels": labels or []}, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def comment_issue(self, issue_number: int, body: str) -> dict:
        url = f"{_API_BASE}/repos/{self.config.github_repository}/issues/{issue_number}/comments"
        resp = requests.post(url, headers=self._headers(), json={"body": body}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def close_issue(self, issue_number: int, state_reason: str = "completed") -> dict:
        url = f"{_API_BASE}/repos/{self.config.github_repository}/issues/{issue_number}"
        resp = requests.patch(
            url, headers=self._headers(), json={"state": "closed", "state_reason": state_reason}, timeout=30
        )
        resp.raise_for_status()
        return resp.json()
