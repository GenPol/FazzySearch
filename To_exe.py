import os
import subprocess
import sys

APP_NAME = "Fazzy Search"
MAIN_FILE = "GUI.py"
ICON_FILE = "logo.ico"

cmd = [
    sys.executable,
    "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--clean",
    "--name", APP_NAME,
    "--icon", ICON_FILE,
    "--hidden-import", "openpyxl",
    "--hidden-import", "rapidfuzz",
    MAIN_FILE
]

print("=" * 50)
print("Сборка началась...")
print("=" * 50)

result = subprocess.run(cmd)

if result.returncode == 0:
    print("\nСборка завершена успешно!")
    print(f"EXE файл: dist\\{APP_NAME}.exe")
else:
    print("\nОшибка сборки.")