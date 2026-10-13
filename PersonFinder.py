import pandas as pd
import re
import logging
import sys
from pathlib import Path
from rapidfuzz import fuzz, process

# =========================================================
# БАЗОВАЯ ПАПКА (ДЛЯ .EXE И СКРИПТА)
# =========================================================
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# =========================================================
# ПУТИ ПО УМОЛЧАНИЮ
# =========================================================
INPUT_DIR = BASE_DIR / "Отчёты" / "Fazzy" / "temp_in"
OUTPUT_DIR = BASE_DIR / "Отчёты" / "Fazzy" / "temp_out"
EMPLOYEES_FILE = BASE_DIR / "Отчёты" / "Fazzy" / "Сотрудники.xlsx"

# =========================================================
# НАСТРОЙКИ НЕОДНОЗНАЧНОСТИ
# =========================================================
AMBIGUITY_THRESHOLD = 5.0    # если 2-й кандидат отстаёт от 1-го < 5% — выводим оба
MAX_MATCHES_PER_ROW = 3      # максимум альтернатив на одну строку исходника

# =========================================================
# НОРМАЛИЗАЦИЯ ТЕКСТА
# =========================================================
def normalize_text(text):
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9_\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# =========================================================
# ИСКЛЮЧЕНИЯ (ВШИТЫ В КОД)
# =========================================================
INTERNAL_COMPANIES = set()  # сюда можно вписать внутренние компании

def is_internal_company(company):
    return normalize_text(company) in INTERNAL_COMPANIES

def normalize_company(company):
    return normalize_text(company)

def detect_type(text):
    t = normalize_text(text)
    if t.startswith("а_"):
        return "OUTSTAFF"
    if t.startswith("к_"):
        return "COMMAND"
    return "INTERNAL"

def split_fio(text):
    parts = normalize_text(text).split()
    return (parts[0] if len(parts) > 0 else "",
            parts[1] if len(parts) > 1 else "",
            parts[2] if len(parts) > 2 else "")

def strict_score(a, b):
    a_s, a_n, a_p = split_fio(a)
    b_s, b_n, b_p = split_fio(b)
    s_score = fuzz.ratio(a_s, b_s)
    if s_score < 80:
        return 0
    score = s_score * 0.7
    if a_n and b_n:
        score += fuzz.ratio(a_n, b_n) * 0.2
    if a_p and b_p:
        score += fuzz.ratio(a_p, b_p) * 0.1
    return score

def parse_outstaff(text):
    t = normalize_text(text)
    parts = t.split("_")
    fio = parts[1] if len(parts) > 1 else ""
    company = parts[-1] if len(parts) > 2 else ""
    return fio, company

# =========================================================
# ЗАГРУЗКА СОТРУДНИКОВ (ИМЯ + ID)
# =========================================================
def load_employees(file_path):
    """Читает файл сотрудников. Возвращает список словарей {'name', 'id'}."""
    df = pd.read_excel(file_path)
    if df.empty:
        return []

    # Ищем колонку с ФИО
    name_col = None
    for col in df.columns:
        c = str(col).lower()
        if any(k in c for k in ("фио", "ф.и.о", "имя", "сотрудник", "name")):
            name_col = col
            break
    if name_col is None:
        name_col = df.columns[0]

    # Ищем колонку с ID
    id_col = None
    for col in df.columns:
        c = str(col).lower().strip()
        if c in ("id", "ид", "код", "табельный", "номер", "№"):
            id_col = col
            break

    employees = []
    for i, row in df.iterrows():
        name = row[name_col]
        if pd.isna(name) or not str(name).strip():
            continue
        if id_col is not None and not pd.isna(row[id_col]):
            emp_id = row[id_col]
        else:
            emp_id = i + 1  # порядковый номер, если ID-колонки нет
        employees.append({"name": str(name), "id": emp_id})
    return employees

