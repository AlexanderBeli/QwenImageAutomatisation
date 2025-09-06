# 20 секунд
# No login modal перед сохранением отредактированного изображения
# размер батча 5 картинок
# images2
import asyncio
import json
import os
import platform
import random
import shutil
import tempfile
import time
from pathlib import Path

import aiofiles
import aiohttp
from playwright.async_api import async_playwright


class ProxyManager:
    def __init__(self, proxies_file="proxies.txt"):
        """Initialize proxy manager with proxy file"""
        self.proxies_file = proxies_file
        self.proxies = []
        self.current_proxy_index = 0
        self.load_proxies()

    def load_proxies(self):
        """Load proxies from file"""
        try:
            with open(self.proxies_file, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and ":" in line:
                        parts = line.split(":")
                        if len(parts) >= 4:
                            host = parts[0]
                            port = parts[1]
                            username = parts[2]
                            password = parts[3]

                            proxy_config = {
                                "server": f"http://{host}:{port}",
                                "username": username,
                                "password": password,
                            }
                            self.proxies.append(proxy_config)

            print(f"Loaded {len(self.proxies)} proxies from {self.proxies_file}")

            if not self.proxies:
                print("WARNING: No valid proxies found. Will run without proxy.")

        except FileNotFoundError:
            print(f"Proxy file {self.proxies_file} not found. Will run without proxy.")
        except Exception as e:
            print(f"Error loading proxies: {e}")

    def get_next_proxy(self):
        """Get next proxy from the list"""
        if not self.proxies:
            return None

        if self.current_proxy_index >= len(self.proxies):
            self.current_proxy_index = 0

        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index += 1

        return proxy

    def get_current_proxy_info(self):
        """Get info about current proxy"""
        if not self.proxies:
            return "No proxy"

        current_index = self.current_proxy_index - 1
        if current_index < 0:
            current_index = len(self.proxies) - 1

        proxy = self.proxies[current_index]
        return f"Proxy {current_index + 1}/{len(self.proxies)}: {proxy['server']}"


class WatermarkRemover:
    def __init__(self, images_folder="images2", output_folder="no_watermarks", batch_size=5):
        """
        Initialize the watermark removal automation with proxy support

        Args:
            images_folder (str): Source images folder
            output_folder (str): Output folder for processed images
            batch_size (int): Number of images to process per proxy session
        """
        self.qwen_url = "https://chat.qwen.ai/?inputFeature=image_edit"
        self.images_folder = Path(images_folder)
        self.output_folder = Path(output_folder)
        self.batch_size = batch_size
        self.playwright = None
        self.browser = None
        self.page = None
        self.supported_formats = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
        self.proxy_manager = ProxyManager()

    async def setup_browser_with_proxy(self, proxy_config=None):
        """Setup Playwright browser with proxy support"""
        self.playwright = await async_playwright().start()

    async def setup_browser_with_proxy(self, proxy_config=None):
        """Setup Playwright browser with proxy support"""
        self.playwright = await async_playwright().start()

    async def setup_browser_with_proxy(self, proxy_config=None):
        """Setup Playwright browser with proxy support and fresh session"""
        self.playwright = await async_playwright().start()

        # Enhanced browser arguments to look more human-like
        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--disable-features=VizDisplayCompositor",
            "--disable-extensions-except",
            "--disable-plugins-discovery",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-field-trial-config",
            "--disable-back-forward-cache",
            "--disable-ipc-flooding-protection",
            # Additional stealth parameters
            "--disable-automation",
            "--disable-dev-shm-usage",
            "--no-zygote",
            "--no-sandbox",
            "--disable-gpu-sandbox",
            "--disable-software-rasterizer",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-extensions",
            # Use a fresh user data directory for each session
            f"--user-data-dir={tempfile.mkdtemp()}",
            f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"Launching browser (attempt {attempt + 1}/{max_attempts})...")

    async def setup_browser_with_proxy(self, proxy_config=None):
        """Setup Playwright browser with proxy support and fresh session"""
        self.playwright = await async_playwright().start()

        # Enhanced browser arguments to look more human-like (removed user-data-dir from args)
        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--disable-features=VizDisplayCompositor",
            "--disable-extensions-except",
            "--disable-plugins-discovery",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-field-trial-config",
            "--disable-back-forward-cache",
            "--disable-ipc-flooding-protection",
            "--disable-automation",
            "--disable-gpu-sandbox",
            "--disable-software-rasterizer",
            "--disable-background-timer-throttling",
            "--disable-features=TranslateUI",
            "--disable-extensions",
        ]

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                print(f"Launching browser (attempt {attempt + 1}/{max_attempts})...")

                if proxy_config:
                    print(f"Using proxy: {proxy_config['server']}")

                    # Create a temporary user data directory for isolation
                    temp_user_data = tempfile.mkdtemp(prefix="chrome_session_")
                    print(f"Using temp user data dir: {temp_user_data}")

                    # Launch browser with persistent context and proxy
                    self.browser = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=temp_user_data,
                        headless=True,  # Set to False to see the browser
                        args=browser_args,
                        proxy=proxy_config,
                        ignore_default_args=["--enable-automation"],
                        channel="chrome",  # Use system Chrome if available
                    )
                    # With persistent context, browser is actually the context
                    self.page = self.browser.pages[0] if self.browser.pages else await self.browser.new_page()
                else:
                    print("Launching browser without proxy...")
                    # Create a temporary user data directory for isolation
                    temp_user_data = tempfile.mkdtemp(prefix="chrome_session_")
                    print(f"Using temp user data dir: {temp_user_data}")

                    self.browser = await self.playwright.chromium.launch_persistent_context(
                        user_data_dir=temp_user_data,
                        headless=True,  # Set to False to see the browser
                        args=browser_args,
                        ignore_default_args=["--enable-automation"],
                        channel="chrome",
                    )
                    self.page = self.browser.pages[0] if self.browser.pages else await self.browser.new_page()

                # Generate realistic user agent variations
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
                ]

                selected_user_agent = random.choice(user_agents)

                # Set realistic headers
                await self.page.set_extra_http_headers(
                    {
                        "User-Agent": selected_user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,uk;q=0.7",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0",
                        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                    }
                )

                # Set viewport to common resolution
                await self.page.set_viewport_size({"width": 1920, "height": 1080})

                # Enhanced stealth scripts to avoid detection
                await self.page.add_init_script(
                    """
                    // Remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    // Override plugins and languages
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en'],
                    });
                    
                    // Mock chrome runtime
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                    );
                    
                    // Add realistic screen properties
                    Object.defineProperty(screen, 'availTop', {
                        get: () => 0,
                    });
                    Object.defineProperty(screen, 'availLeft', {
                        get: () => 0,
                    });
                """
                )

                # Test the connection
                print("Testing connection...")
                await self.page.goto("https://httpbin.org/ip", timeout=30000)
                await asyncio.sleep(2)

                # Check if we can access Qwen
                print("Testing Qwen accessibility...")
                await self.page.goto(self.qwen_url, timeout=30000)
                await asyncio.sleep(5)

                # Add human-like browsing behavior
                await self.page.evaluate(
                    """
                    // Simulate mouse movements
                    document.addEventListener('mousemove', (e) => {
                        // Natural mouse movement simulation
                    });
                    
                    // Add realistic timing
                    const originalSetTimeout = window.setTimeout;
                    window.setTimeout = function(callback, delay) {
                        // Add small random delays to make interactions seem more human
                        const humanDelay = delay + Math.random() * 100;
                        return originalSetTimeout(callback, humanDelay);
                    };
                """
                )

                print("Browser setup successful with enhanced human-like behavior!")
                return True

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")

                # Clean up failed attempt
                try:
                    if hasattr(self, "browser") and self.browser:
                        await self.browser.close()
                    if hasattr(self, "playwright") and self.playwright:
                        await self.playwright.stop()
                except:
                    pass

                if attempt == max_attempts - 1:
                    print(f"All attempts failed for proxy: {proxy_config['server'] if proxy_config else 'No proxy'}")
                    return False

                await asyncio.sleep(5)

        return False

    async def check_authentication(self):
        """Check if the page is accessible and ready for use"""
        try:
            current_url = self.page.url
            print(f"Current URL: {current_url}")

            if "chat.qwen.ai" in current_url:
                # Wait for page to load
                await asyncio.sleep(3)

                # Look for upload button or other interface elements
                upload_indicators = [
                    "button.chat-prompt-upload-group-btn",
                    "input[type='file']",
                    ".upload-button",
                    "[accept*='image']",
                ]

                for indicator in upload_indicators:
                    try:
                        element = await self.page.wait_for_selector(indicator, timeout=3000)
                        if element:
                            print("Upload interface detected - ready to use")
                            return True
                    except:
                        continue

                print("Page loaded but upload interface not found")
                return True  # Still consider it authenticated if we're on the right domain
            else:
                print(f"Not on Qwen page. Current: {current_url}")
                return False

        except Exception as e:
            print(f"Error checking authentication: {e}")
            return False

    async def handle_authentication(self):
        """Handle authentication with simplified approach"""
        print("Checking page accessibility...")

        try:
            # Navigate to the target URL
            await self.page.goto(self.qwen_url, timeout=30000)
            await asyncio.sleep(random.uniform(3, 6))

            # Simulate some basic human behavior
            await self.simulate_basic_human_behavior()

            # Check if login modal appears
            await self.handle_login_modal()

            if await self.check_authentication():
                print("Page is accessible and ready!")
                return True
            else:
                print("Page access failed.")
                return False

        except Exception as e:
            print(f"Error during authentication: {e}")
            return False

    async def simulate_basic_human_behavior(self):
        """Basic human behavior simulation"""
        try:
            # Random mouse movements
            for _ in range(2):
                x = random.randint(100, 1800)
                y = random.randint(100, 900)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.2, 0.5))

            # Small scroll
            await self.page.mouse.wheel(0, random.randint(-200, 200))
            await asyncio.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"Error in behavior simulation: {e}")

    # Remove the problematic methods that are causing errors
    async def create_fresh_session_per_proxy(self):
        """Simplified session creation"""
        return True

    async def generate_realistic_session_data(self):
        """Simplified session data generation"""
        return True

    async def handle_login_modal(self):
        """Handle the login modal that appears when trying to use features"""
        try:
            print("Checking for login modal...")

            # Wait a bit for modal to potentially appear
            await asyncio.sleep(2)

            # Look for the modal with "Welcome" text
            modal_selectors = [
                'div:has-text("Welcome")',
                'div:has-text("Login or sign up")',
                'button:has-text("Stay logged out")',
                '[class*="modal"]',
                '[class*="dialog"]',
            ]

            modal_found = False
            for selector in modal_selectors:
                try:
                    modal = await self.page.wait_for_selector(selector, timeout=3000)
                    if modal and await modal.is_visible():
                        print(f"Found modal with selector: {selector}")
                        modal_found = True
                        break
                except:
                    continue

            if modal_found:
                print("Login modal detected, looking for 'Stay logged out' button...")

                # Try different selectors for "Stay logged out" button
                stay_logged_out_selectors = [
                    'button:has-text("Stay logged out")',
                    'button[class*="text-"]:has-text("Stay logged out")',
                    'button:contains("Stay logged out")',
                    '//button[contains(text(), "Stay logged out")]',
                ]

                button_clicked = False
                for selector in stay_logged_out_selectors:
                    try:
                        if selector.startswith("//"):
                            # XPath selector
                            button = await self.page.wait_for_selector(f"xpath={selector}", timeout=3000)
                        else:
                            button = await self.page.wait_for_selector(selector, timeout=3000)

                        if button and await button.is_visible():
                            print("Found 'Stay logged out' button, clicking...")

                            # Human-like behavior before clicking
                            await button.hover()
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                            await button.click()

                            print("Successfully clicked 'Stay logged out'")
                            button_clicked = True
                            break
                    except Exception as e:
                        print(f"Selector {selector} failed: {e}")
                        continue

                if not button_clicked:
                    print("Could not find 'Stay logged out' button, trying to close modal...")
                    # Try pressing Escape to close modal
                    await self.page.keyboard.press("Escape")

                # Wait for modal to disappear
                await asyncio.sleep(2)
                print("Login modal handled")
            else:
                print("No login modal detected")

        except Exception as e:
            print(f"Error handling login modal: {e}")

    async def upload_image_to_qwen(self, image_path):
        """Upload image to Qwen AI chat interface"""
        try:
            print(f"Uploading image: {image_path.name}")

            # Navigate to chat if not already there
            if "chat.qwen.ai" not in self.page.url:
                await self.page.goto(self.qwen_url)

                # Human-like page loading wait
                await asyncio.sleep(random.uniform(2, 4))

            # Handle any login modal that might appear
            await self.handle_login_modal()

            # Add random mouse movement to simulate human behavior
            await self.page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))

            upload_button_selector = "button.chat-prompt-upload-group-btn"

            # Use Playwright's file chooser event listener
            async with self.page.expect_file_chooser() as fc_info:
                upload_button = await self.page.wait_for_selector(upload_button_selector, timeout=10000)
                if not upload_button:
                    print("Could not find the file upload button.")
                    return False

                # Simulate human-like hover before click
                await upload_button.hover()
                await asyncio.sleep(random.uniform(0.2, 0.8))

                print("Clicking upload button...")
                await upload_button.click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))

            print(f"Image selected successfully: {image_path.name}")

            # Human-like wait after upload and check for any modals
            await asyncio.sleep(random.uniform(2, 4))
            await self.handle_login_modal()
            await asyncio.sleep(random.uniform(1, 2))

            return True

        except Exception as e:
            print(f"Error uploading image: {str(e)}")
            return False

    async def send_prompt_with_modal_handling(self, prompt="Delete watermark", max_attempts=3):
        """Send prompt and handle login modal that appears after clicking send"""
        try:
            print(f"Sending prompt: {prompt}")

            textarea_selector = "textarea#chat-input"
            send_button_selector = "button#send-message-button"

            try:
                input_element = await self.page.wait_for_selector(textarea_selector, timeout=10000)
                print("Found chat input textarea")
            except:
                print("Could not find chat input textarea")
                return False

            # Type the prompt first
            await input_element.click()
            await asyncio.sleep(random.uniform(0.2, 0.6))

            await input_element.fill("")
            await asyncio.sleep(random.uniform(0.1, 0.3))

            # Type with human-like speed and pauses
            for char in prompt:
                await input_element.type(char, delay=random.uniform(50, 150))
                if random.random() < 0.1:  # 10% chance for a longer pause (thinking)
                    await asyncio.sleep(random.uniform(0.2, 0.5))

            await asyncio.sleep(random.uniform(0.5, 1.2))

            # Try to send with modal handling (multiple attempts if needed)
            for attempt in range(max_attempts):
                print(f"Send attempt {attempt + 1}/{max_attempts}")

                success = await self.attempt_send_with_modal_handling(send_button_selector, input_element)

                if success:
                    print("Prompt sent successfully!")
                    await asyncio.sleep(random.uniform(2, 4))
                    return True
                else:
                    print(f"Send attempt {attempt + 1} failed")
                    if attempt < max_attempts - 1:
                        print("Retrying...")
                        await asyncio.sleep(random.uniform(2, 4))

            print("All send attempts failed")
            return False

        except Exception as e:
            print(f"Error sending prompt: {str(e)}")
            return False

    async def attempt_send_with_modal_handling(self, send_button_selector, input_element):
        """Single attempt to send message with modal handling"""
        try:
            # Click send button
            try:
                send_button = await self.page.wait_for_selector(send_button_selector, timeout=5000)
                is_disabled = await send_button.get_attribute("disabled")
                class_list = await send_button.get_attribute("class") or ""

                if is_disabled or "disabled" in class_list:
                    print("Send button is disabled, trying Enter key instead")
                    await input_element.press("Enter")
                else:
                    # Hover before clicking (human-like behavior)
                    await send_button.hover()
                    await asyncio.sleep(random.uniform(0.1, 0.4))
                    await send_button.click()
                    print("Clicked send button")

            except:
                print("Send button not found, using Enter key")
                await input_element.press("Enter")

            # Wait for potential modal to appear
            await asyncio.sleep(2)

            # Check if modal appeared
            modal_appeared = await self.check_if_modal_appeared()

            if modal_appeared:
                print("Modal appeared after send - handling it...")
                modal_handled = await self.handle_login_modal_after_send()

                if modal_handled:
                    print("Modal handled successfully, trying to send again...")
                    # After closing modal, we need to send again
                    await asyncio.sleep(1)

                    # Try to send again after modal was closed
                    try:
                        send_button = await self.page.wait_for_selector(send_button_selector, timeout=5000)
                        is_disabled = await send_button.get_attribute("disabled")
                        class_list = await send_button.get_attribute("class") or ""

                        if is_disabled or "disabled" in class_list:
                            print("Send button still disabled, trying Enter key")
                            await input_element.press("Enter")
                        else:
                            await send_button.hover()
                            await asyncio.sleep(random.uniform(0.1, 0.4))
                            await send_button.click()
                            print("Clicked send button again after modal")

                    except:
                        print("Trying Enter key after modal")
                        await input_element.press("Enter")

                    # Wait and check if another modal appears
                    await asyncio.sleep(2)
                    second_modal = await self.check_if_modal_appeared()

                    if second_modal:
                        print("Second modal appeared, handling...")
                        await self.handle_login_modal_after_send()
                        return False  # Too many modals, consider this attempt failed
                    else:
                        print("No second modal, message should be sent")
                        return await self.verify_message_sent()
                else:
                    print("Failed to handle modal")
                    return False
            else:
                print("No modal appeared, checking if message was sent")
                return await self.verify_message_sent()

        except Exception as e:
            print(f"Error in send attempt: {e}")
            return False

    async def check_if_modal_appeared(self):
        """Check if the login modal appeared"""
        try:
            modal_selectors = [
                'div:has-text("Welcome")',
                'div:has-text("Login or sign up to chat")',
                'div[class*="bg-white"][class*="p-6"]',
                'button:has-text("Stay logged out")',
            ]

            for selector in modal_selectors:
                try:
                    modal = await self.page.wait_for_selector(selector, timeout=1000)
                    if modal and await modal.is_visible():
                        return True
                except:
                    continue

            return False
        except:
            return False

    async def verify_message_sent(self):
        """Verify that the message was actually sent by checking for response or message in chat"""
        try:
            await asyncio.sleep(2)

            # Check for signs that message was sent
            # Look for response containers or message indicators
            indicators = [
                ".response-meesage-container",  # Response from AI
                ".message-container",  # Message container
                ".chat-message",  # Chat message
                '[class*="message"]',  # Any message class
                ".vlo-image-generating",  # Generation indicator
            ]

            for indicator in indicators:
                try:
                    element = await self.page.wait_for_selector(indicator, timeout=3000)
                    if element and await element.is_visible():
                        print(f"Message appears to be sent - found: {indicator}")
                        return True
                except:
                    continue

            # Alternative: check if send button is enabled again (indicating message was processed)
            try:
                send_button = await self.page.wait_for_selector("button#send-message-button", timeout=2000)
                if send_button:
                    is_disabled = await send_button.get_attribute("disabled")
                    if not is_disabled:
                        print("Send button is enabled again, message likely sent")
                        return True
            except:
                pass

            print("Could not verify message was sent")
            return False

        except Exception as e:
            print(f"Error verifying message sent: {e}")
            return False

    async def handle_login_modal_after_send(self):
        """Specifically handle login modal that appears after clicking send button"""
        try:
            print("Checking for login modal after send button click...")

            # Wait for modal to appear - it should appear within 3 seconds
            await asyncio.sleep(1)

            # More specific selectors for the modal that appears after send
            modal_content_selectors = [
                'div:has-text("Welcome")',
                'div:has-text("Login or sign up to chat")',
                'div[class*="bg-white"][class*="p-6"]',  # The specific modal styling
                'div[class*="dark:bg-[#2A2A2A]"]',
                ".flex.flex-col.bg-white.p-6",
            ]

            modal_found = False
            modal_element = None

            for selector in modal_content_selectors:
                try:
                    modal_element = await self.page.wait_for_selector(selector, timeout=3000)
                    if modal_element and await modal_element.is_visible():
                        # Double-check it contains expected text
                        text_content = await modal_element.text_content()
                        if "Welcome" in text_content or "Login or sign up" in text_content:
                            print(f"Found login modal with selector: {selector}")
                            modal_found = True
                            break
                except Exception as e:
                    continue

            if not modal_found:
                print("No login modal detected")
                return True  # No modal = success

            # Look for "Stay logged out" button with multiple approaches
            stay_logged_out_found = False

            # Approach 1: Text-based selectors
            text_selectors = [
                'button:has-text("Stay logged out")',
                'text="Stay logged out"',
                '//button[contains(text(), "Stay logged out")]',
                '//button[text()="Stay logged out"]',
            ]

            for selector in text_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        button = await self.page.wait_for_selector(f"xpath={selector}", timeout=2000)
                    else:
                        button = await self.page.wait_for_selector(selector, timeout=2000)

                    if button and await button.is_visible():
                        print(f"Found 'Stay logged out' button with selector: {selector}")

                        # Human-like behavior before clicking
                        await button.hover()
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                        await button.click()

                        print("Successfully clicked 'Stay logged out'")
                        stay_logged_out_found = True
                        break

                except Exception as e:
                    continue

            # Approach 2: If text selectors fail, try class-based approach
            if not stay_logged_out_found:
                print("Text selectors failed, trying class-based approach...")

                # Find all buttons in the modal area
                try:
                    buttons = await modal_element.query_selector_all("button")
                    print(f"Found {len(buttons)} buttons in modal")

                    for i, button in enumerate(buttons):
                        button_text = await button.text_content()
                        print(f"Button {i}: '{button_text.strip()}'")

                        if "Stay logged out" in button_text or "logged out" in button_text.lower():
                            print(f"Found stay logged out button by text content")
                            await button.hover()
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                            await button.click()
                            print("Successfully clicked stay logged out button")
                            stay_logged_out_found = True
                            break

                except Exception as e:
                    print(f"Class-based approach failed: {e}")

            # Approach 3: Try clicking the third button (usually "Stay logged out")
            if not stay_logged_out_found:
                print("Trying to click third button (usually 'Stay logged out')...")
                try:
                    buttons = await self.page.query_selector_all("button")
                    if len(buttons) >= 3:
                        # Find buttons that might be in the modal
                        for button in buttons:
                            button_text = await button.text_content()
                            if button_text and ("stay" in button_text.lower() or "logged out" in button_text.lower()):
                                await button.hover()
                                await asyncio.sleep(random.uniform(0.3, 0.8))
                                await button.click()
                                print("Clicked potential stay logged out button")
                                stay_logged_out_found = True
                                break
                except Exception as e:
                    print(f"Third button approach failed: {e}")

            # Approach 4: Press Escape as last resort
            if not stay_logged_out_found:
                print("All approaches failed, trying Escape key...")
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1)

            # Wait for modal to disappear
            await asyncio.sleep(2)

            # Verify modal is gone
            try:
                modal_still_there = await self.page.wait_for_selector('div:has-text("Welcome")', timeout=2000)
                if modal_still_there and await modal_still_there.is_visible():
                    print("Modal still visible after attempts to close")
                    return False
                else:
                    print("Modal successfully dismissed")
                    return True
            except:
                print("Modal appears to be gone")
                return True

        except Exception as e:
            print(f"Error handling login modal: {e}")
            return False

    async def wait_for_generation(self, max_wait_time=20):
        """Wait for image generation to complete"""
        print(f"Waiting up to {max_wait_time} seconds for generation to complete...")

        start_time = time.time()
        last_check_time = start_time

        while time.time() - start_time < max_wait_time:
            current_time = time.time()

            if current_time - last_check_time > 15:
                elapsed = int(current_time - start_time)
                print(f"Still waiting for generation... ({elapsed}s elapsed)")
                last_check_time = current_time

            try:
                response_containers = await self.page.query_selector_all(".response-meesage-container")
                if not response_containers:
                    await asyncio.sleep(3)
                    continue

                latest_response = response_containers[-1]

                loading_indicator = await latest_response.query_selector(".vlo-image-generating")
                is_still_generating = loading_indicator and await loading_indicator.is_visible()

                generated_image = await latest_response.query_selector(".vlo-image-content img")
                is_image_ready = generated_image and await generated_image.is_visible()

                if is_image_ready and not is_still_generating:
                    print("Generation completed! Image is ready.")
                    await asyncio.sleep(3)
                    return True

                elif is_still_generating:
                    print("Generation still in progress...")
                    await asyncio.sleep(5)
                else:
                    print("Ambiguous generation state, waiting...")
                    await asyncio.sleep(3)

            except Exception as e:
                print(f"Error during generation check: {e}")
                await asyncio.sleep(5)

        print(f"Generation timeout reached after {max_wait_time}s")
        return False

    async def download_generated_image(self, original_filename):
        """Download the generated image from the most recent response"""
        try:
            print("Attempting to download generated image from latest response...")

            await asyncio.sleep(2)

            response_containers = await self.page.query_selector_all(".response-meesage-container")
            if not response_containers:
                print("No response containers found")
                return None

            latest_response = response_containers[-1]
            print(f"Found {len(response_containers)} response containers, targeting the latest")

            # Try to get the high-quality image URL directly
            generated_image = await latest_response.query_selector(".vlo-image-content img")

            if generated_image:
                img_src = await generated_image.get_attribute("src")
                if img_src and "cdn.qwenlm.ai/output" in img_src:
                    print(f"Found generated image URL: {img_src[:100]}...")

                    high_quality_url = img_src.split("&x-oss-process=")[0] if "&x-oss-process=" in img_src else img_src
                    print(f"Using high-quality URL: {high_quality_url[:100]}...")

                    downloaded_file = await self.download_image_via_http(high_quality_url, original_filename)
                    if downloaded_file:
                        print("Successfully downloaded via high-quality HTTP")
                        return downloaded_file

            # Try download button approach
            print("Direct download failed, trying download button...")

            try:
                await latest_response.hover()
                await asyncio.sleep(1)
                print("Hovered over latest response to make buttons visible")
            except Exception as e:
                print(f"Could not hover over response: {e}")

            download_button_selectors = [
                'div[aria-label="Загрузить"] button',
                'div[aria-label="Download"] button',
                "button:has(i.icon-line-download-02)",
                ".message-footer-button-item:has(i.icon-line-download-02)",
            ]

            download_button = None
            for selector in download_button_selectors:
                try:
                    download_button = await latest_response.query_selector(selector)
                    if download_button and await download_button.is_visible():
                        print(f"Found download button with selector: {selector}")
                        break
                except Exception as e:
                    continue

            if download_button:
                try:
                    print("Clicking download button...")

                    async with self.page.expect_download(timeout=30000) as download_info:
                        await download_button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)

                        try:
                            await download_button.click()
                            print("Successfully clicked download button")
                        except Exception as click_error:
                            print(f"Regular click failed: {click_error}. Trying force click...")
                            await download_button.click(force=True)

                    download = await download_info.value

                    timestamp = int(time.time())
                    file_extension = Path(original_filename).suffix or ".png"
                    temp_filename = f"downloaded_{timestamp}_{Path(original_filename).stem}{file_extension}"
                    temp_path = Path(tempfile.gettempdir()) / temp_filename

                    await download.save_as(temp_path)
                    print(f"Download completed via button: {temp_filename}")
                    return str(temp_path)

                except Exception as download_error:
                    print(f"Button download failed: {str(download_error)}")

            # Screenshot fallback
            if generated_image:
                try:
                    print("Fallback: Taking screenshot of generated image...")

                    timestamp = int(time.time())
                    file_extension = Path(original_filename).suffix or ".png"
                    temp_filename = f"screenshot_{timestamp}_{Path(original_filename).stem}{file_extension}"
                    temp_path = Path(tempfile.gettempdir()) / temp_filename

                    await generated_image.scroll_into_view_if_needed()
                    await asyncio.sleep(1)

                    await generated_image.screenshot(path=temp_path)
                    print(f"Screenshot completed: {temp_filename}")
                    return str(temp_path)

                except Exception as e:
                    print(f"Screenshot failed: {e}")

            print("All download methods failed")
            return None

        except Exception as e:
            print(f"Critical error in download process: {str(e)}")
            import traceback

            traceback.print_exc()
            return None

    async def download_image_via_http(self, img_url, original_filename):
        """Download image using HTTP request with session cookies"""
        try:
            print("Downloading via HTTP request...")

            cookies = await self.page.context.cookies()
            cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}

            # Enhanced headers to look more human-like
            headers = {
                "User-Agent": await self.page.evaluate("navigator.userAgent"),
                "Referer": self.page.url,
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,uk;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }

            timeout = aiohttp.ClientTimeout(total=60)

            async with aiohttp.ClientSession(
                cookies=cookie_dict,
                headers=headers,
                timeout=timeout,
            ) as session:
                # Add small delay to simulate human behavior
                await asyncio.sleep(random.uniform(0.5, 1.5))

                async with session.get(img_url) as response:
                    if response.status == 200:
                        content = await response.read()

                        if len(content) < 1000:
                            print(f"Downloaded file is too small ({len(content)} bytes), likely an error page")
                            return None

                        timestamp = int(time.time())
                        file_extension = Path(original_filename).suffix or ".png"
                        temp_filename = f"http_download_{timestamp}_{Path(original_filename).stem}{file_extension}"
                        temp_path = Path(tempfile.gettempdir()) / temp_filename

                        async with aiofiles.open(temp_path, "wb") as f:
                            await f.write(content)

                        print(f"HTTP download successful: {temp_filename} ({len(content)} bytes)")
                        return str(temp_path)
                    else:
                        print(f"HTTP download failed with status: {response.status}")
                        return None

        except Exception as e:
            print(f"HTTP download error: {str(e)}")
            return None

    async def process_single_image(self, image_path, brand_output_folder):
        """Process a single image through the watermark removal pipeline"""
        try:
            print(f"Starting pipeline for: {image_path.name}")

            if not await self.upload_image_to_qwen(image_path):
                print("Failed at upload step")
                return False

            await asyncio.sleep(3)
            # Use the new method that handles modal after send
            if not await self.send_prompt_with_modal_handling("Delete watermark"):
                print("Failed at prompt step")
                return False

            await asyncio.sleep(5)
            generation_success = await self.wait_for_generation(max_wait_time=20)
            if not generation_success:
                print("Generation may not be complete, but continuing...")

            # Check for any login modal before download
            print("Checking for any login modal before download...")
            await self.handle_login_modal()

            downloaded_file = await self.download_generated_image(image_path.name)
            if not downloaded_file:
                print("Failed at download step")
                return False

            final_path = brand_output_folder / image_path.name

            counter = 1
            original_stem = image_path.stem
            original_suffix = image_path.suffix

            while final_path.exists():
                final_path = brand_output_folder / f"{original_stem}_{counter}{original_suffix}"
                counter += 1

            shutil.move(downloaded_file, final_path)
            print(f"Saved to: {final_path}")

            return True

        except Exception as e:
            print(f"Error processing {image_path.name}: {str(e)}")
            return False

    async def cleanup_browser(self):
        """Clean up browser resources"""
        try:
            if hasattr(self, "browser") and self.browser:
                await self.browser.close()
            if hasattr(self, "playwright") and self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def get_all_images_to_process(self):
        """Get all images that need to be processed"""
        all_images = []

        if not self.images_folder.exists():
            print(f"Images folder not found: {self.images_folder}")
            return []

        brand_folders = [f for f in self.images_folder.iterdir() if f.is_dir()]

        if not brand_folders:
            print("No brand folders found in images directory")
            return []

        for brand_folder in brand_folders:
            brand_output = self.output_folder / brand_folder.name
            brand_output.mkdir(parents=True, exist_ok=True)

            image_files = [
                f for f in brand_folder.iterdir() if f.is_file() and f.suffix.lower() in self.supported_formats
            ]

            for image_file in image_files:
                output_file = brand_output / image_file.name
                if not output_file.exists():
                    all_images.append((image_file, brand_output))

        return all_images

    async def process_batch_with_proxy(self, images_batch, proxy_config):
        """Process a batch of images using a specific proxy"""
        print(f"\n{'='*60}")
        print(f"Starting batch with {self.proxy_manager.get_current_proxy_info()}")
        print(f"Processing {len(images_batch)} images")
        print(f"{'='*60}")

        # Setup browser with proxy
        if not await self.setup_browser_with_proxy(proxy_config):
            print(f"Failed to setup browser with proxy")
            return 0

        # Handle authentication
        if not await self.handle_authentication():
            print("Authentication failed - skipping this proxy")
            await self.cleanup_browser()
            return 0

        processed_count = 0

        try:
            for i, (image_path, brand_output_folder) in enumerate(images_batch, 1):
                print(f"\n[{i}/{len(images_batch)}] Processing: {image_path.name}")
                print(f"Brand folder: {brand_output_folder}")

                success = await self.process_single_image(image_path, brand_output_folder)

                if success:
                    processed_count += 1
                    print(f"Successfully processed: {image_path.name}")
                else:
                    print(f"Failed to process: {image_path.name}")

                # Pause between images with human-like variation
                if i < len(images_batch):
                    print("Pausing before next image...")
                    # Random pause between 3-8 seconds to simulate human behavior
                    pause_time = random.uniform(3, 8)
                    await asyncio.sleep(pause_time)

        except Exception as e:
            print(f"Error during batch processing: {e}")
            import traceback

            traceback.print_exc()

        finally:
            print(f"Closing browser for this proxy session...")
            await self.cleanup_browser()

        print(f"Batch completed: {processed_count}/{len(images_batch)} images processed")
        return processed_count

    async def process_all_images(self):
        """Process all images using proxy rotation"""
        if not self.images_folder.exists():
            print(f"Images folder not found: {self.images_folder}")
            return

        self.output_folder.mkdir(exist_ok=True)
        print(f"Output folder created/verified: {self.output_folder}")

        # Get all images to process
        all_images = self.get_all_images_to_process()

        if not all_images:
            print("No images to process")
            return

        print(f"Found {len(all_images)} images to process")

        total_processed = 0
        total_failed = 0

        # Process images in batches
        while all_images:
            # Get next batch
            current_batch = all_images[: self.batch_size]
            all_images = all_images[self.batch_size :]

            # Get next proxy
            proxy_config = self.proxy_manager.get_next_proxy()

            # Process batch with current proxy
            batch_processed = 0
            max_retries = 3

            for retry in range(max_retries):
                try:
                    batch_processed = await self.process_batch_with_proxy(current_batch, proxy_config)
                    break  # Success, exit retry loop

                except Exception as e:
                    print(f"Batch failed with proxy (attempt {retry + 1}/{max_retries}): {e}")

                    if retry < max_retries - 1:
                        print("Trying with next proxy...")
                        proxy_config = self.proxy_manager.get_next_proxy()
                        await asyncio.sleep(5)
                    else:
                        print("All retry attempts failed for this batch")

            total_processed += batch_processed
            total_failed += len(current_batch) - batch_processed

            print(f"\nProgress: {total_processed} processed, {total_failed} failed, {len(all_images)} remaining")

            # Pause between proxy sessions
            if all_images:  # If there are more images to process
                print("Pausing before next proxy session...")
                await asyncio.sleep(10)

        print(f"\n Processing complete!")
        print(f"Total images processed successfully: {total_processed}")
        print(f"Total images failed: {total_failed}")


