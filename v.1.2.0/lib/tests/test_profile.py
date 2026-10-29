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
