"""Knowledge card linter: quality checks on compiled cards."""
import re
from app.schemas.compile import LintIssue


async def lint_card(title: str, content: str, card_type: str) -> list[LintIssue]:
    """Run quality checks on a compiled knowledge card."""
    issues = []

    # Check for empty content
    if not content or len(content.strip()) < 50:
        issues.append(LintIssue(
            type="content_gap", severity="error",
            message=f"Card '{title}' has very short content ({len(content.strip())} chars)",
            location=title,
        ))

    # Check for placeholder text
    placeholders = ["TODO", "PLACEHOLDER", "INSERT HERE", "FIXME", "TBD"]
    for placeholder in placeholders:
        if placeholder in content.upper():
            issues.append(LintIssue(
                type="placeholder", severity="warning",
                message=f"Card '{title}' contains placeholder text: {placeholder}",
                location=title,
            ))

    # Check for broken markdown links
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    for match in link_pattern.finditer(content):
        link_text, link_url = match.groups()
        if not link_url or link_url == "#":
            issues.append(LintIssue(
                type="broken_link", severity="warning",
                message=f"Card '{title}' has empty/broken link: [{link_text}]({link_url})",
                location=title,
            ))

    # Check for very long unstructured text (no headings)
    if len(content) > 2000 and not re.search(r'^#+\s', content, re.MULTILINE):
        issues.append(LintIssue(
            type="structure", severity="warning",
            message=f"Card '{title}' is long ({len(content)} chars) with no heading structure",
            location=title,
        ))

    # Check card_type specific quality
    if card_type == "concept" and "definition" not in content.lower() and "defined" not in content.lower():
        issues.append(LintIssue(
            type="missing_definition", severity="warning",
            message=f"Concept card '{title}' may be missing a clear definition",
            location=title,
        ))

    return issues
