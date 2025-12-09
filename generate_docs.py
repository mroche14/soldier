import os
import subprocess
from pathlib import Path

def find_modules(root_dir: Path):
    """Find all Python modules in a directory."""
    for path in root_dir.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        # Convert file path to module path
        relative_path = path.relative_to(root_dir.parent)
        module_path = ".".join(relative_path.with_suffix("").parts)
        yield module_path

def generate_docs():
    """Generate markdown documentation for all modules."""
    root_dir = Path("focal")
    output_dir = Path("webdoc/docs/reference")
    output_dir.mkdir(exist_ok=True)

    for module in find_modules(root_dir):
        print(f"Generating docs for {module}...")
        output_file = output_dir / f"{module}.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "uv", "run", "pydoc-markdown",
            "-m", module
        ]
        with open(output_file, "w") as f:
            subprocess.run(command, stdout=f)

if __name__ == "__main__":
    generate_docs()
