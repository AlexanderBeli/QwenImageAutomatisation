# Улучшенная версия: 5 картинок на браузер + циклические прокси + исправление race condition
import json
import os
import pickle
import signal
import subprocess
import tempfile
import time
import uuid
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

    # Создаем уникальный идентификатор для воркера
    worker_uuid = str(uuid.uuid4())[:8]
    temp_script = f"batch_worker_{worker_id}_{worker_uuid}.py"

    try:
        # Читаем оригинальный код
        with open("main_proxies.py", "r", encoding="utf-8") as f:
            original_code = f.read()

        # Модификация для работы с батчами и циклическими прокси
        modified_code = f"""
import sys
import json
import uuid
import asyncio
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

async def process_batch_of_images(batch_tasks, batch_id):
    \"\"\"Обработать батч изображений в одном браузере\"\"\"
    if not batch_tasks:
        return []
    
    print(f"Worker {worker_id}: Processing batch {{batch_id}} with {{len(batch_tasks)}} images")
    
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
    for i, task_data in enumerate(batch_tasks, 1):
        # Распаковываем данные задачи
        image_path_str = task_data['image_path']
        output_path_str = task_data['output_path']
        
        image_path = Path(image_path_str)
        output_path = Path(output_path_str)
        
        print(f"Worker {worker_id}: Batch {{batch_id}} - [{{i}}/{{len(batch_tasks)}}] {{image_path.name}} -> {{output_path.name}}")
        
        try:
            # КРИТИЧНО: Используем точный путь вывода
            success = await remover.process_single_image(image_path, output_path.parent)
            
            # Проверяем, что файл действительно создан с правильным именем
            if success and output_path.exists():
                actual_size = output_path.stat().st_size
                print(f"Worker {worker_id}: ✅ {{image_path.name}} -> {{output_path.name}} ({{actual_size}} bytes)")
                results.append({{
                    'image_path': image_path_str,
                    'output_path': output_path_str,
                    'success': True,
                    'file_size': actual_size
                }})
            else:
                print(f"Worker {worker_id}: ❌ {{image_path.name}} - file not saved correctly")
                results.append({{
                    'image_path': image_path_str,
                    'output_path': output_path_str,
                    'success': False,
                    'file_size': 0
                }})
            
            # Очистка контекста браузера между изображениями
            if i < len(batch_tasks):
                # Закрываем все вкладки кроме первой
                try:
                    pages = remover.context.pages
                    for page in pages[1:]:
                        await page.close()
                except:
                    pass
                
                import random
                await asyncio.sleep(random.uniform(3, 8))
                
        except Exception as e:
            print(f"Worker {worker_id}: Error processing {{image_path.name}}: {{e}}")
            import traceback
            traceback.print_exc()
            results.append({{
                'image_path': image_path_str,
                'output_path': output_path_str,
                'success': False,
                'file_size': 0,
                'error': str(e)
            }})
    
    # Закрываем браузер ОДИН РАЗ после всего батча
    await remover.cleanup_browser()
    
    return results

async def main_batch_worker():
    if len(sys.argv) < 3:
        print("Usage: script.py <batch_json> <batch_id>")
        return []
    
    # Загружаем батч задач из JSON
    batch_json = sys.argv[1]
    batch_id = sys.argv[2]
    
    with open(batch_json, 'r') as f:
        batch_tasks = json.load(f)
    
    return await process_batch_of_images(batch_tasks, batch_id)

if __name__ == "__main__":
    try:
        results = asyncio.run(main_batch_worker())
        # Сохраняем результаты с уникальным именем
        results_file = f"results_worker_{worker_id}_{{sys.argv[2]}}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Worker {worker_id}: Results saved to {{results_file}}")
        sys.exit(0)
    except Exception as e:
        print(f"Worker {worker_id}: Fatal error: {{e}}")
        import traceback
        traceback.print_exc()
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

                # Создаем уникальный ID для батча
                batch_id = f"{worker_id}_{uuid.uuid4().hex[:8]}_{int(time.time())}"
                batch_file = f"batch_{batch_id}.json"

                with open(batch_file, "w") as f:
                    json.dump(batch_tasks, f, indent=2)

                # Запускаем обработку батча как subprocess
                start_time = time.time()
                result = subprocess.run(
                    ["python", temp_script, batch_file, batch_id], capture_output=True, text=True, timeout=1800
                )  # 30 минут на батч

                elapsed = time.time() - start_time

                # Обрабатываем результаты
                results_file = f"results_worker_{worker_id}_{batch_id}.json"
                batch_success_count = 0
                batch_failed_count = 0
                failed_tasks = []

                if result.returncode == 0 and Path(results_file).exists():
                    try:
                        with open(results_file, "r") as f:
                            results = json.load(f)

                        for result_item in results:
                            image_path = result_item["image_path"]
                            output_path = result_item["output_path"]
                            success = result_item["success"]

                            if success:
                                # Дополнительная верификация
                                if Path(output_path).exists():
                                    file_size = result_item.get("file_size", 0)
                                    actual_size = Path(output_path).stat().st_size

                                    if actual_size > 0:
                                        batch_success_count += 1
                                        stats["processed"] += 1
                                        print(
                                            f"Worker {worker_id}: ✓ Verified {Path(image_path).name} ({actual_size} bytes)"
                                        )
                                    else:
                                        print(f"Worker {worker_id}: ⚠ File empty: {output_path}")
                                        batch_failed_count += 1
                                        stats["failed"] += 1
                                        # Находим оригинальную задачу
                                        for task in batch_tasks:
                                            if task["image_path"] == image_path:
                                                failed_tasks.append(task)
                                                break
                                else:
                                    print(f"Worker {worker_id}: ⚠ File not found: {output_path}")
                                    batch_failed_count += 1
                                    stats["failed"] += 1
                                    # Находим оригинальную задачу
                                    for task in batch_tasks:
                                        if task["image_path"] == image_path:
                                            failed_tasks.append(task)
                                            break
                            else:
                                batch_failed_count += 1
                                stats["failed"] += 1
                                # Находим оригинальную задачу
                                for task in batch_tasks:
                                    if task["image_path"] == image_path:
                                        failed_tasks.append(task)
                                        break

                        # Удаляем файл результатов
                        os.remove(results_file)

                    except Exception as e:
                        print(f"Worker {worker_id}: Error reading results: {e}")
                        import traceback

                        traceback.print_exc()
                        batch_failed_count = len(batch_tasks)
                        stats["failed"] += batch_failed_count
                        failed_tasks = batch_tasks
                else:
                    print(f"Worker {worker_id}: Batch failed - returncode: {result.returncode}")
                    if result.stderr:
                        print(f"Worker {worker_id}: STDERR: {result.stderr[:500]}")
                    batch_failed_count = len(batch_tasks)
                    stats["failed"] += batch_failed_count
                    failed_tasks = batch_tasks

                # Возвращаем неудачные задачи в очередь (с ограничением попыток)
                for task in failed_tasks:
                    retry_count = task.get("retry_count", 0)
                    if retry_count < 3:  # Максимум 3 попытки
                        task["retry_count"] = retry_count + 1
                        task_queue.put(task)
                        print(
                            f"Worker {worker_id}: Requeued {Path(task['image_path']).name} (attempt {retry_count + 1}/3)"
                        )
                    else:
                        print(f"Worker {worker_id}: Giving up on {Path(task['image_path']).name} after 3 attempts")

                processed_count += batch_success_count

                print(
                    f"Worker {worker_id}: Batch {batch_id} completed - "
                    f"✅{batch_success_count} ❌{batch_failed_count} ({elapsed:.1f}s)"
                )

                # Очищаем временные файлы
                try:
                    os.remove(batch_file)
                except:
                    pass

            except subprocess.TimeoutExpired:
                print(f"Worker {worker_id}: Batch timeout after 30 minutes")
                stats["failed"] += len(batch_tasks)
                # Возвращаем задачи в очередь
                for task in batch_tasks:
                    retry_count = task.get("retry_count", 0)
                    if retry_count < 3:
                        task["retry_count"] = retry_count + 1
                        task_queue.put(task)
            except Exception as e:
                print(f"Worker {worker_id}: Unexpected error: {e}")
                import traceback

                traceback.print_exc()
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
        """Получить все изображения для обработки с полными путями вывода"""
        all_tasks = []

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

                # Пропускаем уже обработанные файлы
                if not output_file.exists():
                    # КРИТИЧНО: Сохраняем полный путь к выходному файлу
                    task = {"image_path": str(image_file), "output_path": str(output_file), "retry_count": 0}
                    all_tasks.append(task)

        return all_tasks

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

        all_tasks = self.get_all_images_to_process()
        if not all_tasks:
            print("No images to process")
            return

        print(f"Found {len(all_tasks)} images to process")
        print(f"Each worker will cycle through all {len(all_proxies)} proxies")
        print(f"Each browser session will process {self.batch_size} images")

        # Создаем shared объекты
        manager = Manager()
        task_queue = manager.Queue()
        stats = manager.dict({"processed": 0, "failed": 0})

        # Заполняем очередь задач
        for task in all_tasks:
            task_queue.put(task)

        print(f"Added {len(all_tasks)} tasks to queue")

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
            total = len(all_tasks)
            completed = stats["processed"] + stats["failed"]
            percent = (completed / total * 100) if total > 0 else 0

            print(f"\n{'='*70}")
            print(f"Progress: {completed}/{total} ({percent:.1f}%)")
            print(f"  ✅ Processed: {stats['processed']}")
            print(f"  ❌ Failed: {stats['failed']}")
            print(f"  ⏳ Remaining in queue: {remaining}")
            print(f"  ⚡ Rate: {rate:.1f} images/hour")
            print(f"  ⏱ Elapsed: {elapsed/3600:.2f} hours")
            if rate > 0:
                eta = remaining / rate
                print(f"  🕐 ETA: {eta:.1f} hours")
            print(f"{'='*70}\n")

        try:
            print("Monitoring progress...")
            last_stats_time = time.time()

            while True:
                # Проверяем состояние
                if task_queue.empty() and all(not p.is_alive() for p in processes):
                    print("All tasks completed!")
                    break

                # Печатаем статистику каждые 2 минуты
                if time.time() - last_stats_time >= 120:
                    print_stats()
                    last_stats_time = time.time()

                time.sleep(30)  # Проверяем каждые 30 секунд

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
            print("\n\nInterrupted by user, terminating workers...")
            for p in processes:
                p.terminate()
                p.join()

        finally:
            # Финальная статистика
            elapsed = time.time() - start_time
            rate = stats["processed"] / (elapsed / 3600) if elapsed > 0 else 0
            total = len(all_tasks)
            success_rate = (stats["processed"] / total * 100) if total > 0 else 0

            print(f"\n{'='*70}")
            print(f"FINAL RESULTS:")
            print(f"{'='*70}")
            print(f"Total images: {total}")
            print(f"✅ Successfully processed: {stats['processed']} ({success_rate:.1f}%)")
            print(f"❌ Failed: {stats['failed']}")
            print(f"⏱ Total time: {elapsed/3600:.2f} hours")
            print(f"⚡ Average rate: {rate:.1f} images/hour")
            print(f"⏳ Tasks remaining in queue: {task_queue.qsize()}")
            print(f"{'='*70}\n")

            # Очищаем временные файлы
            print("Cleaning up temporary files...")
            temp_files = (
                list(Path(".").glob("batch_*.json"))
                + list(Path(".").glob("results_worker_*.json"))
                + list(Path(".").glob("batch_worker_*.py"))
            )
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                    print(f"Removed: {temp_file}")
                except:
                    pass


def main():
    """Главная функция"""
    print("=" * 70)
    print("Improved Multiprocess Manager - Batches + Cyclic Proxies + Race Fix")
    print("=" * 70)

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
                print("=" * 70)
                print("Improved Multiprocess Manager Commands:")
                print("=" * 70)
                print("  python improved_dynamic.py              - Run with 5 workers, 5 images/browser")
                print("  python improved_dynamic.py 10           - Run with 10 workers")
                print("  python improved_dynamic.py 10 3         - Run with 10 workers, 3 images/browser")
                print("  python improved_dynamic.py help         - Show this help")
                print("=" * 70)
                exit(0)

        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            batch_size = int(sys.argv[2])
            print(f"Using batch size: {batch_size}")

        # Проверки
        if not Path("images2").exists():
            print("❌ Images folder 'images2' not found!")
            exit(1)

        if not Path("proxies.txt").exists():
            print("❌ Proxies file 'proxies.txt' not found!")
            exit(1)

        if not Path("main_proxies.py").exists():
            print("❌ Base file 'main_proxies.py' not found!")
            print("Please make sure main_proxies.py exists in the same directory")
            exit(1)

        # Запуск
        print(f"\n🚀 Starting with {num_workers} workers, {batch_size} images per batch\n")
        manager = ImprovedMultiprocessManager(num_workers=num_workers, batch_size=batch_size)
        manager.process_all_images()

    except KeyboardInterrupt:
        print("\n\n⚠ Stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback

        traceback.print_exc()
