# Correct buttons
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
                automation_profile = tempfile.mkdtemp(prefix="chrome_automation_")

                try:
                    # Copy the existing Chrome profile
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
            cookies = self.driver.get_cookies()
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f)
            print("✓ Cookies saved")
        except Exception as e:
            print(f"✗ Error saving cookies: {e}")

    def load_cookies(self):
        """Load saved session cookies"""
        try:
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
            time.sleep(5)  # Increased wait time

            current_url = self.driver.current_url
            print(f"Current URL: {current_url}")

            # Check if we're in the correct chat
            if self.qwen_url in current_url or "chat.qwen.ai/c/" in current_url:
                # Look for chat interface elements
                chat_indicators = [
                    "textarea",
                    "input[type='text']",
                    ".chat-input",
                    "[placeholder*='message']",
                    "[placeholder*='Message']",
                    "div[contenteditable='true']",
                ]

                for indicator in chat_indicators:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                        if element.is_displayed():
                            print("✓ Chat interface detected - authenticated")
                            return True
                    except NoSuchElementException:
                        continue

                print("⚠ Chat URL correct but no input found")
                return True  # Assume authenticated if we're on the chat page
            else:
                print(f"❌ Not on chat page. Current: {current_url}")
                return False

        except Exception as e:
            print(f"✗ Error checking authentication: {e}")
            return False

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
        time.sleep(3)

        # Wait for manual login
        input("Press ENTER when you have logged in and are ready to continue...")

        # Navigate to specific chat
        self.driver.get(self.qwen_url)
        time.sleep(5)

        # Verify authentication
        if self.check_authentication():
            self.save_cookies()  # Save for future use
            print("✅ Authentication successful!")
            return True
        else:
            print("❌ Authentication failed!")
            return False

    def find_element_with_multiple_selectors(self, selectors, timeout=10):
        """Try multiple selectors to find an element"""
        wait = WebDriverWait(self.driver, timeout)

        for selector in selectors:
            try:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if element and element.is_displayed():
                    print(f"✓ Found element with selector: {selector}")
                    return element
            except TimeoutException:
                continue

        return None

    def upload_image_to_qwen(self, image_path):
        """Upload image to Qwen AI chat interface with Qwen-specific selectors"""
        try:
            print(f"🔄 Uploading image: {image_path}")

            # Navigate to chat if not already there
            if self.qwen_url not in self.driver.current_url:
                self.driver.get(self.qwen_url)
                time.sleep(3)

            # Qwen-specific selectors based on the actual HTML structure
            file_input_selector = 'input[type="file"]#filesUpload'
            upload_button_selector = "button.chat-prompt-upload-group-btn"

            # Try to find the direct file input first
            try:
                upload_element = self.driver.find_element(By.CSS_SELECTOR, file_input_selector)
                print("✓ Found direct file input")
            except:
                upload_element = None

            if not upload_element:
                # Try to click the upload button to activate file input
                try:
                    upload_button = self.driver.find_element(By.CSS_SELECTOR, upload_button_selector)
                    print("📎 Clicking upload button...")
                    upload_button.click()
                    time.sleep(2)

                    # Try to find file input after clicking button
                    upload_element = self.driver.find_element(By.CSS_SELECTOR, file_input_selector)
                    print("✓ Found file input after clicking upload button")
                except:
                    print("✗ Could not find upload button or file input")
                    return False

            if upload_element:
                # Make sure the input is interactable
                self.driver.execute_script(
                    """
                    arguments[0].style.display = 'block';
                    arguments[0].style.visibility = 'visible';
                    arguments[0].style.opacity = '1';
                    arguments[0].style.position = 'static';
                """,
                    upload_element,
                )

                # Upload the file
                upload_element.send_keys(str(image_path))
                print(f"✓ Image uploaded successfully: {os.path.basename(image_path)}")
                time.sleep(5)  # Wait for upload to process and preview to appear
                return True
            else:
                print("✗ Could not find file upload element")
                return False

        except Exception as e:
            print(f"✗ Error uploading image: {str(e)}")
            return False

    def send_prompt(self, prompt="Delete watermark"):
        """Send the watermark removal prompt using Qwen-specific selectors"""
        try:
            print(f"💬 Sending prompt: {prompt}")

            # Qwen-specific textarea selector
            textarea_selector = "textarea#chat-input"
            send_button_selector = "button#send-message-button"

            # Find the textarea
            try:
                input_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, textarea_selector))
                )
                print("✓ Found chat input textarea")
            except TimeoutException:
                print("✗ Could not find chat input textarea")
                return False

            # Clear and enter text
            input_element.clear()
            input_element.send_keys(prompt)
            time.sleep(1)  # Brief pause to let text register

            # Try to find and click send button
            try:
                send_button = self.driver.find_element(By.CSS_SELECTOR, send_button_selector)

                # Check if button is enabled (not disabled)
                is_disabled = "disabled" in send_button.get_attribute("class")
                if is_disabled:
                    print("⚠ Send button is disabled, trying Enter key instead")
                    input_element.send_keys(Keys.RETURN)
                else:
                    send_button.click()
                    print("✓ Clicked send button")

            except NoSuchElementException:
                print("⚠ Send button not found, using Enter key")
                input_element.send_keys(Keys.RETURN)

            print("✓ Prompt sent successfully")
            time.sleep(3)  # Wait for processing to start
            return True

        except Exception as e:
            print(f"✗ Error sending prompt: {str(e)}")
            return False

    def wait_for_generation(self, max_wait_time=120):
        """Wait for image generation to complete with better detection"""
        print("⏳ Waiting for generation to complete...")

        start_time = time.time()
        last_check_time = start_time

        while time.time() - start_time < max_wait_time:
            current_time = time.time()

            # Print progress every 10 seconds
            if current_time - last_check_time > 10:
                elapsed = int(current_time - start_time)
                print(f"⏳ Still waiting... ({elapsed}s elapsed)")
                last_check_time = current_time

            # Check for loading indicators (should disappear when done)
            loading_selectors = [
                '[class*="loading" i]',
                '[class*="generating" i]',
                '[class*="spinner" i]',
                ".progress",
                '[data-testid*="loading"]',
                'svg[class*="spin"]',
                '[class*="animate-spin"]',
            ]

            is_loading = False
            for selector in loading_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            is_loading = True
                            break
                    if is_loading:
                        break
                except:
                    pass

            # Check for generated images (completion indicators)
            completion_selectors = [
                'img[src*="blob:"]',  # Generated images often have blob URLs
                'img[src*="data:"]',  # Base64 images
                'img[alt*="generated" i]',
                'img[alt*="result" i]',
                '[data-testid*="generated"]',
                ".generated-image img",
                ".result-image img",
                'img[class*="generated"]',
            ]

            generated_images = []
            for selector in completion_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.get_attribute("src"):
                            generated_images.append(element)
                except:
                    pass

            # If we have generated images and no loading indicators
            if generated_images and not is_loading:
                print(f"✓ Generation completed! Found {len(generated_images)} generated image(s)")
                return True

            time.sleep(3)

        print("⚠ Generation timeout reached - proceeding anyway")
        return False

    def download_generated_image(self, original_filename):
        """Download the generated image with multiple methods"""
        try:
            print("💾 Attempting to download generated image...")

            # Method 1: Look for download buttons
            download_selectors = [
                "a[download]",
                'button[title*="download" i]',
                'button[aria-label*="download" i]',
                ".download-btn",
                '[data-testid*="download"]',
                'button[class*="download" i]',
                'svg[class*="download"] parent::button',
            ]

            download_button = self.find_element_with_multiple_selectors(download_selectors, 5)
            if download_button:
                download_button.click()
                print("✓ Download initiated via download button")
                return self.wait_for_download(original_filename)

            # Method 2: Find generated images and download via right-click or direct URL
            image_selectors = [
                'img[src*="blob:"]',
                'img[src*="data:"]',
                'img[alt*="generated" i]',
                'img[alt*="result" i]',
                ".generated-image img",
                ".result-image img",
            ]

            generated_image = self.find_element_with_multiple_selectors(image_selectors, 5)
            if generated_image:
                img_src = generated_image.get_attribute("src")
                print(f"Found generated image with src: {img_src[:100]}...")

                if img_src:
                    # Method 2a: Try downloading via requests (for HTTP URLs)
                    if img_src.startswith("http"):
                        downloaded_file = self.download_image_via_requests(img_src, original_filename)
                        if downloaded_file:
                            return downloaded_file

                    # Method 2b: Try right-click save (less reliable)
                    try:
                        actions = ActionChains(self.driver)
                        actions.context_click(generated_image).perform()
                        time.sleep(1)

                        # Try to press 'S' for Save (this is very browser-dependent)
                        actions.send_keys("s").perform()
                        return self.wait_for_download(original_filename)

                    except Exception as e:
                        print(f"Right-click method failed: {e}")

            print("✗ Could not find or download generated image")
            return None

        except Exception as e:
            print(f"✗ Error in download process: {str(e)}")
            return None

    def download_image_via_requests(self, img_url, original_filename):
        """Download image using requests library"""
        try:
            print(f"🌐 Downloading via HTTP request...")

            # Get cookies from selenium session
            selenium_cookies = self.driver.get_cookies()
            cookies = {cookie["name"]: cookie["value"] for cookie in selenium_cookies}

            headers = {
                "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                "Referer": self.driver.current_url,
            }

            response = requests.get(img_url, cookies=cookies, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            # Generate temp filename
            timestamp = int(time.time())
            temp_filename = f"temp_{timestamp}_{original_filename}"
            temp_path = os.path.join(self.download_folder, temp_filename)

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"✓ Downloaded via requests: {temp_filename}")
            return temp_path

        except Exception as e:
            print(f"✗ Error downloading via requests: {str(e)}")
            return None

    def wait_for_download(self, original_filename, timeout=60):
        """Wait for file to appear in download folder"""
        print("⏳ Waiting for download to complete...")
        start_time = time.time()
        initial_files = set(os.listdir(self.download_folder))

        while time.time() - start_time < timeout:
            current_files = set(os.listdir(self.download_folder))
            new_files = current_files - initial_files

            for file in new_files:
                if file.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                    file_path = os.path.join(self.download_folder, file)
                    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
                        print(f"✓ Downloaded file detected: {file}")
                        return file_path

            time.sleep(2)

        print("✗ Download timeout - no new files detected")
        return None

    def process_images(self, images_folder="images", output_folder="no_watermarks"):
        """Main processing function with improved error handling"""
        images_path = Path(images_folder)
        output_path = Path(output_folder)

        if not images_path.exists():
            print(f"✗ Images folder '{images_folder}' not found")
            print(f"Please create the folder and add your images organized by brand subfolders")
            return

        # Create output folder
        output_path.mkdir(exist_ok=True)
        print(f"📁 Output folder created/verified: {output_path}")

        # Setup browser
        if not self.setup_browser(use_existing_session=True):
            print("✗ Failed to setup browser")
            return

        # Handle authentication
        if not self.handle_authentication():
            print("✗ Authentication failed - cannot proceed")
            self.driver.quit()
            return

        processed_count = 0
        error_count = 0

        try:
            # Process each brand folder
            for brand_folder in images_path.iterdir():
                if not brand_folder.is_dir():
                    continue

                print(f"\n{'='*50}")
                print(f"📁 Processing brand folder: {brand_folder.name}")
                print(f"{'='*50}")

                # Create brand folder in output
                brand_output = output_path / brand_folder.name
                brand_output.mkdir(exist_ok=True)
                print(f"📂 Created output folder: {brand_output}")

                # Get all image files
                image_files = [
                    f for f in brand_folder.iterdir() if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
                ]

                print(f"Found {len(image_files)} images to process")

                # Process each image
                for i, image_file in enumerate(image_files, 1):
                    print(f"\n[{i}/{len(image_files)}] 🖼️ Processing: {image_file.name}")

                    # Check if already processed
                    output_file = brand_output / image_file.name
                    if output_file.exists():
                        print(f"⏭️ Skipping (already exists): {image_file.name}")
                        continue

                    # Process the image
                    success = self.process_single_image(image_file, brand_output)

                    if success:
                        processed_count += 1
                        print(f"✅ Successfully processed: {image_file.name}")
                    else:
                        error_count += 1
                        print(f"❌ Failed to process: {image_file.name}")

                    # Pause between images to avoid overwhelming the service
                    if i < len(image_files):  # Don't pause after the last image
                        print("⏸️ Pausing before next image...")
                        time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")

        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")

        finally:
            print(f"\n{'='*50}")
            print("📊 PROCESSING SUMMARY")
            print(f"{'='*50}")
            print(f"✅ Successfully processed: {processed_count}")
            print(f"❌ Failed: {error_count}")
            print(f"📁 Output folder: {output_path}")
            print("🔄 Closing browser...")

            try:
                self.driver.quit()
            except:
                pass

    def process_single_image(self, image_path, output_folder):
        """Process a single image through the watermark removal pipeline"""
        try:
            print(f"🔄 Starting pipeline for: {image_path.name}")

            # Step 1: Upload image
            if not self.upload_image_to_qwen(str(image_path)):
                print("❌ Failed at upload step")
                return False

            # Step 2: Send prompt
            time.sleep(3)  # Wait for upload to be processed
            if not self.send_prompt("Delete watermark"):
                print("❌ Failed at prompt step")
                return False

            # Step 3: Wait for generation
            time.sleep(5)  # Initial wait for processing to start
            generation_success = self.wait_for_generation(max_wait_time=180)
            if not generation_success:
                print("⚠ Generation may not be complete, but continuing...")

            # Step 4: Download result
            downloaded_file = self.download_generated_image(image_path.name)
            if not downloaded_file:
                print("❌ Failed at download step")
                return False

            # Step 5: Move to final location with original filename
            final_path = output_folder / image_path.name

            # Ensure we don't overwrite existing files
            counter = 1
            original_stem = image_path.stem
            original_suffix = image_path.suffix

            while final_path.exists():
                final_path = output_folder / f"{original_stem}_{counter}{original_suffix}"
                counter += 1

            shutil.move(downloaded_file, final_path)
            print(f"✅ Saved to: {final_path}")

            return True

        except Exception as e:
            print(f"❌ Error processing {image_path.name}: {str(e)}")
            return False


