# Qwen Website Image Automation

## Structure

- **main.py** - full circle with playwright: любой сложности, 50 - 60 изображений в день с одного аккаунта
- **selenium_cookies.py** - get Chrome cookies by selenium
- **main_proxies.py** + **dynamic_multiprocess.py** - создает 8 - 12 воркеров, в каждом запускается proxy + Chrome + cookies = 5 картинок без регистрации, затем браузер закрывается и начинается вновь. Результат 185 - 390 картинок / час

```bash
python dynamic_multiprocess.py 12 #number of workers
```

- **compare_images_folder.py** - compare images and no_watermarks folders, moving to sorted_images folder