def create_cookies_file_with_real_data():
    """Create cookies file with your real authentication data"""
    real_cookies = [
        {
            "domain": ".qwen.ai",
            "expiry": 1756378384,
            "httpOnly": False,
            "name": "ssxmod_itna2",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "YqUxBD0Du7T49D4qeqY5q7jo0jYiQDRiiDl4BtGRlDIqe7=GFKDCrOz8DmC+DAI5PeznwipzYKjqD=mDDPEwmWKe03Bfi=8obm3gpWbzV4tnGRweSf/d4xD",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1771928580,
            "httpOnly": False,
            "name": "isg",
            "path": "/",
            "sameSite": "None",
            "secure": True,
            "value": "BKKiFyG4Pk2mYCKFRG6wavKr8y4E86YNQMmcm-w7zpXBv0I51IP2HSi96uND_h6l",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1771928580,
            "httpOnly": False,
            "name": "tfstk",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "gI--WU6umxe8n6NzeB00Kg6QAfHDeqvrGQJ_x6fuRIdvOQMzxp_uOkdAiYJlVbRYG9BBr6MUVkKACBe5OL1CJ-6hMWNSa2-xcCdFFUbS8-ZfET6B9pkPd6OB96YoocvyUMSIsgnijLJAJmGp2MNHhgWHYMDtucvyU-agM0tijJp1MGW5OB_5GZ6NGTw7ABsfGTfbV9Z5dSMALssQP_ZCGt6NdkaBOMMvhsWCATOCPxpfg9sCOfe306uCskL-Hg4-fAX7AktAeanMFsZC3nBRy195PkZBQTQR1L1jNi_ThwdRynm8_TLXBQXJTcrPVwLW5gtK60IXQEA5HBGTJsT94HQM2fUNN35e6gTxGuICq3LG7M3TUtxJhh7p4bEfwIJXSg-sgkd6ndxPuHhTG68lQi6JkvafNwszdhx9OfPG694SHxUU8a6V6aMPJcYEWjXAsxA78y7Y7tCiH4zU8a6VH1D0kyzFkFC..",
        },
        {
            "domain": "chat.qwen.ai",
            "expiry": 1756981380,
            "httpOnly": True,
            "name": "token",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjVkNmVmYzg0LTUxMTQtNGFlYi04ZWFhLWExZTg3YzQ3YTU0OSIsImxhc3RfcGFzc3dvcmRfY2hhbmdlIjoxNzU1ODU4MTk4LCJleHAiOjE3NTY5ODEzODB9.ZiJdo-sqTKM_YRg7Nc-FEh4aFAJGVCmcCnVr7-pIhb4",
        },
        {
            "domain": ".qwen.ai",
            "httpOnly": False,
            "name": "atpsida",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "7393dbadb42aa86b56da1519_1756376581_1",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1756378384,
            "httpOnly": False,
            "name": "ssxmod_itna",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "YqUxBD0Du7T49D4qeqY5q7jo0jYiQDRiiDl4BtGRlDIqe7=GFKDCrOz8DmC+DAI5PeznwipzYKjqD=MD0ymzmDY5GSGxi3Dar4KUbTziDrNATzFARm1m5nlbMoQznlD+IQ88Xjby=z3Xoq4wmmDAEY0DGmD0=DAqPD7k5cDYYDC4GwDGoD34DiDDP3xDUrhePD72udylu4rE2YGnuLiOriirfCxivadZWNdWxNxD3EDB=au82aKPPQDY6=GKPileDLR1PANzrDbEoQN/7Dtq7K27IiocWWlIePjdzb32xbSgXoQA4pFBxIKG/WilziPiGxYrV4w/0rbWTo3xTY9tAHPa47YhB3ygFWSYx4grzeE13riK0qKuqQirYntlxiebNQGbt4xUHPf0VY0DSrbfHPeD",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1790936581,
            "httpOnly": False,
            "name": "cnaui",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "5d6efc84-5114-4aeb-8eaa-a1e87c47a549",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1756635781,
            "httpOnly": False,
            "name": "xlly_s",
            "path": "/",
            "sameSite": "None",
            "secure": True,
            "value": "1",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1790936581,
            "httpOnly": False,
            "name": "cna",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "xUYrIeIptzgCAS7wu5GwY2oh",
        },
        {
            "domain": "chat.qwen.ai",
            "expiry": 1771928579,
            "httpOnly": False,
            "name": "_bl_uid",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "0pms0eX1v7g9019b6msnjnXoeggI",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1764152579,
            "httpOnly": False,
            "name": "_gcl_au",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "1.1.124207464.1756376579",
        },
        {
            "domain": ".qwen.ai",
            "expiry": 1790936582,
            "httpOnly": False,
            "name": "aui",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "5d6efc84-5114-4aeb-8eaa-a1e87c47a549",
        },
        {
            "domain": ".qwen.ai",
            "httpOnly": False,
            "name": "sca",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "f0b02a33",
        },
        {
            "domain": "chat.qwen.ai",
            "httpOnly": False,
            "name": "x-ap",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "eu-central-1",
        },
        {
            "domain": "chat.qwen.ai",
            "expiry": 1756378379,
            "httpOnly": True,
            "name": "acw_tc",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": "0a03e54a17563765791615117e1e8ff31d14874c348ebd9aaded2e2c2eb4aa",
        },
    ]

    with open("qwen_cookies_real.json", "w") as f:
        json.dump(real_cookies, f, indent=2)

    print("Created qwen_cookies_real.json with your authentication data")
    print("This should significantly reduce login modal appearances")
    """Create example proxies.txt file"""
    example_content = """# Proxy format: host:port:username:password
# Example:
# 104.252.196.79:5987:vytbwqwe:xkcasp8b9ye0
# 107.173.93.68:6022:vytbwqwe:xkcasp8b9ye0

# Add your proxies below:
"""

    with open("proxies.txt", "w") as f:
        f.write(example_content)

    print("Created proxies.txt file. Please add your proxy list to this file.")


