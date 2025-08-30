# Chrome
# Fix download button
# Limit 50 pic / day
import asyncio
import json
import os
import platform
import shutil
import tempfile
import time
from pathlib import Path

import aiofiles
import aiohttp
from playwright.async_api import async_playwright


class WatermarkRemover:
    def __init__(self, qwen_chat_url, images_folder="images2", output_folder="no_watermarks", user_data_dir=None):
        """
        Initialize the watermark removal automation with Chrome profile support

        Args:
            qwen_chat_url (str): URL to Qwen AI chat
            images_folder (str): Source images folder
            output_folder (str): Output folder for processed images
            user_data_dir (str): Path to Chrome user data directory for persistent session
        """
        self.qwen_url = qwen_chat_url
        self.images_folder = Path(images_folder)
        self.output_folder = Path(output_folder)
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.browser = None
        self.page = None
        self.cookies_file = "qwen_cookies.json"
        self.supported_formats = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

    async def setup_browser(self, use_existing_session=True):
        """Setup Playwright browser with Chrome profile support"""
        self.playwright = await async_playwright().start()

        # Prepare browser arguments
        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--remote-debugging-port=9222",
        ]

        # Chrome user data directory setup
        automation_profile = None
        if use_existing_session:
            system = platform.system()
            if system == "Darwin":  # macOS
                default_user_data = os.path.join(
                    os.path.expanduser("~"), "Library", "Application Support", "Google", "Chrome"
                )

                # Create a copy for automation
                automation_profile = tempfile.mkdtemp(prefix="chrome_automation_")

                try:
                    print("📋 Copying Chrome profile for automation...")
                    essential_dirs = ["Default"]
                    for dir_name in essential_dirs:
                        src_dir = os.path.join(default_user_data, dir_name)
                        dst_dir = os.path.join(automation_profile, dir_name)

                        if os.path.exists(src_dir):
                            print(f"Copying {dir_name}...")
                            shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns("*Lock*", "Singleton*"))

                    print(f"✓ Using automation profile: {automation_profile}")

                except Exception as e:
                    print(f"⚠ Could not copy profile: {e}")
                    print("Creating fresh profile with saved cookies...")
            else:
                # For other systems, create temp profile
                automation_profile = tempfile.mkdtemp(prefix="chrome_fresh_")
        else:
            # Create fresh temp profile
            automation_profile = tempfile.mkdtemp(prefix="chrome_fresh_")

        # Launch browser with retries
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if automation_profile:
                    # Use persistent context when we have a user data directory
                    print(f"🌐 Launching browser with persistent context...")
                    self.browser = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=automation_profile,
                        headless=False,  # Set to True for headless mode
                        args=browser_args,
                        ignore_default_args=["--enable-automation"],
                        channel="chrome",  # Use system Chrome if available
                    )
                    # With persistent context, browser is actually the context
                    self.page = self.browser.pages[0] if self.browser.pages else await self.browser.new_page()
                else:
                    # Regular launch without persistent context
                    print(f"🌐 Launching browser without persistent context...")
                    browser = await self.playwright.chromium.launch(
                        headless=False, args=browser_args  # Set to True for headless mode
                    )
                    self.browser = await browser.new_context()
                    self.page = await self.browser.new_page()

                # Set user agent to avoid detection
                await self.page.set_extra_http_headers(
                    {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )

                # Remove webdriver property
                await self.page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                """
                )

                print("✓ Playwright browser initialized successfully")
                return True

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    print("❌ All attempts failed. Trying fallback method...")
                    # Fallback: try without persistent context
                    return await self.setup_browser_fallback()
                await asyncio.sleep(2)

        return False

    async def setup_browser_fallback(self):
        """Fallback browser setup without persistent context"""
        try:
            print("🔄 Trying fallback browser setup...")
            browser = await self.playwright.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
            self.browser = await browser.new_context()
            self.page = await self.browser.new_page()

            await self.page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )

            print("✓ Fallback browser setup successful")
            return True
        except Exception as e:
            print(f"❌ Fallback setup failed: {str(e)}")
            return False

    async def save_cookies(self):
        """Save current session cookies to file"""
        try:
            # Handle both persistent context and regular context
            if hasattr(self.browser, "cookies"):
                # Persistent context
                cookies = await self.browser.cookies()
            else:
                # Regular context
                cookies = await self.page.context.cookies()

            async with aiofiles.open(self.cookies_file, "w") as f:
                await f.write(json.dumps(cookies))
            print("✓ Cookies saved")
        except Exception as e:
            print(f"✗ Error saving cookies: {e}")

    async def load_cookies(self):
        """Load saved session cookies"""
        try:
            if os.path.exists(self.cookies_file):
                async with aiofiles.open(self.cookies_file, "r") as f:
                    cookies_data = await f.read()
                    cookies = json.loads(cookies_data)

                # Navigate to domain first
                await self.page.goto("https://chat.qwen.ai")
                await asyncio.sleep(2)

                # Add cookies - handle both context types
                if hasattr(self.browser, "add_cookies"):
                    # Persistent context
                    await self.browser.add_cookies(cookies)
                else:
                    # Regular context
                    await self.page.context.add_cookies(cookies)

                print("✓ Cookies loaded")
                return True
        except Exception as e:
            print(f"✗ Error loading cookies: {e}")
        return False

    async def check_authentication(self):
        """Check if user is authenticated and can access the chat"""
        try:
            await self.page.goto(self.qwen_url)
            await asyncio.sleep(5)

            current_url = self.page.url
            print(f"Current URL: {current_url}")

            if self.qwen_url in current_url or "chat.qwen.ai/c/" in current_url:
                # Look for chat interface elements using Qwen-specific selectors
                chat_indicators = [
                    "textarea#chat-input",  # Qwen-specific chat input
                    "input[type='text']",
                    ".chat-input",
                    "[placeholder*='message']",
                    "[placeholder*='Message']",
                    "div[contenteditable='true']",
                ]

                for indicator in chat_indicators:
                    try:
                        element = await self.page.wait_for_selector(indicator, timeout=2000)
                        if element and await element.is_visible():
                            print("✓ Chat interface detected - authenticated")
                            return True
                    except:
                        continue

                print("⚠ Chat URL correct but no input found")
                return True
            else:
                print(f"❌ Not on chat page. Current: {current_url}")
                return False

        except Exception as e:
            print(f"✗ Error checking authentication: {e}")
            return False

    async def handle_authentication(self):
        """Handle authentication process"""
        print("🔐 Handling authentication...")

        # Method 1: Try loading saved cookies
        if await self.load_cookies():
            if await self.check_authentication():
                return True

        # Method 2: Check if already logged in via Chrome profile
        if await self.check_authentication():
            await self.save_cookies()
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
        await self.page.goto("https://chat.qwen.ai")
        await asyncio.sleep(3)

        # Wait for manual login
        input("Press ENTER when you have logged in and are ready to continue...")

        # Navigate to specific chat
        await self.page.goto(self.qwen_url)
        await asyncio.sleep(5)

        # Verify authentication
        if await self.check_authentication():
            await self.save_cookies()
            print("✅ Authentication successful!")
            return True
        else:
            print("❌ Authentication failed!")
            return False

    async def upload_image_to_qwen(self, image_path):
        """Upload image to Qwen AI chat interface with correct selectors"""
        try:
            print(f"🔄 Uploading image: {image_path.name}")

            # Navigate to chat if not already there
            if self.qwen_url not in self.page.url:
                await self.page.goto(self.qwen_url)
                await asyncio.sleep(3)

            # Qwen-specific selectors from your working Selenium code
            # We'll stick to the button selector and use Playwright's file chooser
            upload_button_selector = "button.chat-prompt-upload-group-btn"

            # Use Playwright's file chooser event listener
            async with self.page.expect_file_chooser() as fc_info:
                # Find and click the button that triggers the file upload
                upload_button = await self.page.wait_for_selector(upload_button_selector, timeout=10000)
                if not upload_button:
                    print("❌ Could not find the file upload button.")
                    return False

                print("📎 Clicking upload button to trigger file chooser...")
                await upload_button.click()

            # Get the file chooser and set the file
            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))

            print(f"✓ Image selected successfully: {image_path.name}")
            await asyncio.sleep(5)  # Wait for upload to process

            # Wait for the image preview to appear to confirm success
            # This is an extra step for robustness
            image_preview_selector = f'img[src*="{image_path.name}"]'  # A potential selector based on filename
            try:
                await self.page.wait_for_selector(image_preview_selector, state="visible", timeout=10000)
                print("✓ Image preview detected. Upload confirmed.")
            except:
                print("⚠ Image preview not detected. Continuing anyway.")

            return True

        except Exception as e:
            print(f"❌ Error uploading image: {str(e)}")
            return False

    async def send_prompt(self, prompt="Delete watermark"):
        """Send the watermark removal prompt using correct Qwen selectors"""
        try:
            print(f"💬 Sending prompt: {prompt}")

            # Qwen-specific selectors from your working code
            textarea_selector = "textarea#chat-input"
            send_button_selector = "button#send-message-button"

            # Find the textarea
            try:
                input_element = await self.page.wait_for_selector(textarea_selector, timeout=10000)
                print("✓ Found chat input textarea")
            except:
                print("✗ Could not find chat input textarea")
                return False

            # Clear and enter text
            await input_element.fill("")
            await input_element.type(prompt)
            await asyncio.sleep(1)

            # Try to find and click send button
            try:
                send_button = await self.page.wait_for_selector(send_button_selector, timeout=5000)

                # Check if button is disabled
                is_disabled = await send_button.get_attribute("disabled")
                class_list = await send_button.get_attribute("class") or ""

                if is_disabled or "disabled" in class_list:
                    print("⚠ Send button is disabled, trying Enter key instead")
                    await input_element.press("Enter")
                else:
                    await send_button.click()
                    print("✓ Clicked send button")

            except:
                print("⚠ Send button not found, using Enter key")
                await input_element.press("Enter")

            print("✓ Prompt sent successfully")
            await asyncio.sleep(3)
            return True

        except Exception as e:
            print(f"✗ Error sending prompt: {str(e)}")
            return False

    # async def wait_for_generation(self, max_wait_time=120):
    #     """
    #     Wait for image generation to complete by looking for the absence of loading indicators
    #     and the presence of the generated image and download button.
    #     """
    #     print("⏳ Waiting for generation to complete...")

    #     start_time = time.time()
    #     last_check_time = start_time

    #     while time.time() - start_time < max_wait_time:
    #         current_time = time.time()
    #         if current_time - last_check_time > 10:
    #             elapsed = int(current_time - start_time)
    #             print(f"⏳ Still waiting... ({elapsed}s elapsed)")
    #             last_check_time = current_time

    #         # Check for specific loading indicators from your HTML
    #         loading_indicator_selector = ".vlo-image-generating"

    #         # Check for completion indicators from your HTML
    #         generated_image_selector = '.vlo-image-content img[src*="qwenlm.ai/output"]'
    #         download_button_selector = ".icon-line-download-02"

    #         try:
    #             # Is the loading element still visible?
    #             loading_element = await self.page.query_selector(loading_indicator_selector)
    #             is_loading_visible = loading_element and await loading_element.is_visible()

    #             # Are the generated image and download button visible?
    #             generated_image = await self.page.query_selector(generated_image_selector)
    #             download_button = await self.page.query_selector(download_button_selector)

    #             if (generated_image and await generated_image.is_visible()) and (
    #                 download_button and await download_button.is_visible()
    #             ):
    #                 # Generation is complete if the image and download button are visible
    #                 print("✓ Generation completed! Image and download button detected.")
    #                 return True

    #             if is_loading_visible:
    #                 # Still loading, so we continue to wait
    #                 await asyncio.sleep(3)
    #             else:
    #                 # No loading indicator, but no completion indicators either. This is an edge case.
    #                 # We should wait a bit longer to be sure before returning False.
    #                 print("⚠ Loading indicator disappeared, but completion elements not found yet.")
    #                 await asyncio.sleep(3)

    #         except Exception as e:
    #             print(f"Error during check: {e}. Retrying...")
    #             await asyncio.sleep(3)

    #     print("⚠ Generation timeout reached. Completion elements not found.")
    #     return False

    async def wait_for_generation(self, max_wait_time=20):
        """
        Improved wait logic that checks for completion of the most recent response
        """
        print(f"⏳ Waiting up to {max_wait_time} seconds for generation to complete...")

        start_time = time.time()
        last_check_time = start_time

        while time.time() - start_time < max_wait_time:
            current_time = time.time()

            # Progress update every 15 seconds
            if current_time - last_check_time > 15:
                elapsed = int(current_time - start_time)
                print(f"⏳ Still waiting for generation... ({elapsed}s elapsed)")
                last_check_time = current_time

            try:
                # Get the most recent response container
                response_containers = await self.page.query_selector_all(".response-meesage-container")
                if not response_containers:
                    await asyncio.sleep(3)
                    continue

                latest_response = response_containers[-1]

                # Check if generation is still in progress
                loading_indicator = await latest_response.query_selector(".vlo-image-generating")
                is_still_generating = loading_indicator and await loading_indicator.is_visible()

                # Check if the final image is ready
                generated_image = await latest_response.query_selector(".vlo-image-content img")
                is_image_ready = generated_image and await generated_image.is_visible()

                if is_image_ready and not is_still_generating:
                    print("✅ Generation completed! Image is ready.")

                    # Extra wait to ensure image is fully loaded
                    await asyncio.sleep(3)
                    return True

                elif is_still_generating:
                    print("🔄 Generation still in progress...")
                    await asyncio.sleep(5)
                else:
                    # Neither loading nor ready - ambiguous state
                    print("⚠ Ambiguous generation state, waiting...")
                    await asyncio.sleep(3)

            except Exception as e:
                print(f"⚠ Error during generation check: {e}")
                await asyncio.sleep(5)

        print(f"⚠ Generation timeout reached after {max_wait_time}s")
        return False  # Don't fail completely, just proceed with download attempt

    async def download_generated_image(self, original_filename):
        """Download the generated image from the most recent response with best quality"""
        try:
            print("💾 Attempting to download generated image from latest response...")

            # Step 1: Find the most recent response message container
            await asyncio.sleep(2)  # Allow page to fully load

            # Get all response message containers, ordered by appearance (last is most recent)
            response_containers = await self.page.query_selector_all(".response-meesage-container")

            if not response_containers:
                print("❌ No response containers found")
                return None

            latest_response = response_containers[-1]  # Get the most recent one
            print(f"✓ Found {len(response_containers)} response containers, targeting the latest")

            # Step 2: First try to get the high-quality image URL directly
            # Look for the generated image within the latest response
            generated_image = await latest_response.query_selector(".vlo-image-content img")

            if generated_image:
                img_src = await generated_image.get_attribute("src")
                if img_src and "cdn.qwenlm.ai/output" in img_src:
                    print(f"✓ Found generated image URL: {img_src[:100]}...")

                    # Get the high-quality version by removing the resize parameter
                    high_quality_url = img_src.split("&x-oss-process=")[0] if "&x-oss-process=" in img_src else img_src
                    print(f"🔍 Using high-quality URL: {high_quality_url[:100]}...")

                    # Try to download via HTTP first (best quality)
                    downloaded_file = await self.download_image_via_http(high_quality_url, original_filename)
                    if downloaded_file:
                        print("✅ Successfully downloaded via high-quality HTTP")
                        return downloaded_file

            # Step 3: If direct download fails, try the download button approach
            print("🔄 Direct download failed, trying download button...")

            # Hover over the latest response to make buttons visible
            try:
                await latest_response.hover()
                await asyncio.sleep(1)  # Wait for hover effects
                print("✓ Hovered over latest response to make buttons visible")
            except Exception as e:
                print(f"⚠ Could not hover over response: {e}")

            # Look for download button within the latest response
            download_button_selectors = [
                # Most specific - download button with the download icon within this response
                'div[aria-label="Загрузить"] button',
                'div[aria-label="Download"] button',
                "button:has(i.icon-line-download-02)",
                ".message-footer-button-item:has(i.icon-line-download-02)",
            ]

            download_button = None
            for selector in download_button_selectors:
                try:
                    # Search within the latest response container
                    download_button = await latest_response.query_selector(selector)
                    if download_button and await download_button.is_visible():
                        print(f"✓ Found download button with selector: {selector}")
                        break
                except Exception as e:
                    continue

            if download_button:
                try:
                    print("🔄 Clicking download button...")

                    # Set up download listener before clicking
                    async with self.page.expect_download(timeout=30000) as download_info:
                        # Ensure the button is clickable
                        await download_button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)

                        try:
                            await download_button.click()
                            print("✓ Successfully clicked download button")
                        except Exception as click_error:
                            print(f"Regular click failed: {click_error}. Trying force click...")
                            await download_button.click(force=True)

                    # Get the download and save it
                    download = await download_info.value

                    # Save download to temp location
                    timestamp = int(time.time())
                    file_extension = Path(original_filename).suffix or ".png"
                    temp_filename = f"downloaded_{timestamp}_{Path(original_filename).stem}{file_extension}"
                    temp_path = Path(tempfile.gettempdir()) / temp_filename

                    await download.save_as(temp_path)
                    print(f"✅ Download completed via button: {temp_filename}")
                    return str(temp_path)

                except Exception as download_error:
                    print(f"❌ Button download failed: {str(download_error)}")

            # Step 4: Screenshot fallback for the generated image
            if generated_image:
                try:
                    print("📸 Fallback: Taking screenshot of generated image...")

                    timestamp = int(time.time())
                    file_extension = Path(original_filename).suffix or ".png"
                    temp_filename = f"screenshot_{timestamp}_{Path(original_filename).stem}{file_extension}"
                    temp_path = Path(tempfile.gettempdir()) / temp_filename

                    # Scroll image into view and take screenshot
                    await generated_image.scroll_into_view_if_needed()
                    await asyncio.sleep(1)

                    await generated_image.screenshot(path=temp_path)
                    print(f"✅ Screenshot completed: {temp_filename}")
                    return str(temp_path)

                except Exception as e:
                    print(f"❌ Screenshot failed: {e}")

            print("❌ All download methods failed")
            return None

        except Exception as e:
            print(f"❌ Critical error in download process: {str(e)}")
            import traceback

            traceback.print_exc()
            return None

    async def download_image_via_http(self, img_url, original_filename):
        """Enhanced HTTP download with better error handling and quality optimization"""
        try:
            print(f"🌐 Downloading via HTTP: {img_url[:100]}...")

            # Get cookies from browser context
            if hasattr(self.browser, "cookies"):
                cookies = await self.browser.cookies()
            else:
                cookies = await self.page.context.cookies()

            cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}

            headers = {
                "User-Agent": await self.page.evaluate("navigator.userAgent"),
                "Referer": self.page.url,
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
            }

            timeout = aiohttp.ClientTimeout(total=60)  # Longer timeout for large images

            async with aiohttp.ClientSession(
                cookies=cookie_dict,
                headers=headers,
                timeout=timeout,
                connector=aiohttp.TCPConnector(limit=10, limit_per_host=5),
            ) as session:
                async with session.get(img_url) as response:
                    if response.status == 200:
                        content = await response.read()

                        if len(content) < 1000:  # Suspiciously small file
                            print(f"⚠ Downloaded file is too small ({len(content)} bytes), likely an error page")
                            return None

                        timestamp = int(time.time())
                        file_extension = Path(original_filename).suffix or ".png"
                        temp_filename = f"http_download_{timestamp}_{Path(original_filename).stem}{file_extension}"
                        temp_path = Path(tempfile.gettempdir()) / temp_filename

                        async with aiofiles.open(temp_path, "wb") as f:
                            await f.write(content)

                        print(f"✅ HTTP download successful: {temp_filename} ({len(content)} bytes)")
                        return str(temp_path)
                    else:
                        print(f"❌ HTTP download failed with status: {response.status}")
                        return None

        except asyncio.TimeoutError:
            print("❌ HTTP download timed out")
            return None
        except Exception as e:
            print(f"❌ HTTP download error: {str(e)}")
            return None

    async def download_image_via_http(self, img_url, original_filename):
        """Download image using HTTP request with session cookies"""
        try:
            print("🌐 Downloading via HTTP request...")

            # Get cookies from browser context
            if hasattr(self.browser, "cookies"):
                # Persistent context
                cookies = await self.browser.cookies()
            else:
                # Regular context
                cookies = await self.page.context.cookies()

            cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}

            headers = {
                "User-Agent": await self.page.evaluate("navigator.userAgent"),
                "Referer": self.page.url,
            }

            async with aiohttp.ClientSession(cookies=cookie_dict, headers=headers) as session:
                async with session.get(img_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()

                        timestamp = int(time.time())
                        temp_filename = f"temp_{timestamp}_{original_filename}"
                        temp_path = Path(tempfile.gettempdir()) / temp_filename

                        async with aiofiles.open(temp_path, "wb") as f:
                            await f.write(content)

                        print(f"✓ Downloaded via HTTP: {temp_filename}")
                        return str(temp_path)

        except Exception as e:
            print(f"✗ Error downloading via HTTP: {str(e)}")
            return None

    async def process_single_image(self, image_path, brand_output_folder):
        """Process a single image through the watermark removal pipeline"""
        try:
            print(f"🔄 Starting pipeline for: {image_path.name}")

            # Step 1: Upload image
            if not await self.upload_image_to_qwen(image_path):
                print("❌ Failed at upload step")
                return False

            # Step 2: Send prompt
            await asyncio.sleep(3)
            if not await self.send_prompt("Delete watermark"):
                print("❌ Failed at prompt step")
                return False

            # Step 3: Wait for generation
            await asyncio.sleep(5)
            generation_success = await self.wait_for_generation(max_wait_time=20)
            if not generation_success:
                print("⚠ Generation may not be complete, but continuing...")

            # Step 4: Download result
            downloaded_file = await self.download_generated_image(image_path.name)
            if not downloaded_file:
                print("❌ Failed at download step")
                return False

            # Step 5: Move to final location with original filename
            final_path = brand_output_folder / image_path.name

            # Ensure we don't overwrite existing files
            counter = 1
            original_stem = image_path.stem
            original_suffix = image_path.suffix

            while final_path.exists():
                final_path = brand_output_folder / f"{original_stem}_{counter}{original_suffix}"
                counter += 1

            shutil.move(downloaded_file, final_path)
            print(f"✅ Saved to: {final_path}")

            return True

        except Exception as e:
            print(f"❌ Error processing {image_path.name}: {str(e)}")
            return False

    async def process_all_images(self):
        """Process all images in the images folder"""
        if not self.images_folder.exists():
            print(f"❌ Images folder not found: {self.images_folder}")
            return

        # Create output folder structure
        self.output_folder.mkdir(exist_ok=True)
        print(f"📁 Output folder created/verified: {self.output_folder}")

        # Setup browser
        if not await self.setup_browser(use_existing_session=True):
            print("❌ Failed to setup browser")
            return

        # Handle authentication
        if not await self.handle_authentication():
            print("❌ Authentication failed - cannot proceed")
            await self.browser.close()
            await self.playwright.stop()
            return

        processed_count = 0
        error_count = 0

        try:
            # Get all brand folders
            brand_folders = [f for f in self.images_folder.iterdir() if f.is_dir()]

            if not brand_folders:
                print("❌ No brand folders found in images directory")
                return

            print(f"📂 Found {len(brand_folders)} brand folders")

            # Process each brand folder
            for brand_folder in brand_folders:
                print(f"\n{'='*50}")
                print(f"📁 Processing brand folder: {brand_folder.name}")
                print(f"{'='*50}")

                # Create brand folder in output
                brand_output = self.output_folder / brand_folder.name
                brand_output.mkdir(exist_ok=True)
                print(f"📂 Created output folder: {brand_output}")

                # Get all image files
                image_files = [
                    f for f in brand_folder.iterdir() if f.is_file() and f.suffix.lower() in self.supported_formats
                ]

                if not image_files:
                    print(f"⚠️  No images found in {brand_folder.name}")
                    continue

                print(f"📸 Found {len(image_files)} images")

                # Process each image
                for i, image_file in enumerate(image_files, 1):
                    print(f"\n[{i}/{len(image_files)}] 🖼️ Processing: {image_file.name}")

                    # Check if already processed
                    output_file = brand_output / image_file.name
                    if output_file.exists():
                        print(f"⏭️ Skipping (already exists): {image_file.name}")
                        continue

                    # Process the image
                    success = await self.process_single_image(image_file, brand_output)

                    if success:
                        processed_count += 1
                        print(f"✅ Successfully processed: {image_file.name}")
                    else:
                        error_count += 1
                        print(f"❌ Failed to process: {image_file.name}")

                    # Pause between images
                    if i < len(image_files):
                        print("⏸️ Pausing before next image...")
                        await asyncio.sleep(5)

            print(f"\n🎉 Processing complete!")
            print(f"📊 Total images processed: {processed_count + error_count}")
            print(f"✅ Successful: {processed_count}")
            print(f"❌ Failed: {error_count}")

        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
        finally:
            # Cleanup
            print("🔄 Closing browser...")
            try:
                if hasattr(self, "browser") and self.browser:
                    await self.browser.close()
                if hasattr(self, "playwright") and self.playwright:
                    await self.playwright.stop()
            except Exception as e:
                print(f"⚠ Error during cleanup: {e}")


# Utility functions
async def setup_authentication_only():
    """Helper function to set up authentication without processing images"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    print("🔐 Setting up authentication only...")

    remover = WatermarkRemover(QWEN_CHAT_URL)
    await remover.setup_browser(use_existing_session=True)

    if await remover.handle_authentication():
        print("✅ Authentication setup complete!")
        print("You can now run the main script")
    else:
        print("❌ Authentication setup failed.")

    await remover.browser.close()
    await remover.playwright.stop()


async def test_single_image():
    """Test function to process just one image"""
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"

    test_image = input("Enter path to test image: ").strip()
    if not os.path.exists(test_image):
        print(f"❌ Test image not found: {test_image}")
        return

    print(f"🧪 Testing with single image: {test_image}")

    remover = WatermarkRemover(QWEN_CHAT_URL)
    await remover.setup_browser(use_existing_session=True)

    if await remover.handle_authentication():
        output_folder = Path("test_output")
        output_folder.mkdir(exist_ok=True)

        success = await remover.process_single_image(Path(test_image), output_folder)

        if success:
            print("✅ Test completed successfully!")
        else:
            print("❌ Test failed!")

    try:
        await remover.browser.close()
        await remover.playwright.stop()
    except:
        pass


def create_folder_structure():
    """Helper function to create the expected folder structure"""
    print("📁 Creating folder structure for watermark removal...")

    images_folder = Path("images2")
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


async def main():
    """Main function"""
    print("🚀 Starting Watermark Removal Automation with Playwright + Chrome Auth")
    print("=" * 70)

    # Configuration
    QWEN_CHAT_URL = "https://chat.qwen.ai/c/720e0f7e-7a90-4b81-87cb-9fc1e1b85982"
    IMAGES_FOLDER = "images2"
    OUTPUT_FOLDER = "no_watermarks"

    print(f"📂 Input folder: {IMAGES_FOLDER}")
    print(f"📁 Output folder: {OUTPUT_FOLDER}")
    print(f"🌐 Chat URL: {QWEN_CHAT_URL}")

    # Create remover instance
    remover = WatermarkRemover(qwen_chat_url=QWEN_CHAT_URL, images_folder=IMAGES_FOLDER, output_folder=OUTPUT_FOLDER)

    # Process all images
    await remover.process_all_images()


if __name__ == "__main__":
    import sys

    try:
        print("🔍 Script started...")

        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            print(f"📋 Running command: {command}")

            if command == "auth":
                print("🔐 Starting authentication setup...")
                asyncio.run(setup_authentication_only())
            elif command == "test":
                print("🧪 Starting test mode...")
                asyncio.run(test_single_image())
            elif command == "setup":
                print("📁 Creating folder structure...")
                create_folder_structure()
            elif command == "help":
                print("🚀 Watermark Remover Commands:")
                print("  python script.py           - Run full processing")
                print("  python script.py auth      - Setup authentication only")
                print("  python script.py test      - Test with single image")
                print("  python script.py setup     - Create folder structure")
                print("  python script.py help      - Show this help")
            else:
                print(f"❌ Unknown command: {command}")
                print("Use 'python script.py help' for available commands")
        else:
            print("🚀 Starting main processing...")
            # Check if images folder exists
            if not Path("images2").exists():
                print("❌ Images folder not found!")
                print("Creating folder structure first...")
                create_folder_structure()
                print("✅ Folder structure created. Please add your images and run again.")
            else:
                asyncio.run(main())

    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        print("👋 Script finished")
