from pathlib import Path


def _find_project_root() -> Path:
    # Try to locate repository root by looking for common markers
    p = Path(__file__).resolve()
    for _ in range(20):
        if (p / 'main.py').exists() or (p / 'README.md').exists() or (p / '.env').exists():
            return p if (p / 'main.py').exists() or (p / 'README.md').exists() else p.parent
        p = p.parent
    # Fallback: assume two levels up is root
    return Path(__file__).resolve().parents[2]


def persist_settings_to_env(host: str, model: str, interval: str, theme: str) -> None:
    """Persist settings to a .env file at project root.
    Creates or updates keys: ollama_host, ollama_model, fetch_interval_minutes, ui_theme
    """
    root = _find_project_root()
    env_path = root / '.env'

    def read_env():
        if env_path.exists():
            with env_path.open('r', encoding='utf-8') as f:
                return f.readlines()
        return []

    def write_env(lines):
        with env_path.open('w', encoding='utf-8') as f:
            f.writelines(lines)

    lines = read_env()
    def set_var(key: str, value: str):
        nonlocal lines
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")

    set_var('ollama_host', host)
    set_var('ollama_model', model)
    set_var('fetch_interval_minutes', str(interval))
    set_var('ui_theme', theme)

    write_env(lines)
