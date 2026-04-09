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
