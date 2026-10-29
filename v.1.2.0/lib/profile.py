"""Per-project profile resolver for the ai-sdlc skills.

A profile is a private markdown file (YAML-subset frontmatter + `## ` sections)
kept outside project repos, by default in ~/.claude/ai-sdlc/profiles/. It is
located via $AI_SDLC_PROFILE, falling back to matching its frontmatter `remotes`
against the repo's `origin` remote.

Note: this module name shadows the stdlib `profile`; lib/ is only put on
sys.path by the CLIs and tests, which never import the stdlib one.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple, Optional


PATH_KEYS = ("task_files_dir", "summaries_dir")


class Resolution(NamedTuple):
    """path is the resolved profile (or None); reason explains a rejected env
    path or a failed lookup, and is None on a clean env-var hit or remote match."""

    path: Optional[Path]
    reason: Optional[str] = None


def normalise_remote(url):
    """Reduce a git remote URL to host/group/repo (no scheme, creds, port, .git)."""
    url = url.strip()
    m = re.match(r"^[\w.-]+@([^:/]+):(?!\d+/)(.+)$", url)  # scp-like git@host:path
    if m:
        host, path = m.groups()
    else:
        m = re.match(r"^[a-z+]+://(?:[^@/]*@)?([^/:]+)(?::\d+)?/(.+)$", url, re.I)
        if not m:
            return url
        host, path = m.groups()
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host.lower()}/{path}"


def _origin_remote(repo):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip() or None


def _split_top(text):
    """Split on commas that are not inside [] or {}."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts]


def _strip_comment(line):
    """Drop a trailing ` # comment` that sits outside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line


def _scalar(text):
    text = text.strip()
    if text[:1] in ("[", "{") and text[-1:] != {"[": "]", "{": "}"}[text[0]]:
        raise ValueError(f"unclosed {text[0]} in value: {text}")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(p) for p in _split_top(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        result = {}
        for part in _split_top(text[1:-1]):
            key, _, val = part.partition(":")
            result[key.strip()] = _scalar(val)
        return result
    if text.lower() in ("null", "~", ""):
        return None
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_frontmatter(text):
    """Parse the YAML subset: `key: scalar|[list]|{map}`, block lists (`- x`)
    and one level of block maps (indented `key: value`) under a bare `key:`.
    Trailing ` # comments` outside quotes are dropped. Raises ValueError on
    a malformed line."""
    data, key = {}, None
    for raw in text.splitlines():
        line = _strip_comment(raw.rstrip())
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line[0] in " \t"
        stripped = line.strip()
        if indented and key is not None:
            if stripped.startswith("- "):
                if not isinstance(data[key], list):
                    data[key] = []
                data[key].append(_scalar(stripped[2:]))
            else:
                if not isinstance(data[key], dict):
                    data[key] = {}
                k, _, v = stripped.partition(":")
                data[key][k.strip()] = _scalar(v)
            continue
        key, sep, val = line.partition(":")
        key = key.strip()
        if not sep or not key:
            raise ValueError(f"expected `key: value`, got: {line}")
        data[key] = _scalar(val)
    return data


LIST_KEYS = ("remotes", "forbidden", "forbidden.paths", "forbidden.commands",
             "jira_statuses", "jira_statuses.start")


def settings_warnings(settings):
    """Warn when a key that should be a list or map parsed as a plain string
    (usually a missing [ ] or { })."""
    warnings = []
    for dotted in LIST_KEYS:
        value = settings
        for part in dotted.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, str):
            warnings.append(f"{dotted} is a plain string ({value!r}); expected a list or map")
    return warnings


def _split_document(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", text, re.S)
    if not m:
        return "", text
    return m.group(1), m.group(2)


def load_profile(path):
    """Return {"settings": frontmatter dict, "sections": {heading: body}}."""
    front, body = _split_document(Path(path).read_text())
    sections, heading, lines = {}, None, []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if heading is not None:
                sections[heading] = "\n".join(lines).strip()
            heading, lines = m.group(1), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections[heading] = "\n".join(lines).strip()
    settings = parse_frontmatter(front)
    for key in PATH_KEYS:
        if isinstance(settings.get(key), str):
            settings[key] = os.path.expanduser(settings[key])
    return {"settings": settings, "sections": sections}


def resolve_profile_path(repo, env, profiles_dir):
    """Find the profile for `repo`.

    Order: env["AI_SDLC_PROFILE"] if it names an existing file; else the first
    file in profiles_dir whose `remotes` contains the normalised origin URL.
    Returns Resolution(path, reason). reason is set when the env path was
    rejected (even if a remote match then succeeded) or nothing matched.
    """
    reason = None
    explicit = env.get("AI_SDLC_PROFILE")
    if explicit:
        explicit = os.path.expanduser(explicit)
        if Path(explicit).is_file():
            return Resolution(Path(explicit))
        reason = f"AI_SDLC_PROFILE points to a missing file: {explicit}"

    remote = _origin_remote(repo)
    if remote is None:
        return Resolution(None, _join(reason, "no origin remote in repo"))
    wanted = normalise_remote(remote)
    profiles_dir = Path(profiles_dir)
    for candidate in sorted(profiles_dir.glob("*.md")) if profiles_dir.is_dir() else []:
        try:
            remotes = load_profile(candidate)["settings"].get("remotes") or []
        except (OSError, ValueError):  # unreadable or malformed: skip
            continue
        if isinstance(remotes, str):
            remotes = [remotes]
        if wanted in [normalise_remote(r) for r in remotes]:
            return Resolution(candidate, reason)
    return Resolution(None, _join(reason, f"no profile in {profiles_dir} lists remote {wanted}"))


def _join(first, second):
    return f"{first}; {second}" if first else second
