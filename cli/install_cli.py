import pathlib
import os

bin_dir = pathlib.Path(os.path.expanduser("~/.local/bin"))
bin_dir.mkdir(parents=True, exist_ok=True)

bat = bin_dir / "cortex.bat"
content = '@echo off\nC:\\Python314\\python.exe "c:\\Projects\\Projrct Aeon\\qmind\\cli\\cortex.py" %*\n'
bat.write_text(content)
print(f"Created: {bat}")
print(f"Exists: {bat.exists()}")