async def main():
    """Main function"""
    print("Starting Watermark Removal Automation with Proxy Support")
    print("=" * 70)

    IMAGES_FOLDER = "images2"
    OUTPUT_FOLDER = "no_watermarks"
    BATCH_SIZE = 5  # Images per proxy session

    print(f"Input folder: {IMAGES_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"Batch size: {BATCH_SIZE} images per proxy")
    print(f"Target URL: https://chat.qwen.ai/?inputFeature=image_edit")

    remover = WatermarkRemover(images_folder=IMAGES_FOLDER, output_folder=OUTPUT_FOLDER, batch_size=BATCH_SIZE)

    await remover.process_all_images()


if __name__ == "__main__":
    import sys

    try:
        print("Script started...")

        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            print(f"Running command: {command}")

            if command == "setup":
                print("Creating folder structure and proxy file...")
                # create_folder_structure()
                # create_proxies_file()
            elif command == "help":
                print("Watermark Remover with Proxy Support Commands:")
                print("  python script.py           - Run full processing with proxy rotation")
                print("  python script.py setup     - Create folder structure and proxy file")
                print("  python script.py help      - Show this help")
            else:
                print(f"Unknown command: {command}")
                print("Use 'python script.py help' for available commands")
        else:
            # Check prerequisites
            if not Path("images2").exists():
                print("Images folder not found!")
                print("Creating folder structure first...")
                # create_folder_structure()
                # print("Folder structure created. Please add your images and run again.")
            elif not Path("proxies.txt").exists():
                print("Proxy file not found!")
                # create_proxies_file()
                print("Proxy file created. Please add your proxies and run again.")
            else:
                asyncio.run(main())

    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        print("Script finished")