# Usage functions
def main():
    """Main execution function"""
    # Configuration
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"
    IMAGES_FOLDER = "images"
    OUTPUT_FOLDER = "no_watermarks"

    print("🚀 Starting Qwen AI Watermark Remover")
    print(f"📂 Input folder: {IMAGES_FOLDER}")
    print(f"📁 Output folder: {OUTPUT_FOLDER}")
    print(f"🌐 Chat URL: {QWEN_CHAT_URL}")

    # Initialize and run
    remover = WatermarkRemover(QWEN_CHAT_URL)
    remover.process_images(IMAGES_FOLDER, OUTPUT_FOLDER)


def setup_authentication_only():
    """Helper function to set up authentication without processing images"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    print("🔐 Setting up authentication only...")

    remover = WatermarkRemover(QWEN_CHAT_URL)
    remover.setup_browser(use_existing_session=True)

    if remover.handle_authentication():
        print("✅ Authentication setup complete!")
        print("You can now run the main script with: python script.py")
    else:
        print("❌ Authentication setup failed.")

    remover.driver.quit()


def test_single_image():
    """Test function to process just one image"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    # Specify a test image path
    test_image = input("Enter path to test image: ").strip()
    if not os.path.exists(test_image):
        print(f"❌ Test image not found: {test_image}")
        return

    print(f"🧪 Testing with single image: {test_image}")

    remover = WatermarkRemover(QWEN_CHAT_URL)
    remover.setup_browser(use_existing_session=True)

    if remover.handle_authentication():
        output_folder = Path("test_output")
        output_folder.mkdir(exist_ok=True)

        success = remover.process_single_image(Path(test_image), output_folder)

        if success:
            print("✅ Test completed successfully!")
        else:
            print("❌ Test failed!")

    remover.driver.quit()


