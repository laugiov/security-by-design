#!/usr/bin/env python3
"""
Fix openapi-generator imports in model files.

This script replaces:
    from openapi_server.models.xxx import Xxx
With:
    from skylink.models.<service>.xxx import Xxx
"""

import re
from pathlib import Path


def fix_imports_in_file(file_path: Path) -> bool:
    """Fix imports in a single file."""
    # Determine service name from path
    parts = file_path.parts
    if "models" not in parts:
        return False

    models_index = parts.index("models")
    if len(parts) <= models_index + 1:
        return False

    service = parts[models_index + 1]  # e.g., "weather", "contacts", etc.

    # Read file content
    content = file_path.read_text()
    original_content = content

    # Replace imports: from openapi_server.models.xxx import Xxx
    # with: from skylink.models.<service>.xxx import Xxx
    pattern = r"from openapi_server\.models\.(\w+) import"
    replacement = rf"from skylink.models.{service}.\1 import"
    content = re.sub(pattern, replacement, content)

    # Check if changes were made
    if content != original_content:
        file_path.write_text(content)
        return True

    return False


def main():
    """Fix all model files."""
    project_root = Path(__file__).parent.parent
    models_dir = project_root / "skylink" / "models"

    fixed_count = 0

    # Process all Python files in models/
    for py_file in models_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        if fix_imports_in_file(py_file):
            print(f"✅ Fixed: {py_file.relative_to(project_root)}")
            fixed_count += 1

    print(f"\n🎉 Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
