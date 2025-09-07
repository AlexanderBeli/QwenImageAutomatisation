# Улучшенная версия: 5 картинок на браузер + циклические прокси
import json
import os
import pickle
import signal
import subprocess
import tempfile
import time
from multiprocessing import Manager, Process, Queue, Value
from pathlib import Path


def worker_process(worker_id, task_queue, stats, all_proxies_data, batch_size=5):
    """
    Процесс воркера - обрабатывает батчи по 5 изображений
    Использует все прокси циклически
    """
    print(f"Worker {worker_id}: Process started with {len(all_proxies_data)} total proxies")

    processed_count = 0
    current_proxy_index = worker_id  # Начинаем с разных прокси для каждого воркера

    # Создаем модифицированный скрипт для этого воркера
    temp_script = f"batch_worker_{worker_id}.py"

    try:
        # Читаем оригинальный код
        with open("main_proxies.py", "r", encoding="utf-8") as f:
            original_code = f.read()

        # Модификация для работы с батчами и циклическими прокси
        modified_code = f"""
import sys
import json
from pathlib import Path

# Прокси для всех воркеров (циклическое использование)
ALL_PROXIES_DATA = {repr(all_proxies_data)}

class CyclicProxyManager:
    def __init__(self, worker_id={worker_id}, start_index={current_proxy_index}):
        self.worker_id = worker_id
        self.current_index = start_index
        self.proxies = []
        self.load_proxies()
    
    def load_proxies(self):
        for proxy_line in ALL_PROXIES_DATA:
            if proxy_line and ":" in proxy_line:
                parts = proxy_line.split(":")
                if len(parts) >= 4:
                    host = parts[0]
                    port = parts[1]
                    username = parts[2]
                    password = parts[3]
                    proxy_config = {{
                        "server": f"http://{{host}}:{{port}}",
                        "username": username,
                        "password": password,
                    }}
                    self.proxies.append(proxy_config)
        print(f"Worker {worker_id}: Loaded {{len(self.proxies)}} total proxies for cycling")
    
    def get_next_proxy(self):
        if not self.proxies:
            return None
        
        # Циклическое использование всех прокси
        proxy = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        return proxy
    
    def get_current_proxy_info(self):
        if not self.proxies:
            return "No proxy"
        current_idx = (self.current_index - 1) % len(self.proxies)
        proxy = self.proxies[current_idx]
        return f"Worker {worker_id} using proxy {{current_idx + 1}}/{{len(self.proxies)}}: {{proxy['server']}}"

# Заменяем оригинальный ProxyManager
ProxyManager = CyclicProxyManager

{original_code}

async def process_batch_of_images(batch_tasks):
    \"\"\"Обработать батч изображений в одном браузере\"\"\"
    if not batch_tasks:
        return []
    
    print(f"Worker {worker_id}: Processing batch of {{len(batch_tasks)}} images")
    
    remover = WatermarkRemover(
        images_folder="images2",
        output_folder="no_watermarks",
        batch_size={batch_size}
    )
    
    # Получаем прокси для этого батча
    proxy_config = remover.proxy_manager.get_next_proxy()
    if not proxy_config:
        print(f"Worker {worker_id}: No proxy available")
        return []
    
    # Настраиваем браузер ОДИН РАЗ для всего батча
    if not await remover.setup_browser_with_proxy(proxy_config):
        print(f"Worker {worker_id}: Failed to setup browser")
        return []
    
    # Аутентификация ОДИН РАЗ
    if not await remover.handle_authentication():
        print(f"Worker {worker_id}: Authentication failed")
        await remover.cleanup_browser()
        return []
    
    print(f"Worker {worker_id}: Browser ready, processing {{len(batch_tasks)}} images...")
    
    # Обрабатываем все изображения в батче
    results = []
    for i, (image_path_str, output_folder_str) in enumerate(batch_tasks, 1):
        image_path = Path(image_path_str)
        output_folder = Path(output_folder_str)
        
        print(f"Worker {worker_id}: [{{i}}/{{len(batch_tasks)}}] {{image_path.name}}")
        
        try:
            success = await remover.process_single_image(image_path, output_folder)
            results.append((image_path_str, success))
            
            if success:
                print(f"Worker {worker_id}: ✅ {{image_path.name}}")
            else:
                print(f"Worker {worker_id}: ❌ {{image_path.name}}")
            
            # Пауза между изображениями в батче
            if i < len(batch_tasks):
                import random
                await asyncio.sleep(random.uniform(3, 8))
                
        except Exception as e:
            print(f"Worker {worker_id}: Error processing {{image_path.name}}: {{e}}")
            results.append((image_path_str, False))
    
    # Закрываем браузер ОДИН РАЗ после всего батча
    await remover.cleanup_browser()
    
    return results

async def main_batch_worker():
    if len(sys.argv) < 2:
        print("Usage: script.py <batch_json>")
        return []
    
    # Загружаем батч задач из JSON
    batch_json = sys.argv[1]
    with open(batch_json, 'r') as f:
        batch_tasks = json.load(f)
    
    return await process_batch_of_images(batch_tasks)

if __name__ == "__main__":
    import asyncio
    try:
        results = asyncio.run(main_batch_worker())
        # Сохраняем результаты
        results_file = f"results_worker_{worker_id}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f)
        sys.exit(0)
    except Exception as e:
        print(f"Worker {worker_id}: Error: {{e}}")
        sys.exit(1)
"""

        # Записываем модифицированный скрипт
        with open(temp_script, "w", encoding="utf-8") as f:
            f.write(modified_code)

        # Основной цикл воркера - обрабатываем батчи
        while True:
            try:
                # Собираем батч задач из очереди
                batch_tasks = []

                # Собираем до batch_size задач или до таймаута
                for _ in range(batch_size):
                    try:
                        task = task_queue.get(timeout=30)  # 30 сек на получение задачи
                        if task is None:  # Сигнал остановки
                            if batch_tasks:
                                break  # Обрабатываем оставшиеся задачи
                            else:
                                print(f"Worker {worker_id}: Stop signal received")
                                return
                        batch_tasks.append(task)
                    except:
                        # Таймаут - если есть задачи в батче, обрабатываем их
                        if batch_tasks:
                            break
                        else:
                            # Проверяем, есть ли еще задачи
                            if task_queue.empty():
                                print(f"Worker {worker_id}: No more tasks")
                                return
                            continue

                if not batch_tasks:
                    continue

                print(f"Worker {worker_id}: Got batch of {len(batch_tasks)} images")

                # Создаем временный файл с батчем
                batch_file = f"batch_worker_{worker_id}_{int(time.time())}.json"
                with open(batch_file, "w") as f:
                    json.dump(batch_tasks, f)

                # Запускаем обработку батча как subprocess
                start_time = time.time()
                result = subprocess.run(
                    ["python", temp_script, batch_file], capture_output=True, text=True, timeout=1800
                )  # 30 минут на батч

                elapsed = time.time() - start_time

                # Обрабатываем результаты
                results_file = f"results_worker_{worker_id}.json"
                batch_success_count = 0
                batch_failed_count = 0

                if result.returncode == 0 and Path(results_file).exists():
                    try:
                        with open(results_file, "r") as f:
                            results = json.load(f)

                        for image_path, success in results:
                            if success:
                                batch_success_count += 1
                                stats["processed"] += 1
                            else:
                                batch_failed_count += 1
                                stats["failed"] += 1
                                # Возвращаем неудачные задачи в очередь
                                for orig_task in batch_tasks:
                                    if orig_task[0] == image_path:
                                        task_queue.put(orig_task)
                                        break

                        os.remove(results_file)

                    except Exception as e:
                        print(f"Worker {worker_id}: Error reading results: {e}")
                        batch_failed_count = len(batch_tasks)
                        stats["failed"] += batch_failed_count
                        # Возвращаем все задачи в очередь
                        for task in batch_tasks:
                            task_queue.put(task)
                else:
                    print(f"Worker {worker_id}: Batch failed - {result.stderr[:200]}")
                    batch_failed_count = len(batch_tasks)
                    stats["failed"] += batch_failed_count
                    # Возвращаем все задачи в очередь
                    for task in batch_tasks:
                        task_queue.put(task)

                processed_count += batch_success_count

                print(
                    f"Worker {worker_id}: Batch completed - ✅{batch_success_count} ❌{batch_failed_count} ({elapsed:.1f}s)"
                )

                # Очищаем временные файлы
                try:
                    os.remove(batch_file)
                except:
                    pass

            except subprocess.TimeoutExpired:
                print(f"Worker {worker_id}: Batch timeout")
                stats["failed"] += len(batch_tasks)
                for task in batch_tasks:
                    task_queue.put(task)
            except Exception as e:
                print(f"Worker {worker_id}: Error: {e}")
                time.sleep(10)

    finally:
        # Очистка
        try:
            os.remove(temp_script)
        except:
            pass

        print(f"Worker {worker_id}: Finished. Total processed: {processed_count} images")