# =========================================================
# ОСНОВНАЯ ФУНКЦИЯ (ВЫЗЫВАЕТСЯ ИЗ GUI)
# =========================================================
def run_personfinder(input_dir=None, output_dir=None, progress_callback=None):
    in_dir = Path(input_dir) if input_dir else INPUT_DIR
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR

    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not EMPLOYEES_FILE.exists():
        raise FileNotFoundError(f"Не найден файл сотрудников: {EMPLOYEES_FILE}")

    logging.info("=== PERSON FINDER START ===")

    # Ищем только Excel-файлы
    files = [
        f for f in in_dir.glob("*")
        if f.suffix.lower() in ('.xlsx', '.xls', '.xlsm')
    ]
    if not files:
        raise Exception("Папка temp_in пуста или не содержит Excel-файлов")

    shift_file = files[0]
    output_file = out_dir / "РЕЗУЛЬТАТ.xlsx"

    employees = load_employees(EMPLOYEES_FILE)
    if not employees:
        raise Exception("Файл сотрудников пуст или не удалось прочитать ФИО")
    employee_names = [e["name"] for e in employees]

    def load_shift_file(file_path):
        excel = pd.ExcelFile(file_path)
        for sheet in excel.sheet_names:
            if "ноч" in sheet.lower():
                logging.info(f"Найден лист: {sheet}")
                return pd.read_excel(file_path, sheet_name=sheet)
        logging.info("Специальный лист не найден. Используется первый лист.")
        return pd.read_excel(file_path, sheet_name=0)

    shift_df = load_shift_file(shift_file)
    total_rows = len(shift_df)
    results = []
    id_counter = 0  # сквозной счётчик ID по строкам исходного файла

    for idx, (_, row) in enumerate(shift_df.iterrows(), start=1):
        number = row.iloc[0]
        raw = str(row.iloc[1])
        emp_type = detect_type(raw)

        if emp_type == "OUTSTAFF":
            search_base, company = parse_outstaff(raw)
            if not is_internal_company(company):
                search_base = f"{search_base} {normalize_company(company)}"
        elif emp_type == "COMMAND":
            search_base = raw.replace("к_", "").strip()
        else:
            search_base = raw

        search_base = normalize_text(search_base)

        # ---------- Строгий скоринг ----------
        candidates = []  # список (employee_dict, score)
        for emp in employees:
            score = strict_score(search_base, emp["name"])
            if score > 0:
                candidates.append((emp, score))

        # ---------- Мягкий fallback ----------
        if not candidates:
            fallback = process.extract(
                search_base,
                employee_names,
                scorer=fuzz.partial_ratio,
                limit=MAX_MATCHES_PER_ROW * 2,
            )
            # rapidfuzz возвращает (match, score, index)
            for m, s, i in fallback:
                candidates.append((employees[i], s))

        candidates.sort(key=lambda x: x[1], reverse=True)

        # ---------- Отбор «похожих» кандидатов ----------
        top_matches = []
        if candidates:
            best_score = candidates[0][1]
            for emp, score in candidates:
                if not top_matches or (best_score - score) <= AMBIGUITY_THRESHOLD:
                    top_matches.append((emp, score))
                else:
                    break
            top_matches = top_matches[:MAX_MATCHES_PER_ROW]

        # ---------- Запись результата ----------
        id_counter += 1

        if not top_matches:
            results.append({
                "ID": id_counter,
                "№": number,
                "Имя": raw,
                "Результат": "НЕ НАЙДЕНО",
                "%": 0,
            })
            logging.info(f"[{id_counter}] {raw} -> НЕ НАЙДЕНО")

        elif len(top_matches) == 1:
            emp, score = top_matches[0]
            results.append({
                "ID": id_counter,
                "№": number,
                "Имя": raw,
                "Результат": emp["name"],
                "%": round(score, 2),
            })
            logging.info(f"[{id_counter}] {raw} -> {emp['name']} ({score:.2f})")

        else:
            # Неоднозначность: ID с приставкой .01, .02, ...
            for j, (emp, score) in enumerate(top_matches, start=1):
                row_id = round(id_counter + j * 0.01, 2)
                results.append({
                    "ID": row_id,
                    "№": number,
                    "Имя": raw,
                    "Результат": emp["name"],
                    "%": round(score, 2),
                })
                logging.info(
                    f"[{id_counter}.{j:02d}] {raw} -> {emp['name']} ({score:.2f})"
                )

        if progress_callback:
            progress_callback(int(idx * 100 / total_rows))

    df = pd.DataFrame(results)
    df.to_excel(output_file, index=False)

    logging.info(f"ГОТОВО -> {output_file}")
    return str(output_file)