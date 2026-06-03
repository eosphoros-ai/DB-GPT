#!/usr/bin/env python3
"""Finish ru/common.ts: translate user-facing strings; keep brands, URLs, filenames."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RU_COMMON = ROOT / "web/locales/ru/common.ts"
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)

# Keys to leave exactly as in EN (brands, filenames, universal acronyms)
SKIP_KEYS = frozenset(
    {
        "sample_annual_report_2019.pdf",  # filename
    }
)

# key -> Russian UI label
TRANSLATE: dict[str, str] = {
    "URL": "URL",
    "Text_Source": "Источник текста (необязательно)",
    "Chunks": "Фрагменты",
    "Content": "Содержимое",
    "Meta_Data": "Метаданные",
    "Embedding": "Эмбеддинг",
    "topk": "Top-K",
    "recall_score": "Порог релевантности",
    "recall_type": "Тип поиска",
    "model": "Модель",
    "Automatic": "Автоматически",
    "Process": "Обработка",
    "chunk_size": "Размер фрагмента",
    "chunk_overlap": "Перекрытие фрагментов",
    "retrieve_mode": "Режим поиска",
    "Prompt": "Промпт",
    "max_token": "Макс. токенов",
    "max_iteration": "Макс. итераций",
    "concurrency_limit": "Лимит параллелизма",
    "Theme": "Тема",
    "Remark": "Примечание",
    "data_center_desc": "DB-GPT: интерфейс центра данных для удобного сопровождения и настройки.",
    "path": "Путь",
    "stop_model": "Остановить модель",
    "start_model": "Запустить модель",
    "model_deploy_name": "Имя модели",
    "Open_Sidebar": "Развернуть",
    "Prompt_Info_Sub_Scene": "Подсцена",
    "Prompt_Info_Content": "Содержимое",
    "Lowest": "Плохо",
    "Missed": "Не по теме",
    "Lost": "Упущено",
    "Incorrect": "Неверно",
    "Verbose": "Слишком подробно",
    "Best": "Отлично",
    "Q_A_Category": "Категория Q&A",
    "Q_A_Rating": "Оценка Q&A",
    "Update_From_Github": "Загрузить с GitHub",
    "Market_Plugins": "Плагины маркетплейса",
    "My_Plugins": "Мои плагины",
    "stacked_column_chart": "Столбчатая с накоплением",
    "column_chart": "Столбчатая",
    "percent_stacked_column_chart": "Столбчатая (% от суммы)",
    "grouped_column_chart": "Групповая столбчатая",
    "time_column": "Столбчатая (время)",
    "pie_chart": "Круговая",
    "line_chart": "Линейная",
    "area_chart": "Область",
    "stacked_area_chart": "Область с накоплением",
    "scatter_plot": "Точечная",
    "bubble_chart": "Пузырьковая",
    "stacked_bar_chart": "Полосовая с накоплением",
    "bar_chart": "Полосовая",
    "percent_stacked_bar_chart": "Полосовая (% от суммы)",
    "grouped_bar_chart": "Групповая полосовая",
    "water_fall_chart": "Водопад",
    "table": "Таблица",
    "multi_line_chart": "Несколько линий",
    "multi_measure_column_chart": "Несколько метрик (столбцы)",
    "multi_measure_line_chart": "Несколько метрик (линии)",
    "Advices": "Рекомендации",
    "used_apps": "Использованные приложения",
    "collect": "В избранное",
    "native_type": "Тип приложения",
    "yuque": "Документ Yuque",
    "Manual_entry": "Ручной ввод",
    "Data_content": "Содержимое данных",
    "Main_content": "Основной текст",
    "Auxiliary_data": "Вспомогательные данные",
    "View_details": "Подробности",
    "publish": "Опубликовать",
    "dbgpts_community": "Сообщество DBGPTS",
    "community_dbgpts": "DBGPTS сообщества",
    "my_dbgpts": "Мои DBGPTS",
    "Refresh_dbgpts": "Обновить из Git-репозитория сообщества",
    "workflow": "Рабочий процесс",
    "resources": "Ресурсы",
    "api_url": "URL API",
    "header_info": "HTTP-заголовок",
    "parse_strategy": "Стратегия разбора",
    "skills_github_url_label": "URL GitHub",
    "rounds_pending_replay": " раундов ожидают повтора…",
    "admin_employee_id_leading_zeros_removed": "Админ (табельный номер, без ведущих нулей):",
    "clear_history": "Очистить историю",
    "execution_process": "Процесс выполнения",
    "score_details": "Детали оценки",
    "no_knowledge_base_available": "Нет доступных баз знаний",
    "personal": "Личные",
    "evaluation_data": "Данные оценки",
    "manage_databases": "Управление БД →",
    "recall_results": "Результаты поиска",
    "started_successfully": "Успешно запущено",
    "start_evaluation": "Запустить оценку",
    "knowledge_bases_available": " баз знаний доступно",
    "invalid_header_json_format": "Неверный формат JSON в заголовках",
    "dataset_name": "Имя набора данных",
    "form_validation_failed": "Ошибка проверки формы:",
    "members": "Участники",
    "evaluation_status": "Статус оценки",
    "add_dataset": "Добавить набор данных",
    "manage_knowledge": "Управление знаниями →",
    "evaluation_metrics": "Метрики оценки",
    "no_matching_skills_found": "Подходящие навыки не найдены",
    "view_logs_and_scores": "Журнал и оценки",
    "score_threshold": "Порог оценки",
    "recall_configuration": "Настройки поиска",
    "encoding": "Кодировка",
    "validation_passed": "Проверка пройдена",
    "recall_method": "Метод поиска",
    "test": "Тест",
    "test_question": "Тестовый вопрос",
    "invalid_response_mapping_json_format": "Неверный формат JSON сопоставления ответа",
    "dataset": "Набор данных",
    "related_questions": "Связанные вопросы:",
    "enter_password": "Введите пароль",
    "your_feedback_helps_me_improve": "Ваш отзыв помогает улучшать ответы",
    "evaluation_metrics_2": "Метрики оценки",
    "no_matching_database_found": "Подходящая база не найдена",
    "evaluation_code": "Код оценки",
    "start_evaluation_2": "Запустить оценку",
    "help_center": "Справка",
}


def write_ts_values(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, val in updates.items():
        esc = val.replace("\\", "\\\\").replace("'", "\\'")
        text, n = re.subn(
            rf"^(\s+{re.escape(key)}\s*:\s*)'(?:\\'|[^'])*'",
            rf"\1'{esc}'",
            text,
            count=1,
            flags=re.M,
        )
        if not n:
            print(f"warn: missing {key}")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    en = dict(PAIR.findall((ROOT / "web/locales/en/common.ts").read_text(encoding="utf-8")))
    ru = dict(PAIR.findall(RU_COMMON.read_text(encoding="utf-8")))
    updates: dict[str, str] = {}
    skipped = []
    for key in ru:
        if key not in en or ru[key] != en[key]:
            continue
        if key in SKIP_KEYS:
            skipped.append(key)
            continue
        if key in TRANSLATE:
            updates[key] = TRANSLATE[key]
        else:
            print(f"unmapped: {key} = {en[key]!r}")
    write_ts_values(RU_COMMON, updates)
    print(f"updated: {len(updates)}, skipped: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
