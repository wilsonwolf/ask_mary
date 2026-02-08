"""Shared communications template loading and rendering."""

from pathlib import Path

import yaml
from jinja2 import Template

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "comms_templates"


def load_template(template_id: str) -> dict:
    """Load a communications template from YAML.

    Args:
        template_id: Template filename without extension.

    Returns:
        Parsed template dict with name, channel, body fields.

    Raises:
        FileNotFoundError: If template file does not exist.
    """
    path = _TEMPLATES_DIR / f"{template_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")
    with open(path) as f:
        return yaml.safe_load(f)


def render_template(template_id: str, **variables: str) -> str:
    """Render a template body with Jinja2 variables.

    Args:
        template_id: Template filename without extension.
        **variables: Key-value pairs for Jinja2 substitution.

    Returns:
        Rendered template string.
    """
    data = load_template(template_id)
    template = Template(data["body"])
    return template.render(**variables)


def list_templates() -> list[str]:
    """List all available template names.

    Returns:
        List of template IDs (filenames without .yaml extension).
    """
    return [p.stem for p in _TEMPLATES_DIR.glob("*.yaml")]
