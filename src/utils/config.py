import os
import yaml
from pathlib import Path

def load_config(config_path="config/config.yaml"):
    config_path = Path(config_path)
    if not config_path.exists():
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}\nCopy config/config.example.yaml to config/config.yaml and fill in your keys.")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    config.setdefault("output_dir", str(Path(__file__).parent.parent.parent / "output"))
    config.setdefault("assets_dir", str(Path(__file__).parent.parent.parent / "assets"))
    for dir_key in ["output_dir", "assets_dir"]:
        config[dir_key] = str(Path(config[dir_key]).resolve())
        Path(config[dir_key]).mkdir(parents=True, exist_ok=True)
    return config
