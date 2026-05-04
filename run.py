from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / "Site-GPTcode"

if not PROJECT_DIR.exists():
    raise SystemExit(
        f"Pasta do projeto nao encontrada em: {PROJECT_DIR}"
    )

sys.path.insert(0, str(PROJECT_DIR))

from backend.app import app


if __name__ == "__main__":
    app.run(debug=True, port=5000)
