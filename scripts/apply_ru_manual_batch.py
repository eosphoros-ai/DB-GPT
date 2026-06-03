#!/usr/bin/env python3
"""Apply hand-reviewed RU strings for keys still in English or garbled."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "web" / "locales"
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)

# key -> Russian (common + chat subsets)
MANUAL: dict[str, str] = {
    # RAG / knowledge
    "the_top_k_vectors": "Топ-K векторов по оценке сходства",
    "Set_a_threshold_score": "Порог для отбора похожих векторов",
    "A_model_used": "Модель для векторных представлений текста и данных",
    "Automatic_desc": "Автоматические правила сегментации и предобработки",
    "The_size_of_the_data_chunks": "Размер фрагментов данных при обработке",
    "The_amount_of_overlap": "Перекрытие между соседними фрагментами",
    "The_strategy_of_query_retrival": "Стратегия поиска при обработке запроса",
    "A_contextual_parameter": "Контекстный параметр среды, в которой используется промпт",
    "structure_or_format": "Готовая структура промпта для единообразного стиля ответов",
    "The_maximum_number_of_tokens": "Максимум токенов или слов в промпте",
    "scene": "Сцена",
    "template": "Шаблон",
    "Port": "Порт",
    "Username": "Имя пользователя",
    "Password": "Пароль",
    # Evaluation
    "evaluation_dataset_info": "Сведения о наборе данных оценки",
    "refresh_list": "Обновить список",
    "new_evaluation_task": "Новая задача оценки",
    "task_name": "Имя задачи",
    "models_to_evaluate": "Модели для оценки",
    "get_model_list_failed": "Не удалось получить список моделей",
    "create_evaluation_failed": "Не удалось создать задачу оценки",
    "evaluation_dataset_name": "Имя набора данных",
    "finish_time": "Время завершения",
    "model_name": "Имя модели",
    "round_time": "Время раунда",
    "dataset_evaluation_detail": "Отчёт по оценке набора данных",
    "back_to_list": "Назад к списку",
    "download_evaluation_result": "Скачать результат оценки",
    "get_evaluation_result_failed": "Не удалось получить результат оценки",
    "model_count": "Число моделей",
    "total_questions": "Всего вопросов",
    "correct_questions": "Верных ответов",
    "wrong_questions": "Неверных ответов",
    "failed_questions": "Неудачных вопросов",
    "overview": "Обзор",
    "round": "Раунд",
    "question_count": "Число вопросов",
    "executable_rate": "Доля исполняемых",
    "accuracy": "Точность",
    "evaluation_datasets": "Наборы данных для оценки",
    "back_to_evaluation_task_list": "Назад к списку задач оценки",
    "dataset_list": "Список наборов данных",
    "table_data": "Данные таблицы",
    "only_show_first_10_data": "(Показаны первые 10 строк)",
    "get_dataset_list_failed": "Не удалось получить список наборов данных",
    "get_table_list_failed": "Не удалось получить список таблиц",
    "get_table_data_failed": "Не удалось получить данные таблицы",
    "tables": "Таблицы",
    "evaluation_type": "Тип оценки",
    "evaluate_model": "Оценить модель",
    "http_method": "HTTP-метод",
    "header_info_placeholder": 'JSON заголовков, напр.:\\n{\\n  "Authorization": "Bearer token"\\n}',
    "parse_strategy_direct": "DIRECT — API возвращает SQL напрямую",
    "parse_strategy_json_path": "JSON_PATH — извлечение SQL через JSONPath",
    "response_mapping": "Сопоставление ответа",
    "response_mapping_placeholder": 'JSON сопоставления, напр.:\\n{\\n  "sql": "$.data.content"\\n}',
    "api_timeout": "Таймаут API",
    "timeout_range_validation": "Таймаут: от 1 до 2000 секунд",
    "api_timeout_placeholder": "Таймаут, напр.: 300",
    "evaluation_env": "Среда оценки",
    "please_select_evaluation_env": "Выберите среду оценки",
    "evaluation_env_dev": "Dev-набор",
    "evaluation_env_test": "Test-набор",
    "evaluation_env_dev_tooltip": "Набор для локальной разработки и отладки",
    "evaluation_env_test_tooltip": "Набор для официальной оценки и рейтинга",
    # Garbled / phase2 fixes
    "deleted_successfully": "Удалено",
    "added_successfully": "Добавлено",
    "search_knowledge_base": "Поиск базы знаний",
    "search_database": "Поиск базы данных",
    "pending": "В ожидании",
    "are_you_sure_you_want_to_delete": "Удалить?",
    "ask_me_anything": "Спросите что угодно",
    "dataset_count": "Число наборов данных",
    "file_download_failed": "Не удалось скачать файл",
    "no_matching_conversations": "Нет подходящих диалогов",
    "new_chat_2": "Новый чат",
    "invalid_data_format": "Неверный формат данных",
    "failed_to_load_evaluation_list": "Не удалось загрузить список оценок",
    "end_topic": "Завершить тему",
    "permission_management": "Управление правами",
    "failed_to_load_chat_history": "Не удалось загрузить историю чата",
    "scene_type": "Тип сцены",
    "enter_a_test_question": "Введите тестовый вопрос",
    "sql_query": "SQL-запрос",
    "confirm_delete": "Подтвердить удаление?",
    "databases_available": " баз доступно",
    "no_suitable_chart_view": "Нет подходящего типа диаграммы",
    "evaluation_results": "Результаты оценки",
    "failed_to_load_example": "Не удалось загрузить пример: ",
    "no_history_yet": "Истории пока нет",
    "steps": " шагов",
    "no_matching_knowledge_base": "Нет подходящей базы знаний",
    "numeric": "Числовой",
    "parallel_parameters": "Параллельные параметры",
    "request_error": "Ошибка запроса",
    "api_interface_abnormal": "Сбой интерфейса. Повторите позже.",
    "network_error": "Сетевая ошибка",
}

CHAT_MANUAL: dict[str, str] = {
    "db_gpt_computer": "Компьютер DB-GPT",
    "feedback_submitted": "Отзыв отправлен",
    "data_type": "Тип данных",
    "saturday": "Суббота",
    "you_might_want_to_ask": "Возможно, вас интересует:",
    "column_info": "Информация о столбце",
    "field_list": "Список полей:",
    "copy_all": "Копировать всё",
    "operation_successful": "Действие выполнено",
    "tuesday": "Вторник",
    "view_reply_reference": "Ссылки в ответе",
    "thursday": "Четверг",
    "friday": "Пятница",
    "items": " элементов)",
    "popup_blocked_by_browser_please_allow_and_retry": "Всплывающее окно заблокировано. Разрешите и повторите.",
    "download_successful": "Скачано",
    "data_size": "Размер данных:",
    "monday": "Понедельник",
    "download_failed": "Ошибка скачивания",
    "sunday": "Воскресенье",
    "wednesday": "Среда",
    "click_to_analyze_current_anomaly": "Нажмите для анализа аномалии",
    "reply_reference": "Ссылки ответа",
    "link": "Ссылка",
    "sql_copied_to_clipboard": "SQL скопирован в буфер",
    "column": "Столбец",
    "code_file": "Файл кода",
    "source_code": "Исходный код",
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
            print(f"warn: {path.name}: {key}")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    for mod, keys in (
        ("common", MANUAL),
        ("chat", CHAT_MANUAL),
    ):
        ru_path = LOCALES / "ru" / f"{mod}.ts"
        existing = set(PAIR.findall(ru_path.read_text(encoding="utf-8")))
        updates = {k: v for k, v in keys.items() if k in dict(existing)}
        if updates:
            write_ts_values(ru_path, updates)
            print(f"{mod}: {len(updates)} manual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
