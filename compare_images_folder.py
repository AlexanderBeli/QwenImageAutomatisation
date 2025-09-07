# compare images2 VS no_watermarks
import os
import shutil
from pathlib import Path


def compare_and_sort_images(images_dir="images", no_watermarks_dir="no_watermarks", sorted_dir="sorted_images"):
    """
    Сравнивает папки images и no_watermarks, и перемещает файлы из images
    в sorted_images только если такие же файлы/папки есть в обеих исходных папках.

    Args:
        images_dir: путь к папке с изображениями
        no_watermarks_dir: путь к папке без водяных знаков
        sorted_dir: путь к папке для отсортированных изображений
    """

    # Преобразуем в объекты Path для удобства работы
    images_path = Path(images_dir)
    no_watermarks_path = Path(no_watermarks_dir)
    sorted_path = Path(sorted_dir)

    # Проверяем существование исходных папок
    if not images_path.exists():
        print(f"Папка {images_dir} не существует!")
        return

    if not no_watermarks_path.exists():
        print(f"Папка {no_watermarks_dir} не существует!")
        return

    # Создаем папку sorted_images если её нет
    sorted_path.mkdir(exist_ok=True)

    print(f"Начинаем сравнение папок {images_dir} и {no_watermarks_dir}...")

    # Рекурсивно обходим папку images
    for item_path in images_path.rglob("*"):
        if item_path.is_file():
            # Получаем относительный путь файла от корня images
            relative_path = item_path.relative_to(images_path)

            # Проверяем, есть ли такой же файл в no_watermarks
            corresponding_file = no_watermarks_path / relative_path

            if corresponding_file.exists():
                # Создаем целевую папку в sorted_images
                target_file = sorted_path / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Перемещаем файл
                try:
                    shutil.move(str(item_path), str(target_file))
                    print(f"Перемещен: {relative_path}")
                except Exception as e:
                    print(f"Ошибка при перемещении {relative_path}: {e}")

    # Удаляем пустые папки в images после перемещения
    remove_empty_dirs(images_path)

    print("Сортировка завершена!")


def remove_empty_dirs(path):
    """
    Рекурсивно удаляет пустые папки
    """
    for item in path.iterdir():
        if item.is_dir():
            remove_empty_dirs(item)
            # Проверяем, стала ли папка пустой после рекурсивного удаления
            try:
                if not any(item.iterdir()):
                    item.rmdir()
                    print(f"Удалена пустая папка: {item.relative_to(path.parent)}")
            except OSError:
                pass  # Папка не пустая или нет прав на удаление


def get_directory_structure(path, max_depth=3, current_depth=0):
    """
    Вспомогательная функция для просмотра структуры папок (для отладки)
    """
    items = []
    if current_depth >= max_depth:
        return items

    try:
        for item in sorted(Path(path).iterdir()):
            if item.is_dir():
                items.append(f"{'  ' * current_depth}📁 {item.name}/")
                items.extend(get_directory_structure(item, max_depth, current_depth + 1))
            else:
                items.append(f"{'  ' * current_depth}📄 {item.name}")
    except PermissionError:
        items.append(f"{'  ' * current_depth}❌ Нет доступа")

    return items


if __name__ == "__main__":
    # Можете изменить пути к папкам здесь
    IMAGES_DIR = "images2"
    NO_WATERMARKS_DIR = "no_watermarks"
    SORTED_DIR = "sorted_images"

    print("=== Скрипт сортировки изображений ===")
    print(f"Исходная папка: {IMAGES_DIR}")
    print(f"Папка для сравнения: {NO_WATERMARKS_DIR}")
    print(f"Папка назначения: {SORTED_DIR}")
    print()

    # Показываем структуру папок перед началом (опционально)
    response = input("Показать структуру папок перед началом? (y/n): ").lower().strip()
    if response == "y":
        print(f"\nСтруктура {IMAGES_DIR}:")
        structure = get_directory_structure(IMAGES_DIR)
        for item in structure[:20]:  # Показываем только первые 20 элементов
            print(item)
        if len(structure) > 20:
            print(f"... и еще {len(structure) - 20} элементов")

        print(f"\nСтруктура {NO_WATERMARKS_DIR}:")
        structure = get_directory_structure(NO_WATERMARKS_DIR)
        for item in structure[:20]:
            print(item)
        if len(structure) > 20:
            print(f"... и еще {len(structure) - 20} элементов")

    # Подтверждение перед началом
    print(f"\n⚠️  ВНИМАНИЕ: Файлы будут ПЕРЕМЕЩЕНЫ из {IMAGES_DIR} в {SORTED_DIR}")
    print("Пустые папки в images будут удалены.")
    confirmation = input("Продолжить? (yes/no): ").lower().strip()

    if confirmation in ["yes", "y", "да", "д"]:
        compare_and_sort_images(IMAGES_DIR, NO_WATERMARKS_DIR, SORTED_DIR)
    else:
        print("Операция отменена.")
