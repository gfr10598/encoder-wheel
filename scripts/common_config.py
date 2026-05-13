import yaml, re


def load_config(path):
    """Load configuration from YAML or Markdown frontmatter and fail loudly.

    Raises ValueError if the file cannot be parsed or yields an empty result.
    """
    with open(path, 'r') as f:
        txt = f.read()
    s = txt.lstrip()
    cfg = None
    # YAML frontmatter
    if s.startswith('---'):
        lines = txt.splitlines()
        if lines and lines[0].strip() == '---':
            end = None
            for i in range(1, len(lines)):
                if lines[i].strip() == '---':
                    end = i
                    break
            if end is not None:
                yaml_txt = '\n'.join(lines[1:end])
                cfg = yaml.safe_load(yaml_txt)
    # fenced yaml block
    if cfg is None:
        m = re.search(r'```yaml\n(.*?)\n```', txt, re.S)
        if m:
            cfg = yaml.safe_load(m.group(1))
    # fallback: parse entire file as YAML
    if cfg is None:
        cfg = yaml.safe_load(txt)
    if not cfg or not isinstance(cfg, dict):
        raise ValueError(f"Configuration at {path} did not parse or is empty")
    return cfg


def validate_config(cfg, required_keys):
    """Ensure `cfg` contains all `required_keys`. Raises KeyError if any missing."""
    missing = [k for k in required_keys if k not in cfg]
    if missing:
        raise KeyError(f"Configuration missing required keys: {missing}")
    return True
