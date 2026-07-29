from pathlib import Path
import subprocess
import sys


workspace = Path(sys.argv[1]).resolve()
if (workspace / "verifier.py").exists() or (workspace / "reference.txt").exists():
    raise SystemExit("hidden material leaked into the agent workspace")
completed = subprocess.run(
    [sys.executable, "-c", "from calculator import add; assert add(2, 3) == 5"],
    cwd=workspace,
    check=False,
)
raise SystemExit(completed.returncode)
