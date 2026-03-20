import pathlib
import shutil

SRC_DIR = pathlib.Path("src/codex_services")
DOCS_DIR = pathlib.Path("docs")
LANGS = ["en", "ru"]


def generate_docs():
    # 1. Purge old structure
    if (DOCS_DIR / "api").exists():
        shutil.rmtree(DOCS_DIR / "api")
        print("Removed old docs/api/")

    # We will traverse and build the nav structure simultaneously using a dictionary tree

    def process_dir(current_src_dir: pathlib.Path, nav_parent_dict: dict):
        items = sorted(current_src_dir.iterdir())

        for item in items:
            if item.name == "__pycache__":
                continue

            # Calculate the python module path
            rel_path = item.relative_to(SRC_DIR.parent)
            module_name = str(rel_path).replace("\\", ".").replace("/", ".").replace(".py", "")

            if item.is_file() and item.suffix == ".py":
                if item.name == "__init__.py":
                    # For __init__.py, we don't add to nav dict directly as a child file but as index
                    md_filename = "index.md"
                    title = "Overview"
                    nav_key = "Overview"
                    # The module name is the dir name without .__init__
                    module_name = module_name[:-9]
                else:
                    md_filename = item.name.replace(".py", ".md")
                    title = item.stem.replace("_", " ").title()
                    nav_key = title

                # Write to both languages
                for lang in LANGS:
                    out_dir = DOCS_DIR / lang / "api" / current_src_dir.relative_to(SRC_DIR)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_file = out_dir / md_filename

                    content = f"<!-- Type: REFERENCE -->\n\n# {module_name}\n\n::: {module_name}\n"
                    out_file.write_text(content, encoding="utf-8")

                # Add to nav tree based on the english path
                docs_rel_path = f"api/{current_src_dir.relative_to(SRC_DIR)}/{md_filename}".replace("\\", "/")

                # If it's an init file, it goes first in the dictionary if possible
                if nav_key == "Overview":
                    # Prepend Overview to the front of this level's dict keys.
                    # Since dictionaries retain order in python 3.7+, we can't easily prepend without recreating,
                    # but we'll sort Overview to top during YAML dumping.
                    nav_parent_dict[nav_key] = docs_rel_path
                else:
                    nav_parent_dict[title] = docs_rel_path

            elif item.is_dir():
                sub_dict = {}
                title = item.name.replace("_", " ").title()
                nav_parent_dict[title] = sub_dict
                process_dir(item, sub_dict)

    nav_tree = {}
    process_dir(SRC_DIR, nav_tree)

    def print_yaml_dict(d, indent=0):
        # Ensure Overview is printed first
        keys = list(d.keys())
        if "Overview" in keys:
            keys.remove("Overview")
            keys.insert(0, "Overview")

        for k in keys:
            v = d[k]
            if isinstance(v, dict):
                print(f"{' ' * indent}- {k}:")
                print_yaml_dict(v, indent + 4)
            else:
                print(f"{' ' * indent}- {k}: {v}")

    print("\n--- YAML NAVIGATION BLOCK FOR mkdocs.yml (Under API Reference:) ---\n")
    print_yaml_dict(nav_tree)


if __name__ == "__main__":
    generate_docs()
