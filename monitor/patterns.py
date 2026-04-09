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


def _is_chrome_line(line: str) -> bool:
    """Check if a line is Claude Code UI chrome (status bar, separators, etc.)."""
    stripped = line.strip()
    if not stripped:
        return False
    if any(kw in stripped for kw in ["Context ", "bypass permissions", "new task?"]):
        return True
    if re.match(r"─{5,}", stripped):
        return True
    if re.match(r"❯", stripped):
        return True
    if re.match(r"\[(?:Opus|Sonnet|Haiku|Claude)", stripped):
        return True
    if stripped.startswith("✻"):
        return True
    if re.match(r"^[▘▝▗▖▚▞▀▄█░⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏\s/|\\-]+$", stripped) and len(stripped) < 20:
        return True
    return False


def extract_summary(output: str, state: str) -> str:
    """Extract the last full block of Claude's response from terminal output."""
    cleaned = clean_output(output)
    if not cleaned:
        return ""

    lines = cleaned.split("\n")

    # Walk backwards from end, skip chrome, collect content until we hit
    # a separator (─────) or run out of lines. This gives us the last
    # full response block.
    block_lines: list[str] = []
    found_content = False

    for line in reversed(lines):
        stripped = line.strip()

        # Skip empty lines at the very end (before we find content)
        if not found_content and not stripped:
            continue

        # Skip chrome lines at the end (status bar, prompt, separators)
        if not found_content and _is_chrome_line(line):
            continue

        # Skip timing lines ("Worked for 44s") at boundary
        if not found_content and re.match(r"(Worked|Baked|Sautéed|Brewed) for ", stripped):
            continue

        # Once we've started collecting content, a separator means end of block
        if found_content and re.match(r"─{5,}", stripped):
            break

        # Also stop at a user prompt line (❯ ...) which separates turns
        if found_content and re.match(r"❯", stripped):
            break

        found_content = True
        block_lines.append(line)

        # Cap at ~30 lines to keep it reasonable
        if len(block_lines) >= 30:
            break

    if not block_lines:
        return ""

    # Reverse back to original order and strip trailing/leading blanks
    block_lines.reverse()
    # Trim leading/trailing empty lines
    while block_lines and not block_lines[0].strip():
        block_lines.pop(0)
    while block_lines and not block_lines[-1].strip():
        block_lines.pop()

    return "\n".join(block_lines)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
