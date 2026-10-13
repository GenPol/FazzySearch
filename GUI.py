import sys
import os
import shutil
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices

# --- Импорт обработчика ---
try:
    from PersonFinder import run_personfinder
except Exception as e:
    print(f"WARNING: Не удалось импортировать PersonFinder: {e}")
    run_personfinder = None

# --- Единообразное определение BASE_DIR (скрипт / .exe) ---
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR  = BASE_DIR / "Отчёты" / "Важные" / "temp_in"
OUTPUT_DIR = BASE_DIR / "Отчёты" / "Важные" / "temp_out"
TEMP_IN    = INPUT_DIR
TEMP_OUT   = OUTPUT_DIR

for d in (TEMP_IN, TEMP_OUT):
    d.mkdir(parents=True, exist_ok=True)

print(f"BASE_DIR: {BASE_DIR}")
print(f"TEMP_IN : {TEMP_IN}")
print(f"TEMP_OUT: {TEMP_OUT}")


class GuiLogHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        self.widget.append(self.format(record))


class DropArea(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fazzy Search")
        self.resize(700, 500)

        self.setStyleSheet("""
            QMainWindow { background-color: black; }
            QLabel { color: #FFD700; font-weight: bold; }
            QPushButton {
                background-color: black; color: #FFD700;
                border: 1px solid #FFD700; padding: 10px; font-size: 13px;
            }
            QPushButton:hover { background-color: #111111; }
            QProgressBar {
                border: 1px solid #FFD700; text-align: center;
                color: #FFD700; background-color: black;
            }
            QProgressBar::chunk { background-color: #FFD700; }
            QTextEdit {
                background-color: black; color: #FFD700;
                border: 1px solid #FFD700;
            }
        """)

        self.setAcceptDrops(True)
        self._last_file = None
        self.prepare_folders()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.input_label = QLabel("Перетащите Excel файл сюда")
        self.input_label.setAlignment(Qt.AlignCenter)
        self.input_label.setStyleSheet("border: 2px dashed #888; padding: 40px; font-size: 14px;")
        layout.addWidget(self.input_label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("""
            background-color: #000000; color: #FFD700;
            border: 1px solid #FFD700; font-family: Consolas; font-size: 12px;
        """)
        layout.addWidget(self.log_window)

        buttons_layout = QHBoxLayout()
        self.btn_person = QPushButton("Импорт сотрудников")
        self.btn_open  = QPushButton("Открыть папку")
        buttons_layout.addWidget(self.btn_person)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_open)
        layout.addLayout(buttons_layout)

        self.support_label = QLabel("техподдержка vk.com/skladnalad")
        self.support_label.setAlignment(Qt.AlignCenter)
        self.support_label.setStyleSheet("color: #888; font-size: 15px;")
        layout.addWidget(self.support_label)

        self._setup_logging()

        self.btn_person.clicked.connect(self.run_person)
        self.btn_open.clicked.connect(self.open_output_folder)

    def _setup_logging(self):
        logging.getLogger().handlers.clear()
        handler = GuiLogHandler(self.log_window)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def prepare_folders(self):
        for folder in (TEMP_IN, TEMP_OUT):
            folder.mkdir(parents=True, exist_ok=True)
            for f in folder.iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                except Exception:
                    pass

    def open_output_folder(self):
        abs_path = str(TEMP_OUT.resolve())
        self.log_window.append(f"📂 Открываю: {abs_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        file_path = urls[0].toLocalFile()
        if not file_path.lower().endswith((".xlsx", ".xls", ".xlsm")):
            self.log_window.append("❌ Разрешены только Excel-файлы")
            return

        dest_path = TEMP_IN / Path(file_path).name
        try:
            shutil.copy2(file_path, dest_path)
            self._last_file = str(dest_path)
            self.input_label.setText(f"📥 Загружен файл:\n{dest_path.name}")
            self.log_window.append(f"✅ Файл загружен: {dest_path.name}")
        except Exception as e:
            self.log_window.append(f"❌ Ошибка загрузки файла: {e}")

    def update_progress(self, value):
        self.progress.setValue(value)
        QApplication.processEvents()

    def run_person(self):
        if run_personfinder is None:
            self.log_window.append("❌ Модуль PersonFinder не загружен — проверьте импорт")
            return

        input_files = list(TEMP_IN.glob("*.*"))
        if not input_files and not self._last_file:
            self.log_window.append("⚠️ Нет файлов для обработки. Перетащите Excel.")
            return

        try:
            self.log_window.append("\n==============================")
            self.log_window.append("Запуск обработки сотрудников...")
            self.log_window.append(f"Вход:  {TEMP_IN}")
            self.log_window.append(f"Выход: {TEMP_OUT}")
            self.log_window.append("==============================\n")

            result = run_personfinder(
                input_dir=str(TEMP_IN),
                output_dir=str(TEMP_OUT),
                progress_callback=self.update_progress
            )

            if result:
                self.log_window.append(f"\n✅ Готово\nРезультат: {result}")
            else:
                self.log_window.append("\n✅ Обработка завершена")

            self.progress.setValue(100)

        except Exception as e:
            self.log_window.append(f"\n❌ Ошибка:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DropArea()
    window.show()
    sys.exit(app.exec_())