class ImprovedMultiprocessManager:
    def __init__(self, images_folder="images2", output_folder="no_watermarks", num_workers=5, batch_size=5):
        self.images_folder = Path(images_folder)
        self.output_folder = Path(output_folder)
        self.num_workers = num_workers
        self.batch_size = batch_size

        print(f"ImprovedMultiprocessManager: {num_workers} workers, {batch_size} images per browser session")

    def load_all_proxies(self):
        """Загрузить все прокси"""
        proxies = []
        try:
            with open("proxies.txt", "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        proxies.append(line)
            print(f"Loaded {len(proxies)} proxies (all workers will cycle through all proxies)")
            return proxies
        except Exception as e:
            print(f"Error loading proxies: {e}")
            return []

    def get_all_images_to_process(self):
        """Получить все изображения для обработки"""
        all_images = []

        if not self.images_folder.exists():
            return []

        brand_folders = [f for f in self.images_folder.iterdir() if f.is_dir()]

        for brand_folder in brand_folders:
            brand_output = self.output_folder / brand_folder.name
            brand_output.mkdir(parents=True, exist_ok=True)

            supported_formats = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            image_files = [f for f in brand_folder.iterdir() if f.is_file() and f.suffix.lower() in supported_formats]

            for image_file in image_files:
                output_file = brand_output / image_file.name
                if not output_file.exists():
                    all_images.append((str(image_file), str(brand_output)))

        return all_images

    def process_all_images(self):
        """Обработка с батчами и циклическими прокси"""
        print("Starting improved multiprocess processing...")

        # Проверки
        if not self.images_folder.exists():
            print(f"Images folder not found: {self.images_folder}")
            return

        if not Path("main_proxies.py").exists():
            print("main_proxies.py not found!")
            return

        self.output_folder.mkdir(exist_ok=True)

        # Загружаем данные
        all_proxies = self.load_all_proxies()
        if not all_proxies:
            print("No proxies found!")
            return

        if len(all_proxies) < self.num_workers:
            print(f"Warning: Only {len(all_proxies)} proxies for {self.num_workers} workers")

        all_images = self.get_all_images_to_process()
        if not all_images:
            print("No images to process")
            return

        print(f"Found {len(all_images)} images to process")
        print(f"Each worker will cycle through all {len(all_proxies)} proxies")
        print(f"Each browser session will process {self.batch_size} images")

        # Создаем shared объекты
        manager = Manager()
        task_queue = manager.Queue()
        stats = manager.dict({"processed": 0, "failed": 0})

        # Заполняем очередь задач
        for image_data in all_images:
            task_queue.put(image_data)

        print(f"Added {len(all_images)} tasks to queue")

        # Запускаем процессы воркеров
        start_time = time.time()
        processes = []

        for i in range(self.num_workers):
            p = Process(target=worker_process, args=(i, task_queue, stats, all_proxies, self.batch_size))
            p.start()
            processes.append(p)
            print(f"Started worker process {i}")
            time.sleep(3)  # Пауза между запуском процессов

        # Мониторинг прогресса
        def print_stats():
            elapsed = time.time() - start_time
            rate = stats["processed"] / (elapsed / 3600) if elapsed > 0 else 0
            remaining = task_queue.qsize()
            print(
                f"Progress: {stats['processed']} done, {stats['failed']} failed, "
                f"{remaining} remaining, {rate:.1f} img/h"
            )

        try:
            print("Monitoring progress...")

            while True:
                if task_queue.empty() and all(not p.is_alive() for p in processes):
                    break

                print_stats()
                time.sleep(120)  # Статистика каждые 2 минуты

            print("All tasks completed, stopping workers...")

            # Отправляем сигналы остановки
            for _ in range(self.num_workers):
                try:
                    task_queue.put(None, timeout=5)
                except:
                    pass

            # Ждем завершения процессов
            for i, p in enumerate(processes):
                p.join(timeout=60)
                if p.is_alive():
                    print(f"Force terminating worker {i}")
                    p.terminate()
                    p.join()

        except KeyboardInterrupt:
            print("\nInterrupted by user, terminating workers...")
            for p in processes:
                p.terminate()
                p.join()

        finally:
            # Финальная статистика
            elapsed = time.time() - start_time
            rate = stats["processed"] / (elapsed / 3600) if elapsed > 0 else 0

            print(f"\n{'='*60}")
            print(f"FINAL RESULTS:")
            print(f"Total processed: {stats['processed']}")
            print(f"Total failed: {stats['failed']}")
            print(f"Total time: {elapsed/3600:.2f} hours")
            print(f"Average rate: {rate:.1f} images/hour")
            print(f"Tasks remaining: {task_queue.qsize()}")
            print(f"{'='*60}")


def main():
    """Главная функция"""
    print("Improved Multiprocess Manager - Batches + Cyclic Proxies")
    print("=" * 60)

    NUM_WORKERS = 5
    BATCH_SIZE = 5  # 5 картинок на один браузер

    manager = ImprovedMultiprocessManager(num_workers=NUM_WORKERS, batch_size=BATCH_SIZE)
    manager.process_all_images()


if __name__ == "__main__":
    import sys

    try:
        num_workers = 5
        batch_size = 5

        if len(sys.argv) > 1:
            if sys.argv[1].isdigit():
                num_workers = int(sys.argv[1])
                print(f"Using {num_workers} workers")
            elif sys.argv[1] == "help":
                print("Improved Multiprocess Manager Commands:")
                print("  python improved_dynamic.py           - Run with 5 workers, 5 images per browser")
                print("  python improved_dynamic.py 10        - Run with 10 workers")
                print("  python improved_dynamic.py help      - Show this help")
                exit(0)

        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            batch_size = int(sys.argv[2])
            print(f"Using batch size: {batch_size}")

        # Проверки
        if not Path("images2").exists():
            print("Images folder 'images2' not found!")
            exit(1)

        if not Path("proxies.txt").exists():
            print("Proxies file 'proxies.txt' not found!")
            exit(1)

        if not Path("main_proxies.py").exists():
            print("Base file 'main_proxies.py' not found!")
            print("Please rename main_proxies6.py to main_proxies.py")
            exit(1)

        # Запуск
        manager = ImprovedMultiprocessManager(num_workers=num_workers, batch_size=batch_size)
        manager.process_all_images()

    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback

        traceback.print_exc()
