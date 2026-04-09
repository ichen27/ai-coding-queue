import re

# --- Claude Code session detection ---
# These patterns identify whether a session is running Claude Code at all
_CLAUDE_CODE_SIGNATURES = [
    re.compile(r"Context\s+[█░]+\s+\d+%"),       # Context progress bar
    re.compile(r"\[(?:Opus|Sonnet|Haiku|Claude)\s+[\d.]+\]", re.IGNORECASE),  # Model name
    re.compile(r"bypass permissions", re.IGNORECASE),  # Permission mode indicator
    re.compile(r"Co-Authored-By:.*Claude"),        # Commit signature
]


def is_claude_code_session(output: str) -> bool:
    """Check if the terminal output looks like a Claude Code session."""
    if not output.strip():
        return False
    # Need at least one signature match
    for pattern in _CLAUDE_CODE_SIGNATURES:
        if pattern.search(output):
            return True
    return False


# --- State detection (only for Claude Code sessions) ---

# Permission prompts — Claude Code shows these when tools need approval
_PERMISSION_PATTERNS = [
    re.compile(r"Allow\s+Deny", re.IGNORECASE),
    re.compile(r"\(y/n\)", re.IGNORECASE),
]

# Claude Code ready prompt — ❯ after the separator line
_READY_PATTERNS = [
    re.compile(r"─{5,}\n❯"),                      # ❯ right after separator
    re.compile(r"❯\s*$"),                          # ❯ at end of content
]

# Question patterns — Claude is asking something
_QUESTION_PATTERNS = [
    re.compile(r"\?\s*$", re.MULTILINE),
]


def detect_state(output: str) -> str:
    """Analyze terminal output and return the detected Claude Code state.

    Returns one of: "permission_prompt", "ready", "needs_input", "working"
    """
    if not output.strip():
        return "working"

    lines = output.strip().split("\n")
    recent = "\n".join(lines[-30:])

    # Highest priority: permission prompts
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(recent):
            return "permission_prompt"

    # Check if Claude Code is at its input prompt (❯ after separator)
    for pattern in _READY_PATTERNS:
        if pattern.search(recent):
            # If context is 0%, this is a fresh/idle session
            if re.search(r"Context\s+░{5,}\s+0%", recent):
                return "idle"
            return "ready"

    # Question — Claude is asking something (check last non-empty line before status bar)
    # Skip the status bar lines (Context, bypass permissions, model name)
    content_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip Claude Code status bar lines
        if any(kw in stripped for kw in ["Context ", "bypass permissions", "─────", "❯"]):
            continue
        if re.match(r"\[(?:Opus|Sonnet|Haiku|Claude)", stripped):
            continue
        content_lines.append(stripped)
        if len(content_lines) >= 5:
            break

    if content_lines and "?" in content_lines[0]:
        return "needs_input"

    return "working"


def extract_tail(output: str, num_lines: int = 50) -> str:
    """Extract the last N lines from output."""
    lines = output.split("\n")
    if len(lines) <= num_lines:
        return output
    return "\n".join(lines[-num_lines:])


# ANSI escape code pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]")
# Control characters (except newline and tab)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_output(text: str) -> str:
    """Strip ANSI codes, control chars, and collapse excessive blank lines."""
    text = _ANSI_RE.sub("", text)
    text = text.replace("\x00", " ")  # iTerm2 uses null bytes as space padding
    text = text.replace("\xa0", " ")  # non-breaking space → regular space
    text = _CTRL_RE.sub("", text)
    lines = text.split("\n")
    cleaned = []
    blank_count = 0
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            blank_count += 1
            if blank_count <= 1:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def extract_summary(output: str, state: str) -> str:
    """Extract a one-line summary from cleaned output based on detected state."""
    cleaned = clean_output(output)
    if not cleaned:
        return ""

    lines = cleaned.split("\n")

    # Find meaningful content lines (skip status bar, separators, empty)
    content_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip Claude Code chrome
        if any(kw in stripped for kw in ["Context ", "bypass permissions", "─────", "❯", "new task?"]):
            continue
        if re.match(r"\[(?:Opus|Sonnet|Haiku|Claude)", stripped):
            continue
        if stripped.startswith("Worked for") or stripped.startswith("Baked for") or stripped.startswith("Sautéed for") or stripped.startswith("Brewed for"):
            continue
        if stripped.startswith("✻"):
            continue
        # Skip Claude Code spinner/braille animation remnants
        if re.match(r"^[▘▝▗▖▚▞▀▄█░⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏\s/|\\-]+", stripped) and len(stripped) < 20:
            continue
        content_lines.append(stripped)
        if len(content_lines) >= 5:
            break

    if not content_lines:
        return ""

    if state == "permission_prompt":
        for line in content_lines:
            lower = line.lower()
            if "allow" in lower and "deny" in lower:
                continue
            if line.strip():
                return _truncate(line.strip(), 120)

    if state == "needs_input":
        for line in content_lines:
            if "?" in line:
                return _truncate(line.strip(), 120)

    # For ready/working — show the last meaningful content line
    return _truncate(content_lines[0].strip(), 120)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
