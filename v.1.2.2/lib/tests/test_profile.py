import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from profile import load_profile, normalise_remote, resolve_profile_path

PROFILE = """---
name: demo
remotes: [git.epam.com/grp/repo, github.com/acme/other]
base_branch: develop
branch_pattern: "user/{user}/{ticket}-{slug}"
jira_statuses: {start: [Open, To Do], in_progress: In Progress}
forbidden:
  paths: [.env]
  commands: [rm -rf]
task_files_dir: tasks
extra:
  - one
  - two
---
## How the application works
It works.

## Local testing flow
Run tests.
"""


def make_repo(tmp_path, url="git@git.epam.com:grp/repo.git", name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
    return repo


def make_profiles(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "demo.md").write_text(PROFILE)
    return d


def test_env_var_wins(tmp_path):
    repo = make_repo(tmp_path)
    explicit = tmp_path / "explicit.md"
    explicit.write_text(PROFILE)
    res = resolve_profile_path(repo, {"AI_SDLC_PROFILE": str(explicit)}, make_profiles(tmp_path))
    assert res.path == explicit
    assert res.reason is None


def test_env_var_missing_file_falls_back_to_remote(tmp_path):
    repo = make_repo(tmp_path)
    profiles = make_profiles(tmp_path)
    bad = tmp_path / "nope.md"
    res = resolve_profile_path(repo, {"AI_SDLC_PROFILE": str(bad)}, profiles)
    assert res.path == profiles / "demo.md"
    assert str(bad) in res.reason


def test_remote_match_ssh_and_https(tmp_path):
    profiles = make_profiles(tmp_path)
    for i, url in enumerate(["git@git.epam.com:grp/repo.git", "https://git.epam.com/grp/repo"]):
        repo = make_repo(tmp_path, url, name=f"r{i}")
        assert resolve_profile_path(repo, {}, profiles).path == profiles / "demo.md"


def test_no_match_returns_none(tmp_path):
    repo = make_repo(tmp_path, "git@git.epam.com:other/thing.git")
    res = resolve_profile_path(repo, {}, make_profiles(tmp_path))
    assert res.path is None
    assert res.reason


def test_normalise_remote():
    assert normalise_remote("git@host:group/repo.git") == "host/group/repo"
    assert normalise_remote("https://host/group/repo.git") == "host/group/repo"
    assert normalise_remote("https://user:tok@host/group/repo") == "host/group/repo"
    assert normalise_remote("ssh://git@host:2222/group/repo.git") == "host/group/repo"


def test_load_profile_parses_frontmatter_and_sections(tmp_path):
    p = tmp_path / "p.md"
    p.write_text(PROFILE)
    data = load_profile(p)
    s = data["settings"]
    assert s["base_branch"] == "develop"
    assert s["branch_pattern"] == "user/{user}/{ticket}-{slug}"
    assert s["jira_statuses"]["start"] == ["Open", "To Do"]
    assert s["jira_statuses"]["in_progress"] == "In Progress"
    assert s["forbidden"] == {"paths": [".env"], "commands": ["rm -rf"]}
    assert s["extra"] == ["one", "two"]
    assert "Local testing flow" in data["sections"]
    assert data["sections"]["How the application works"] == "It works."


def test_cli_show(tmp_path):
    repo = make_repo(tmp_path)
    profiles = make_profiles(tmp_path)
    cli = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli_profile.py")
    env = {**os.environ, "AI_SDLC_PROFILES_DIR": str(profiles)}
    env.pop("AI_SDLC_PROFILE", None)
    out = subprocess.run([sys.executable, cli, "show", "--section", "Local testing flow"],
                         cwd=repo, env=env, capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["sections"] == {"Local testing flow": "Run tests."}
    repo2 = make_repo(tmp_path, "git@h:a/b.git", name="repo2")
    env["AI_SDLC_PROFILES_DIR"] = str(tmp_path / "empty")
    out = subprocess.run([sys.executable, cli, "show"], cwd=repo2, env=env, capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout)["profile"] is None


def test_env_var_expands_tilde(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "x.md").write_text(PROFILE)
    monkeypatch.setenv("HOME", str(home))
    res = resolve_profile_path(make_repo(tmp_path), {"AI_SDLC_PROFILE": "~/x.md"}, tmp_path / "none")
    assert res.path == home / "x.md"


def test_path_settings_expand_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "p.md"
    p.write_text("---\nsummaries_dir: ~/notes\ntask_files_dir: tasks\n---\n")
    s = load_profile(p)["settings"]
    assert s["summaries_dir"] == str(tmp_path / "notes")
    assert s["task_files_dir"] == "tasks"


def test_normalise_remote_lowercases_host():
    assert normalise_remote("git@Git.EPAM.com:Grp/Repo.git") == "git.epam.com/Grp/Repo"


def test_cli_unreadable_profile_reports_null(tmp_path):
    repo = make_repo(tmp_path)
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe\x00bad")
    cli = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli_profile.py")
    env = {**os.environ, "AI_SDLC_PROFILE": str(bad)}
    out = subprocess.run([sys.executable, cli, "show"], cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout)["profile"] is None


CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli_profile.py")


def run_show(repo, profile_path):
    env = {**os.environ, "AI_SDLC_PROFILE": str(profile_path)}
    out = subprocess.run([sys.executable, CLI, "show"], cwd=repo, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_trailing_comments_are_stripped(tmp_path):
    p = tmp_path / "p.md"
    p.write_text(
        "---\n"
        "base_branch: develop  # default branch\n"
        "remotes: [a/b, c/d] # two remotes\n"
        'branch_pattern: "user/#{ticket}"  # quoted hash kept\n'
        "forbidden:\n"
        "  paths: [.env]  # secrets\n"
        "url: http://x/y#frag\n"
        "---\n"
    )
    s = load_profile(p)["settings"]
    assert s["base_branch"] == "develop"
    assert s["remotes"] == ["a/b", "c/d"]
    assert s["branch_pattern"] == "user/#{ticket}"
    assert s["url"] == "http://x/y#frag"


def test_cli_malformed_frontmatter_reports_null(tmp_path):
    repo = make_repo(tmp_path)
    p = tmp_path / "bad.md"
    p.write_text("---\nremotes: [a/b\n---\n")
    out = run_show(repo, p)
    assert out["profile"] is None
    assert "reason" in out


def test_cli_warns_on_string_list_keys(tmp_path):
    repo = make_repo(tmp_path)
    p = tmp_path / "p.md"
    p.write_text(
        "---\n"
        "remotes: git.epam.com/grp/repo\n"
        "forbidden:\n"
        "  paths: .env\n"
        "  commands: [rm -rf]\n"
        "jira_statuses: {start: Open}\n"
        "---\n"
    )
    warnings = run_show(repo, p)["warnings"]
    joined = " ".join(warnings)
    assert "remotes" in joined
    assert "forbidden.paths" in joined
    assert "jira_statuses.start" in joined
    assert "forbidden.commands" not in joined


def test_cli_no_warnings_for_clean_profile(tmp_path):
    repo = make_repo(tmp_path)
    p = tmp_path / "p.md"
    p.write_text(PROFILE)
    assert "warnings" not in run_show(repo, p)


def test_parse_block_list_of_inline_maps(tmp_path):
    """Parser supports block list of inline maps: - {k: v, k2: v2}"""
    p = tmp_path / "p.md"
    p.write_text(
        "---\n"
        "repos:\n"
        "  - {name: frontend, path: ui-app, remote: git.epam.com/grp/ui-app, owns: \"UI layer\"}\n"
        "  - {name: backend, path: api-service, remote: git.epam.com/grp/api, owns: \"REST API\"}\n"
        "---\n"
    )
    s = load_profile(p)["settings"]
    assert isinstance(s["repos"], list)
    assert len(s["repos"]) == 2
    assert s["repos"][0] == {"name": "frontend", "path": "ui-app", "remote": "git.epam.com/grp/ui-app", "owns": "UI layer"}
    assert s["repos"][1] == {"name": "backend", "path": "api-service", "remote": "git.epam.com/grp/api", "owns": "REST API"}


def test_workspace_mode_with_repos(tmp_path):
    """cli_profile.py show outputs mode:workspace and repos with abs_path and exists flags."""
    # Workspace root (not a git repo)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create one existing repo
    existing = workspace / "frontend"
    existing.mkdir()

    # Profile with workspace_root and repos
    p = tmp_path / "profile.md"
    p.write_text(
        "---\n"
        "name: team\n"
        f"workspace_root: {workspace}\n"
        "repos:\n"
        "  - {name: frontend, path: frontend, remote: git.epam.com/team/frontend, owns: \"UI\"}\n"
        "  - {name: backend, path: backend, remote: git.epam.com/team/backend, owns: \"API\"}\n"
        "---\n"
    )

    env = {**os.environ, "AI_SDLC_PROFILE": str(p)}
    out = subprocess.run([sys.executable, CLI, "show"], cwd=workspace, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)

    assert result["mode"] == "workspace"
    assert "repos" in result
    assert len(result["repos"]) == 2

    # First repo exists
    assert result["repos"][0]["name"] == "frontend"
    assert result["repos"][0]["abs_path"] == str(workspace / "frontend")
    assert result["repos"][0]["exists"] is True

    # Second repo doesn't exist
    assert result["repos"][1]["name"] == "backend"
    assert result["repos"][1]["abs_path"] == str(workspace / "backend")
    assert result["repos"][1]["exists"] is False


def test_non_git_cwd_uses_env_only(tmp_path):
    """Resolution in non-git cwd: AI_SDLC_PROFILE only, no remote match."""
    # Non-git directory
    non_git = tmp_path / "non-git"
    non_git.mkdir()

    # Profile with a remote
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "demo.md").write_text(PROFILE)

    # Another profile pointed to by env
    explicit = tmp_path / "explicit.md"
    explicit.write_text(PROFILE.replace("name: demo", "name: explicit"))

    # Without AI_SDLC_PROFILE, should return null (no remote to match)
    env = {**os.environ, "AI_SDLC_PROFILES_DIR": str(profiles)}
    env.pop("AI_SDLC_PROFILE", None)
    out = subprocess.run([sys.executable, CLI, "show"], cwd=non_git, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["profile"] is None
    assert result["mode"] == "workspace"
    assert result["workspace_root"] == str(non_git.resolve())
    assert result["reason"] == (
        f"workspace root: set AI_SDLC_PROFILE in {non_git.resolve()}/.claude/settings.local.json "
        "(run /dev-profile-init)"
    )

    # With AI_SDLC_PROFILE, should use it (ignoring remote match)
    env["AI_SDLC_PROFILE"] = str(explicit)
    out = subprocess.run([sys.executable, CLI, "show"], cwd=non_git, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["path"] == str(explicit)
    assert result["settings"]["name"] == "explicit"


def test_cli_warns_on_string_repos(tmp_path):
    """Warn when repos is a string instead of a list."""
    repo = make_repo(tmp_path)
    p = tmp_path / "p.md"
    p.write_text(
        "---\n"
        "remotes: [git.epam.com/grp/repo]\n"
        "repos: single-string-not-a-list\n"
        "---\n"
    )
    warnings = run_show(repo, p)["warnings"]
    assert any("repos" in w for w in warnings)


def test_null_profile_in_git_repo_reports_repo_mode(tmp_path):
    repo = make_repo(tmp_path)
    env = {**os.environ, "AI_SDLC_PROFILES_DIR": str(tmp_path / "none")}
    env.pop("AI_SDLC_PROFILE", None)
    out = subprocess.run([sys.executable, CLI, "show"], cwd=repo, env=env, capture_output=True, text=True)
    result = json.loads(out.stdout)
    assert result["profile"] is None
    assert result["mode"] == "repo"
    assert "no profile in" in result["reason"]


def test_profile_workspace_root_wins_for_nested_repo_found_by_remote(tmp_path):
    """A repo with its own .claude/settings.local.json, profile found by remote
    match: repos resolve against the profile's workspace_root, not the repo."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repo = make_repo(workspace, name="api")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text("{}")
    (workspace / "ui").mkdir()
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "team.md").write_text(
        "---\n"
        "remotes: [git.epam.com/grp/repo]\n"
        f"workspace_root: {workspace}\n"
        "repos:\n"
        "  - {name: ui, path: ui}\n"
        "  - {name: api, path: api}\n"
        "---\n"
    )
    env = {**os.environ, "AI_SDLC_PROFILES_DIR": str(profiles)}
    env.pop("AI_SDLC_PROFILE", None)
    out = subprocess.run([sys.executable, CLI, "show"], cwd=repo, env=env, capture_output=True, text=True)
    result = json.loads(out.stdout)
    assert result["mode"] == "repo"
    assert [r["abs_path"] for r in result["repos"]] == [str(workspace / "ui"), str(workspace / "api")]
    assert all(r["exists"] for r in result["repos"])


def test_relative_workspace_root_resolves_against_profile_dir(tmp_path):
    profile_dir = tmp_path / "ws" / "profiles"
    profile_dir.mkdir(parents=True)
    (tmp_path / "ws" / "ui").mkdir()
    p = profile_dir / "team.md"
    p.write_text("---\nworkspace_root: ..\nrepos:\n  - {name: ui, path: ui}\n---\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = {**os.environ, "AI_SDLC_PROFILE": str(p)}
    out = subprocess.run([sys.executable, CLI, "show"], cwd=elsewhere, env=env, capture_output=True, text=True)
    result = json.loads(out.stdout)
    assert result["repos"][0]["abs_path"] == str((tmp_path / "ws" / "ui").resolve())
    assert result["repos"][0]["exists"] is True
