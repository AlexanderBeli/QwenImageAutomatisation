"""
1320 картинок
Автоматическое удаление водяных знаков с изображений.
Загружает изображения из папки 'images' на сайт toolsmart.ai,
затем сохраняет обработанные изображения в папку 'no_watermarks'.
"""

import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import Browser, Download, Page, async_playwright

from logger_config import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class WatermarkRemover:
    """Класс для автоматического удаления водяных знаков с изображений."""

    def __init__(self):
        self.url = "https://www.toolsmart.ai/ru-RU/feature-free-watermark-remover/"
        self.images_folder = Path("images")
        self.output_folder = Path("no_watermarks")
        self.supported_formats = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".nef", ".dng", ".jpe"}

        # Создаем папку для сохранения результатов
        self.output_folder.mkdir(exist_ok=True)

    def get_image_files(self) -> list[Path]:
        """Получает список файлов изображений из папки images."""
        if not self.images_folder.exists():
            logger.error(f"Папка {self.images_folder} не существует")
            return []

        image_files = []
        for file_path in self.images_folder.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                image_files.append(file_path)

        logger.info(f"Найдено {len(image_files)} изображений для обработки")
        return sorted(image_files)

    async def wait_for_upload_completion(self, page: Page) -> bool:
        """Ожидает завершения загрузки и обработки изображения."""
        try:
            # Ждем появления области результата или области обработки
            logger.info("Ожидание завершения загрузки...")

            # Ждем либо область обработки, либо область с результатом
            await page.wait_for_selector(".process-area, .result-area", timeout=30000)

            # Если появилась область обработки, ждем появления результата
            process_area = await page.query_selector(".process-area")
            if process_area:
                logger.info("Изображение обрабатывается...")
                await page.wait_for_selector(".result-area", timeout=60000)
                logger.info("Обработка завершена")

            # Дополнительная пауза для стабилизации
            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"Ошибка при ожидании загрузки: {e}")
            return False

    async def upload_image(self, page: Page, image_path: Path) -> bool:
        """Загружает изображение на сайт."""
        try:
            logger.info(f"Загрузка изображения: {image_path.name}")

            # Ищем input для загрузки файла
            file_input = await page.query_selector('input[type="file"]')
            if not file_input:
                logger.error("Не найден элемент для загрузки файла")
                return False

            # Загружаем файл
            await file_input.set_input_files(str(image_path.absolute()))

            # Ожидаем завершения загрузки
            return await self.wait_for_upload_completion(page)

        except Exception as e:
            logger.error(f"Ошибка при загрузке изображения {image_path.name}: {e}")
            return False

    async def save_processed_image(self, page: Page, original_path: Path) -> bool:
        """Сохраняет обработанное изображение."""
        try:
            # Создаем путь для сохранения с сохранением структуры папок
            relative_path = original_path.relative_to(self.images_folder)
            output_path = self.output_folder / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Сохранение обработанного изображения: {output_path.name}")

            # Ищем кнопку скачивания
            download_button = await page.query_selector(".download-btn")
            if not download_button:
                logger.error("Не найдена кнопка скачивания")
                return False

            # Настраиваем обработчик скачивания
            async with page.expect_download() as download_info:
                await download_button.click()

            download = await download_info.value

            # Сохраняем файл
            await download.save_as(str(output_path))
            logger.info(f"Изображение сохранено: {output_path}")

            return True

        except Exception as e:
            logger.error(f"Ошибка при сохранении изображения: {e}")
            return False

    async def refresh_page(self, page: Page) -> bool:
        """Обновляет страницу для следующей загрузки."""
        try:
            logger.info("Обновление страницы...")
            await page.reload()

            # Ждем загрузки страницы
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            return True

        except Exception as e:
            logger.error(f"Ошибка при обновлении страницы: {e}")
            return False

    async def process_single_image(self, page: Page, image_path: Path) -> bool:
        """Обрабатывает одно изображение."""
        try:
            logger.info(f"Начало обработки: {image_path.name}")

            # Загружаем изображение
            if not await self.upload_image(page, image_path):
                return False

            # Сохраняем результат
            if not await self.save_processed_image(page, image_path):
                return False

            logger.info(f"Успешно обработано: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при обработке {image_path.name}: {e}")
            return False

    async def run(self) -> None:
        """Запускает основной процесс обработки изображений."""
        # Получаем список изображений
        image_files = self.get_image_files()
        if not image_files:
            logger.warning("Не найдено изображений для обработки")
            return

        # Статистика
        processed_count = 0
        failed_count = 0

        async with async_playwright() as p:
            # Запускаем браузер
            browser = await p.chromium.launch(
                headless=False, args=["--no-sandbox", "--disable-web-security"]  # Показываем браузер для отладки
            )

            try:
                # Создаем контекст браузера
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )

                # Открываем страницу
                page = await context.new_page()

                logger.info(f"Переход на сайт: {self.url}")
                await page.goto(self.url)
                await page.wait_for_load_state("networkidle")

                # Обрабатываем каждое изображение
                for i, image_path in enumerate(image_files, 1):
                    logger.info(f"Обработка {i}/{len(image_files)}: {image_path.name}")

                    # Если это не первое изображение, обновляем страницу
                    if i > 1:
                        if not await self.refresh_page(page):
                            logger.error(f"Не удалось обновить страницу для {image_path.name}")
                            failed_count += 1
                            continue

                    # Обрабатываем изображение
                    if await self.process_single_image(page, image_path):
                        processed_count += 1
                    else:
                        failed_count += 1

                    # Пауза между обработками
                    if i < len(image_files):
                        logger.info("Пауза между обработками...")
                        await asyncio.sleep(3)

            finally:
                await browser.close()

        # Выводим статистику
        logger.info(f"Обработка завершена!")
        logger.info(f"Успешно обработано: {processed_count}")
        logger.info(f"Неудачных попыток: {failed_count}")
        logger.info(f"Всего изображений: {len(image_files)}")


async def main():
    """Основная функция."""
    try:
        logger.info("Запуск программы удаления водяных знаков")

        remover = WatermarkRemover()
        await remover.run()

        logger.info("Программа завершена успешно")

    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
