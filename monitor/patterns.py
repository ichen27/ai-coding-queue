import re

_PERMISSION_PATTERNS = [
    re.compile(r"Allow\s+Deny", re.IGNORECASE),
    re.compile(r"^\s*(Yes|No)\s+(Yes|No)\s*$", re.MULTILINE),
    re.compile(r"\(y/n\)", re.IGNORECASE),
]

_READY_PATTERNS = [
    re.compile(r"[❯>]\s*$"),
    re.compile(r"\$\s*$"),
]

_QUESTION_PATTERNS = [
    re.compile(r"\?\s*$", re.MULTILINE),
]


def detect_state(output: str) -> str:
    if not output.strip():
        return "working"
    lines = output.strip().split("\n")
    recent = "\n".join(lines[-20:])
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(recent):
            return "permission_prompt"
    for pattern in _READY_PATTERNS:
        if pattern.search(recent):
            return "ready"
    for pattern in _QUESTION_PATTERNS:
        if pattern.search(lines[-1]):
            return "needs_input"
    return "working"


def extract_tail(output: str, num_lines: int = 50) -> str:
    lines = output.split("\n")
    if len(lines) <= num_lines:
        return output
    return "\n".join(lines[-num_lines:])


# ANSI escape code pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]")
# Control characters (except newline and tab)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# 3+ consecutive blank lines → 1
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def clean_output(text: str) -> str:
    """Strip ANSI codes, control chars, and collapse excessive blank lines."""
    text = _ANSI_RE.sub("", text)
    text = _CTRL_RE.sub("", text)
    # Collapse runs of whitespace-only lines
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

    lines = [l for l in cleaned.split("\n") if l.strip()]
    if not lines:
        return ""

    if state == "permission_prompt":
        # Look for the line describing what permission is needed
        for line in reversed(lines):
            lower = line.lower()
            if "allow" in lower and "deny" in lower:
                continue  # Skip the Allow/Deny buttons line itself
            if "yes" == lower.strip() or "no" == lower.strip():
                continue
            if line.strip():
                return _truncate(line.strip(), 120)
        return _truncate(lines[-1].strip(), 120)

    if state == "needs_input":
        # Find the last question
        for line in reversed(lines):
            if "?" in line:
                return _truncate(line.strip(), 120)
        return _truncate(lines[-1].strip(), 120)

    if state == "ready":
        # Find the last meaningful non-prompt line
        for line in reversed(lines):
            stripped = line.strip()
            if stripped in ("❯", ">", "$", ""):
                continue
            return _truncate(stripped, 120)

    # working — show last meaningful line
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            return _truncate(stripped, 120)

    return ""


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