def create_folder_structure():
    """Helper function to create the expected folder structure"""
    print("📁 Creating folder structure for watermark removal...")

    images_folder = Path("images")
    output_folder = Path("no_watermarks")

    # Create main folders
    images_folder.mkdir(exist_ok=True)
    output_folder.mkdir(exist_ok=True)

    # Create example brand folders
    example_brands = ["brand1", "brand2", "brand3"]

    for brand in example_brands:
        brand_folder = images_folder / brand
        brand_folder.mkdir(exist_ok=True)

        # Create a readme file in each brand folder
        readme_path = brand_folder / "README.txt"
        with open(readme_path, "w") as f:
            f.write(f"Place your {brand} images here.\n")
            f.write("Supported formats: .jpg, .jpeg, .png, .webp, .gif\n")

    print("✅ Folder structure created:")
    print(f"   📂 {images_folder}/")
    for brand in example_brands:
        print(f"      📁 {brand}/")
    print(f"   📂 {output_folder}/")
    print("\nNow place your images in the brand subfolders and run the script!")


def debug_page_elements():
    """Debug function to inspect Qwen AI page elements"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    print("🔍 Debug mode: Inspecting page elements...")

    remover = WatermarkRemover(QWEN_CHAT_URL)
    remover.setup_browser(use_existing_session=True)

    if remover.handle_authentication():
        print("\n🔍 Analyzing page elements...")

        # Find all input elements
        inputs = remover.driver.find_elements(By.TAG_NAME, "input")
        print(f"Found {len(inputs)} input elements:")
        for i, inp in enumerate(inputs[:10]):  # Limit to first 10
            input_type = inp.get_attribute("type")
            input_class = inp.get_attribute("class")
            input_placeholder = inp.get_attribute("placeholder")
            input_id = inp.get_attribute("id")
            print(
                f"  {i+1}. Type: {input_type}, Class: {input_class}, Placeholder: {input_placeholder}, ID: {input_id}"
            )

        # Find all textareas
        textareas = remover.driver.find_elements(By.TAG_NAME, "textarea")
        print(f"\nFound {len(textareas)} textarea elements:")
        for i, ta in enumerate(textareas[:5]):  # Limit to first 5
            ta_class = ta.get_attribute("class")
            ta_placeholder = ta.get_attribute("placeholder")
            ta_id = ta.get_attribute("id")
            print(f"  {i+1}. Class: {ta_class}, Placeholder: {ta_placeholder}, ID: {ta_id}")

        # Find all buttons
        buttons = remover.driver.find_elements(By.TAG_NAME, "button")
        print(f"\nFound {len(buttons)} button elements:")
        for i, btn in enumerate(buttons[:10]):  # Limit to first 10
            btn_class = btn.get_attribute("class")
            btn_title = btn.get_attribute("title")
            btn_text = btn.text
            print(f"  {i+1}. Class: {btn_class}, Title: {btn_title}, Text: {btn_text}")

        # Find elements with upload-related attributes
        upload_elements = remover.driver.find_elements(
            By.CSS_SELECTOR, '[class*="upload"], [title*="upload"], [aria-label*="upload"]'
        )
        print(f"\nFound {len(upload_elements)} upload-related elements:")
        for i, elem in enumerate(upload_elements):
            elem_tag = elem.tag_name
            elem_class = elem.get_attribute("class")
            elem_title = elem.get_attribute("title")
            print(f"  {i+1}. Tag: {elem_tag}, Class: {elem_class}, Title: {elem_title}")

        print("\n🔍 Debug complete. Keep the browser open to manually inspect elements.")
        input("Press ENTER to close the browser...")

    remover.driver.quit()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "auth":
            setup_authentication_only()
        elif command == "test":
            test_single_image()
        elif command == "debug":
            debug_page_elements()
        elif command == "setup":
            create_folder_structure()
        elif command == "help":
            print("🚀 Qwen AI Watermark Remover Commands:")
            print("  python script.py           - Run full processing")
            print("  python script.py auth      - Setup authentication only")
            print("  python script.py test      - Test with single image")
            print("  python script.py debug     - Debug page elements")
            print("  python script.py setup     - Create folder structure")
            print("  python script.py help      - Show this help")
        else:
            print(f"❌ Unknown command: {command}")
            print("Use 'python script.py help' for available commands")
    else:
        main()
