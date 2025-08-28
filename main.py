import json
import os
import platform
import shutil
import tempfile
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class WatermarkRemover:
    def __init__(self, qwen_chat_url, download_folder=None, user_data_dir=None):
        """
        Initialize the watermark removal automation

        Args:
            qwen_chat_url (str): URL to Qwen AI chat
            download_folder (str): Default download folder path
            user_data_dir (str): Path to Chrome user data directory for persistent session
        """
        self.qwen_url = qwen_chat_url
        self.download_folder = download_folder or os.path.join(os.path.expanduser("~"), "Downloads")
        self.user_data_dir = user_data_dir
        self.driver = None
        self.wait_timeout = 30
        self.cookies_file = "qwen_cookies.json"

    def setup_browser(self, use_existing_session=True):
        """Setup Chrome browser with appropriate options"""
        chrome_options = Options()

        # Download preferences
        prefs = {
            "download.default_directory": self.download_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        if use_existing_session:
            # For macOS, use the default Chrome user data directory
            system = platform.system()
            if system == "Darwin":  # macOS
                default_user_data = os.path.join(
                    os.path.expanduser("~"), "Library", "Application Support", "Google", "Chrome"
                )

                # Create a copy of the user data for automation to avoid conflicts
                import tempfile

                automation_profile = tempfile.mkdtemp(prefix="chrome_automation_")

                try:
                    # Copy the existing Chrome profile
                    import subprocess

                    print("📋 Copying Chrome profile for automation...")

                    # Copy only essential directories to avoid conflicts
                    essential_dirs = ["Default"]  # Main profile directory
                    for dir_name in essential_dirs:
                        src_dir = os.path.join(default_user_data, dir_name)
                        dst_dir = os.path.join(automation_profile, dir_name)

                        if os.path.exists(src_dir):
                            print(f"Copying {dir_name}...")
                            shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns("*Lock*", "Singleton*"))

                    chrome_options.add_argument(f"--user-data-dir={automation_profile}")
                    chrome_options.add_argument("--profile-directory=Default")
                    print(f"✓ Using automation profile: {automation_profile}")

                except Exception as e:
                    print(f"⚠ Could not copy profile: {e}")
                    print("Creating fresh profile with saved cookies...")
                    chrome_options.add_argument(f"--user-data-dir={automation_profile}")
        else:
            # Create a fresh temporary profile
            automation_profile = tempfile.mkdtemp(prefix="chrome_fresh_")
            chrome_options.add_argument(f"--user-data-dir={automation_profile}")

        # Additional options for stability and to avoid detection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--remote-debugging-port=9222")  # Enable remote debugging
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Try to initialize driver with error handling
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                print("✓ Chrome browser initialized successfully")
                return self.driver

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    print("❌ All attempts failed. Please make sure:")
                    print("1. Chrome is completely closed")
                    print("2. ChromeDriver is installed and in PATH")
                    print("3. No other automation tools are using Chrome")
                    raise e
                time.sleep(2)

        return None

    def save_cookies(self):
        """Save current session cookies to file"""
        try:
            import json

            cookies = self.driver.get_cookies()
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f)
            print("✓ Cookies saved")
        except Exception as e:
            print(f"✗ Error saving cookies: {e}")

    def load_cookies(self):
        """Load saved session cookies"""
        try:
            import json

            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, "r") as f:
                    cookies = json.load(f)

                # Navigate to domain first
                self.driver.get("https://chat.qwen.ai")
                time.sleep(2)

                # Add each cookie
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"Warning: Could not add cookie {cookie.get('name', 'unknown')}: {e}")

                print("✓ Cookies loaded")
                return True
        except Exception as e:
            print(f"✗ Error loading cookies: {e}")
        return False

    def check_authentication(self):
        """Check if user is authenticated and can access the chat"""
        try:
            # Navigate to the specific chat URL
            self.driver.get(self.qwen_url)
            time.sleep(3)

            # Check if redirected to login page or main page
            current_url = self.driver.current_url

            # Common indicators of being logged out
            logout_indicators = [
                "login" in current_url.lower(),
                "signin" in current_url.lower(),
                "auth" in current_url.lower(),
                current_url == "https://chat.qwen.ai/" or current_url == "https://chat.qwen.ai",
                self.qwen_url not in current_url,
            ]

            if any(logout_indicators):
                print("❌ Not authenticated - redirected from chat URL")
        except Exception as e:
            print(f"✗ Error checking authentication: {e}")

    def wait_for_element(self, by, value, timeout=None):
        """Wait for element to be present and return it"""
        timeout = timeout or self.wait_timeout
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def handle_authentication(self):
        """Handle authentication process"""
        print("🔐 Handling authentication...")

        # Method 1: Try loading saved cookies
        if self.load_cookies():
            if self.check_authentication():
                return True

        # Method 2: Check if already logged in via Chrome profile
        if self.check_authentication():
            self.save_cookies()  # Save for next time
            return True

        # Method 3: Manual login prompt
        print("\n" + "=" * 50)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 50)
        print("Please complete the following steps:")
        print("1. The browser will open to Qwen AI")
        print("2. Log in manually if needed")
        print("3. Navigate to your specific chat URL")
        print("4. Press ENTER here when ready to continue...")

        # Navigate to login page
        self.driver.get("https://chat.qwen.ai")

        # Wait for manual login
        input("Press ENTER when you have logged in and are ready to continue...")

        # Navigate to specific chat
        self.driver.get(self.qwen_url)
        time.sleep(3)

        # Verify authentication
        if self.check_authentication():
            self.save_cookies()  # Save for future use
            print("✅ Authentication successful!")
            return True
        else:
            print("❌ Authentication failed!")
            return False

            # Look for chat interface elements
            chat_indicators = [
                'textarea[placeholder*="message" i]',
                'input[placeholder*="message" i]',
                ".chat-input",
                ".message-input",
                '[data-testid="chat-input"]',
            ]

            for selector in chat_indicators:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        print("✓ Authenticated and chat interface found")
                        return True
                except NoSuchElementException:
                    continue

            print("⚠ Authentication unclear - no chat input found")
            return False

        # except Exception as e:
        #     print(f"✗ Error checking authentication: {e}")
        #     return False

    def handle_authentication(self):
        """Handle authentication process"""
        print("🔐 Handling authentication...")

        # Method 1: Try loading saved cookies
        if self.load_cookies():
            if self.check_authentication():
                return True

        # Method 2: Check if already logged in via Chrome profile
        if self.check_authentication():
            self.save_cookies()  # Save for next time
            return True

        # Method 3: Manual login prompt
        print("\n" + "=" * 50)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 50)
        print("Please complete the following steps:")
        print("1. The browser will open to Qwen AI")
        print("2. Log in manually if needed")
        print("3. Navigate to your specific chat URL")
        print("4. Press ENTER here when ready to continue...")

        # Navigate to login page
        self.driver.get("https://chat.qwen.ai")

        # Wait for manual login
        input("Press ENTER when you have logged in and are ready to continue...")

        # Navigate to specific chat
        self.driver.get(self.qwen_url)
        time.sleep(3)

        # Verify authentication
        if self.check_authentication():
            self.save_cookies()  # Save for future use
            print("✅ Authentication successful!")
            return True
        else:
            print("❌ Authentication failed!")
            return False
        """Wait for element to be present and return it"""
        timeout = timeout or self.wait_timeout
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))

    def wait_for_clickable(self, by, value, timeout=None):
        """Wait for element to be clickable and return it"""
        timeout = timeout or self.wait_timeout
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable((by, value)))

    def upload_image_to_qwen(self, image_path):
        """
        Upload image to Qwen AI chat interface
        Note: Selectors may need adjustment based on actual website structure
        """
        try:
            # Navigate to Qwen chat if not already there
            if self.qwen_url not in self.driver.current_url:
                self.driver.get(self.qwen_url)
                time.sleep(3)

            # Look for file upload button/input (common selectors - adjust as needed)
            upload_selectors = [
                'input[type="file"]',
                '[data-testid="file-upload"]',
                ".upload-button input",
                "#file-upload",
                ".file-input",
            ]

            upload_element = None
            for selector in upload_selectors:
                try:
                    upload_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if upload_element:
                        break
                except NoSuchElementException:
                    continue

            if not upload_element:
                # Try to find upload button and click it first
                upload_buttons = [
                    '[title*="upload" i]',
                    '[aria-label*="upload" i]',
                    'button[class*="upload" i]',
                    ".upload-btn",
                ]

                for selector in upload_buttons:
                    try:
                        button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        button.click()
                        time.sleep(1)
                        upload_element = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                        break
                    except NoSuchElementException:
                        continue

            if upload_element:
                upload_element.send_keys(str(image_path))
                print(f"✓ Uploaded: {image_path}")
                return True
            else:
                print(f"✗ Could not find upload element for: {image_path}")
                return False

        except Exception as e:
            print(f"✗ Error uploading {image_path}: {str(e)}")
            return False

    def send_prompt(self, prompt="Delete watermark"):
        """Send the watermark removal prompt"""
        try:
            # Common selectors for chat input (adjust as needed)
            input_selectors = [
                'textarea[placeholder*="message" i]',
                'input[placeholder*="message" i]',
                ".chat-input textarea",
                ".message-input",
                "#chat-input",
            ]

            input_element = None
            for selector in input_selectors:
                try:
                    input_element = self.wait_for_element(By.CSS_SELECTOR, selector, 5)
                    break
                except TimeoutException:
                    continue

            if input_element:
                input_element.clear()
                input_element.send_keys(prompt)

                # Find and click send button
                send_selectors = [
                    'button[type="submit"]',
                    ".send-button",
                    '[aria-label*="send" i]',
                    'button[class*="send" i]',
                ]

                for selector in send_selectors:
                    try:
                        send_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        send_btn.click()
                        print(f"✓ Sent prompt: {prompt}")
                        return True
                    except NoSuchElementException:
                        continue

                # If no send button found, try Enter key
                from selenium.webdriver.common.keys import Keys

                input_element.send_keys(Keys.RETURN)
                print(f"✓ Sent prompt with Enter: {prompt}")
                return True

            print("✗ Could not find chat input element")
            return False

        except Exception as e:
            print(f"✗ Error sending prompt: {str(e)}")
            return False

    def wait_for_generation(self, max_wait_time=120):
        """Wait for image generation to complete"""
        print("⏳ Waiting for generation...")

        # Look for indicators that generation is complete
        completion_indicators = [
            'img[src*="generated"]',
            ".generated-image",
            '[data-testid="generated-image"]',
            ".result-image",
            'img[alt*="result" i]',
        ]

        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            # Check for loading indicators first (should disappear when done)
            loading_indicators = [".loading", ".generating", '[class*="spinner"]', ".progress"]

            is_loading = False
            for indicator in loading_indicators:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                    if element.is_displayed():
                        is_loading = True
                        break
                except NoSuchElementException:
                    pass

            # Check for completion
            for indicator in completion_indicators:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                    if element.is_displayed():
                        print("✓ Generation completed")
                        return True
                except NoSuchElementException:
                    pass

            time.sleep(2)

        print("⚠ Generation timeout - proceeding anyway")
        return False

    def download_generated_image(self, original_filename):
        """Download the generated image"""
        try:
            # Look for download button or generated image
            download_selectors = [
                "a[download]",
                'button[title*="download" i]',
                ".download-btn",
                '[data-testid="download"]',
            ]

            # First try to find explicit download button
            for selector in download_selectors:
                try:
                    download_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    download_btn.click()
                    print("✓ Download initiated via button")

                    # Wait for file to appear in download folder
                    return self.wait_for_download(original_filename)
                except NoSuchElementException:
                    continue

            # If no download button, try right-click on generated image
            image_selectors = ['img[src*="generated"]', ".generated-image img", ".result-image"]

            for selector in image_selectors:
                try:
                    img_element = self.driver.find_element(By.CSS_SELECTOR, selector)

                    # Right-click and save
                    from selenium.webdriver.common.action_chains import ActionChains

                    actions = ActionChains(self.driver)
                    actions.context_click(img_element).perform()

                    # This is tricky - browser context menu automation
                    # Alternative: get image src and download via requests
                    img_src = img_element.get_attribute("src")
                    if img_src and img_src.startswith("http"):
                        return self.download_image_via_requests(img_src, original_filename)

                except NoSuchElementException:
                    continue

            print("✗ Could not find generated image to download")
            return None

        except Exception as e:
            print(f"✗ Error downloading image: {str(e)}")
            return None

    def download_image_via_requests(self, img_url, original_filename):
        """Download image using requests library"""
        try:
            # Get cookies from selenium session for authenticated requests
            selenium_cookies = self.driver.get_cookies()
            cookies = {cookie["name"]: cookie["value"] for cookie in selenium_cookies}

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            response = requests.get(img_url, cookies=cookies, headers=headers, stream=True)
            response.raise_for_status()

            # Save to temporary location first
            temp_path = os.path.join(self.download_folder, f"temp_{original_filename}")
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"✓ Downloaded via requests: {temp_path}")
            return temp_path

        except Exception as e:
            print(f"✗ Error downloading via requests: {str(e)}")
            return None

    def wait_for_download(self, original_filename, timeout=30):
        """Wait for file to appear in download folder"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Look for recently downloaded files
            for file in os.listdir(self.download_folder):
                file_path = os.path.join(self.download_folder, file)
                if (
                    os.path.isfile(file_path)
                    and file.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                    and os.path.getmtime(file_path) > start_time
                ):
                    print(f"✓ Found downloaded file: {file}")
                    return file_path
            time.sleep(1)

        print("✗ Download timeout")
        return None

    def process_images(self, images_folder="images", output_folder="no_watermarks"):
        """Main processing function"""
        images_path = Path(images_folder)
        output_path = Path(output_folder)

        if not images_path.exists():
            print(f"✗ Images folder '{images_folder}' not found")
            return

        # Create output folder
        output_path.mkdir(exist_ok=True)

        # Setup browser with existing session
        driver = self.setup_browser(use_existing_session=True)
        if not driver:
            print("✗ Failed to setup browser")
            return

        # Handle authentication
        if not self.handle_authentication():
            print("✗ Authentication failed - cannot proceed")
            self.driver.quit()
            return

        try:
            # Process each brand folder
            for brand_folder in images_path.iterdir():
                if not brand_folder.is_dir():
                    continue

                print(f"\n📁 Processing brand: {brand_folder.name}")

                # Create brand folder in output
                brand_output = output_path / brand_folder.name
                brand_output.mkdir(exist_ok=True)

                # Process each image in brand folder
                for image_file in brand_folder.iterdir():
                    if image_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                        print(f"\n🖼️  Processing: {image_file.name}")

                        # Check if already processed
                        output_file = brand_output / image_file.name
                        if output_file.exists():
                            print(f"⏭️  Skipping (already exists): {image_file.name}")
                            continue

                        success = self.process_single_image(image_file, brand_output, image_file.name)

                        if success:
                            print(f"✅ Successfully processed: {image_file.name}")
                        else:
                            print(f"❌ Failed to process: {image_file.name}")

                        # Brief pause between images
                        time.sleep(2)

        finally:
            self.driver.quit()

    def process_single_image(self, image_path, output_folder, filename):
        """Process a single image through the watermark removal pipeline"""
        try:
            # Step 1: Upload image
            if not self.upload_image_to_qwen(image_path):
                return False

            # Step 2: Send prompt
            time.sleep(2)
            if not self.send_prompt("Delete watermark"):
                return False

            # Step 3: Wait for generation
            time.sleep(5)
            self.wait_for_generation()

            # Step 4: Download result
            downloaded_file = self.download_generated_image(filename)
            if not downloaded_file:
                return False

            # Step 5: Move to final location
            final_path = output_folder / filename
            shutil.move(downloaded_file, final_path)

            print(f"✓ Saved to: {final_path}")
            return True

        except Exception as e:
            print(f"✗ Error processing {filename}: {str(e)}")
            return False


# Usage example
def main():
    # Configuration
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"
    IMAGES_FOLDER = "images"
    OUTPUT_FOLDER = "no_watermarks"

    # Optional: Specify custom Chrome user data directory
    # USER_DATA_DIR = "/path/to/your/chrome/profile"
    USER_DATA_DIR = None  # Use default Chrome profile

    # Initialize and run
    remover = WatermarkRemover(QWEN_CHAT_URL, user_data_dir=USER_DATA_DIR)
    remover.process_images(IMAGES_FOLDER, OUTPUT_FOLDER)


def setup_authentication_only():
    """Helper function to just set up authentication without processing images"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    remover = WatermarkRemover(QWEN_CHAT_URL)
    remover.setup_browser(use_existing_session=True)

    if remover.handle_authentication():
        print("✅ Authentication setup complete!")
        print("You can now run the main script.")
    else:
        print("❌ Authentication setup failed.")

    remover.driver.quit()


if __name__ == "__main__":
    # Uncomment the next line to just set up authentication first
    # setup_authentication_only()

    main()
