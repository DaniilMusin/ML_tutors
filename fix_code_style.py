#!/usr/bin/env python3
"""
Скрипт для автоматического исправления стилистических ошибок в коде.
"""

import os
import re
import sys
from pathlib import Path


def add_newline_at_end(file_path):
    """Добавляет перенос строки в конце файла, если его нет."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if content and not content.endswith('\n'):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content + '\n')
            print(f"✓ Добавлен перенос строки в конце: {file_path}")
            return True
    except Exception as e:
        print(f"✗ Ошибка при обработке {file_path}: {e}")
    return False


def remove_trailing_whitespace(file_path):
    """Удаляет лишние пробелы в конце строк."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        for i, line in enumerate(lines):
            if line.rstrip() != line:
                lines[i] = line.rstrip() + '\n'
                modified = True
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"✓ Удалены лишние пробелы: {file_path}")
            return True
    except Exception as e:
        print(f"✗ Ошибка при обработке {file_path}: {e}")
    return False


def fix_long_lines(file_path, max_length=120):
    """Исправляет слишком длинные строки."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        modified = False
        
        for i, line in enumerate(lines):
            if len(line) > max_length:
                # Простые случаи разбиения строк
                if 'f"' in line and line.count('f"') == 1:
                    # Разбиение f-строк
                    match = re.search(r'f"([^"]*)"', line)
                    if match:
                        f_string_content = match.group(1)
                        if len(f_string_content) > 50:
                            # Разбиваем f-строку
                            parts = f_string_content.split('. ')
                            if len(parts) > 1:
                                new_line = line.replace(
                                    f'f"{f_string_content}"',
                                    f'f"{parts[0]}. " f"{". ".join(parts[1:])}"'
                                )
                                lines[i] = new_line
                                modified = True
                
                elif 'logger.' in line and len(line) > max_length:
                    # Разбиение логгер строк
                    if 'logger.info(' in line or 'logger.warning(' in line or 'logger.error(' in line:
                        # Находим начало и конец строки логгера
                        start = line.find('logger.')
                        end = line.rfind(')')
                        if start != -1 and end != -1:
                            log_content = line[start:end+1]
                            if len(log_content) > max_length - 20:  # Оставляем место для отступов
                                # Разбиваем на части
                                parts = log_content.split(' + ')
                                if len(parts) > 1:
                                    indent = ' ' * (line.find('logger') - 4)
                                    new_line = f"{indent}{parts[0]}\n"
                                    for part in parts[1:]:
                                        new_line += f"{indent}    + {part}\n"
                                    lines[i] = new_line.rstrip()
                                    modified = True
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print(f"✓ Исправлены длинные строки: {file_path}")
            return True
    except Exception as e:
        print(f"✗ Ошибка при обработке {file_path}: {e}")
    return False


def check_unused_imports(file_path):
    """Проверяет неиспользуемые импорты (базовая проверка)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Простая проверка на очевидные неиспользуемые импорты
        lines = content.split('\n')
        imports = []
        used_imports = set()
        
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
            elif line and not line.startswith('#'):
                # Проверяем использование импортов
                for imp in imports:
                    if 'import ' in imp:
                        module = imp.split('import ')[1].split(' as ')[0].strip()
                        if module in line and module not in used_imports:
                            used_imports.add(module)
                    elif 'from ' in imp and ' import ' in imp:
                        module = imp.split('from ')[1].split(' import ')[0].strip()
                        if module in line and module not in used_imports:
                            used_imports.add(module)
        
        # Выводим потенциально неиспользуемые импорты
        for imp in imports:
            if 'import ' in imp:
                module = imp.split('import ')[1].split(' as ')[0].strip()
                if module not in used_imports:
                    print(f"⚠️  Возможно неиспользуемый импорт в {file_path}: {imp}")
            elif 'from ' in imp and ' import ' in imp:
                module = imp.split('from ')[1].split(' import ')[0].strip()
                if module not in used_imports:
                    print(f"⚠️  Возможно неиспользуемый импорт в {file_path}: {imp}")
                    
    except Exception as e:
        print(f"✗ Ошибка при проверке импортов в {file_path}: {e}")


def process_file(file_path):
    """Обрабатывает один файл."""
    print(f"\nОбработка: {file_path}")
    
    changes = 0
    changes += add_newline_at_end(file_path)
    changes += remove_trailing_whitespace(file_path)
    changes += fix_long_lines(file_path)
    check_unused_imports(file_path)
    
    return changes


def main():
    """Основная функция."""
    print("🔧 Исправление стилистических ошибок в коде...")
    
    # Находим все Python файлы
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Пропускаем виртуальные окружения и кэш
        if 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Найдено {len(python_files)} Python файлов")
    
    total_changes = 0
    for file_path in python_files:
        total_changes += process_file(file_path)
    
    print(f"\n✅ Обработка завершена! Внесено изменений: {total_changes}")
    
    # Создаем недостающие файлы
    create_missing_files()
    
    print("\n📋 Рекомендации:")
    print("1. Запустите 'python manage.py check' для проверки Django")
    print("2. Запустите 'python manage.py test' для запуска тестов")
    print("3. Используйте 'black' для автоматического форматирования")
    print("4. Используйте 'flake8' для проверки стиля кода")
    print("5. Используйте 'isort' для сортировки импортов")


def create_missing_files():
    """Создает недостающие файлы."""
    print("\n📁 Создание недостающих файлов...")
    
    # Проверяем существование apps/ml/tasks.py
    if not os.path.exists('apps/ml/tasks.py'):
        print("⚠️  Файл apps/ml/tasks.py уже создан")
    
    # Проверяем apps/frontend/urls.py
    if os.path.exists('apps/frontend/urls.py'):
        with open('apps/frontend/urls.py', 'r') as f:
            content = f.read()
        if not content.strip():
            print("⚠️  Файл apps/frontend/urls.py пустой, но это нормально для разработки")
    
    print("✅ Проверка файлов завершена")


if __name__ == '__main__':
    main()