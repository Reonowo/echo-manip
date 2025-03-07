import json
import os
import shutil
import tkinter as tk
from datetime import datetime
from tkinter import ttk
import threading
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui
import time
import keyboard
from PIL import ImageDraw, ImageFont


def setup_logging():
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Archive old logs
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists('logs/app.log'):
        shutil.move('logs/app.log', f'logs/app_{current_time}.log')

    return open('logs/app.log', 'w')


log_file = setup_logging()


def log_with_timestamp(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    log_file.write(log_message + '\n')
    log_file.flush()


def load_config():
    default_config = {
        "keybinds": {
            "toggle_clicking": "f13",
            "toggle_screenshots": "f14",
            "quit": "f16"
        },
        "time_patterns": {
            "hour": "XX",
            "minute": "X7",
            "second": ["00", "15", "30"],
            "millisecond": "50"
        },
        "window": {
            "title": "Echo Manipulator",
            "size": "300x200"
        },
        "screenshot": {
            "width": 940,
            "height": 735,
            "delay": 2.0  # Default 2 seconds delay
        }
    }

    try:
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        # Ensure all expected keys are present
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in config[key]:
                        config[key][sub_key] = sub_value

        # Make sure all screenshot dimensions are integers and delay is float
        config['screenshot']['width'] = int(config['screenshot']['width'])
        config['screenshot']['height'] = int(config['screenshot']['height'])
        config['screenshot']['delay'] = float(config['screenshot']['delay'])

        # Write back the potentially updated config
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)

    except FileNotFoundError:
        log_with_timestamp("Config file not found. Creating default config.")
        config = default_config
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)

    return config


def setup_driver():
    log_with_timestamp("Starting setup_driver function")

    chrome_options = Options()
    chrome_options.add_argument("--log-level=3")
    chrome_options.page_load_strategy = 'eager'
    log_with_timestamp("Chrome options set")

    service = Service(ChromeDriverManager().install())
    log_with_timestamp("ChromeDriver service created")

    driver = webdriver.Chrome(service=service, options=chrome_options)
    log_with_timestamp("WebDriver initialized")

    log_with_timestamp("Navigating to https://clock.zone/")
    driver.get("https://clock.zone/")
    log_with_timestamp("Navigation complete")

    js_code = """
    function onTimeChange(hours, minutes, seconds, milliseconds) {
        document.body.setAttribute('data-current-time', `${hours}:${minutes}:${seconds}:${milliseconds}`);
    }

    function setupObserver() {
        const clockElement = document.getElementById('MyClockDisplay');
        if (!clockElement) {
            console.log('Clock element not found. Retrying in 1 second...');
            setTimeout(setupObserver, 1000);
            return;
        }

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' || mutation.type === 'characterData') {
                    const hours = document.getElementById('hh').textContent;
                    const minutes = document.getElementById('mm').textContent;
                    const seconds = document.getElementById('ss').textContent;
                    const milliseconds = document.getElementById('ms').textContent;
                    onTimeChange(hours, minutes, seconds, milliseconds);
                }
            });
        });

        const config = { childList: true, characterData: true, subtree: true };
        observer.observe(clockElement, config);
        console.log('Observer set up successfully!');

        document.body.setAttribute('data-observer-ready', 'true');
    }

    setupObserver();
    """

    driver.execute_script(js_code)
    log_with_timestamp("JavaScript code execution complete")

    return driver


def time_matches_pattern(current_time, pattern):
    if isinstance(pattern, str):
        return current_time == pattern or pattern == 'XX' or (
                pattern.startswith('X') and current_time.endswith(pattern[1:]))
    elif isinstance(pattern, list):
        return current_time in pattern
    return False


def get_current_time(driver):
    current_time = driver.find_element(By.TAG_NAME, "body").get_attribute("data-current-time")
    if current_time:
        return current_time.split(':')
    return None


def should_click(h, m, s, ms, h_pattern, m_pattern, s_pattern, ms_pattern):
    return (time_matches_pattern(h, h_pattern) and
            time_matches_pattern(m, m_pattern) and
            time_matches_pattern(s, s_pattern) and
            time_matches_pattern(ms, ms_pattern))


def wait_for_observer(driver):
    log_with_timestamp("Waiting for observer to be ready")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body[data-observer-ready='true']"))
    )
    log_with_timestamp("Observer setup complete. Clock monitoring has started.")


class AutoClickerApp:
    def __init__(self, master, driver):
        self.master = master
        self.driver = driver
        self.config = load_config()
        self.apply_config()

        self.clicking_enabled = tk.BooleanVar()
        self.clicking_enabled.set(False)
        self.screenshot_enabled = tk.BooleanVar()
        self.screenshot_enabled.set(False)

        self.enable_button = ttk.Checkbutton(master, text="Enable Clicking", variable=self.clicking_enabled)
        self.enable_button.pack(pady=5)

        self.screenshot_button = ttk.Checkbutton(master, text="Enable Screenshots", variable=self.screenshot_enabled)
        self.screenshot_button.pack(pady=5)

        self.last_click_label = ttk.Label(master, text="Last Click: N/A")
        self.last_click_label.pack(pady=5)

        self.time_pattern_label = ttk.Label(master, text=self.get_time_pattern_text())
        self.time_pattern_label.pack(pady=5)

        self.reload_button = ttk.Button(master, text="Reload Config", command=self.reload_config)
        self.reload_button.pack(pady=5)

        self.quit_button = ttk.Button(master, text="Quit", command=self.quit)
        self.quit_button.pack(pady=5)

        self.setup_hotkeys()

        self.running = True

    def apply_config(self):
        window_config = self.config['window']
        self.master.title(window_config['title'])
        self.master.geometry(window_config['size'])

    def setup_hotkeys(self):
        keybinds = self.config['keybinds']
        keyboard.add_hotkey(keybinds['toggle_clicking'], self.toggle_clicking)
        keyboard.add_hotkey(keybinds['toggle_screenshots'], self.toggle_screenshots)
        keyboard.add_hotkey(keybinds['quit'], self.quit)

    def get_time_pattern_text(self):
        patterns = self.config['time_patterns']
        return f"Time Pattern: {patterns['hour']}:{patterns['minute']}:{patterns['second']}:{patterns['millisecond']}"

    def reload_config(self):
        keyboard.unhook_all()
        self.config = load_config()
        self.apply_config()
        self.setup_hotkeys()
        self.time_pattern_label.config(text=self.get_time_pattern_text())
        log_with_timestamp("Config reloaded")

    def update_last_click(self, time):
        self.last_click_label.config(text=f"Last Click: {time}")

    def toggle_clicking(self):
        self.clicking_enabled.set(not self.clicking_enabled.get())
        log_with_timestamp(f"Clicking {'enabled' if self.clicking_enabled.get() else 'disabled'}")

    def toggle_screenshots(self):
        self.screenshot_enabled.set(not self.screenshot_enabled.get())
        log_with_timestamp(f"Screenshots {'enabled' if self.screenshot_enabled.get() else 'disabled'}")

    def quit(self):
        self.running = False
        self.master.after(100, self.master.quit)

    def take_screenshot(self, click_time):
        def delayed_screenshot():
            delay = float(self.config['screenshot']['delay'])
            time.sleep(delay)
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
            screenshot_config = self.config['screenshot']
            width = int(screenshot_config['width'])
            height = int(screenshot_config['height'])
            screen_width, screen_height = pyautogui.size()
            left = (screen_width - width) // 2
            top = (screen_height - height) // 2
            screenshot = pyautogui.screenshot(region=(left, top, width, height))

            # Create a drawing object
            draw = ImageDraw.Draw(screenshot)

            # Set up the font
            try:
                font = ImageFont.truetype("arial.ttf", 32)
            except IOError:
                print("Arial font not found. Using default font.")
                font = ImageFont.load_default()

            # Prepare the text
            time_pattern = self.get_time_pattern_text().split(": ")[1]  # Get just the pattern part
            text = f"Click at {click_time} with pattern {time_pattern}"

            # Get text size
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top

            # Calculate position (bottom right corner)
            text_position = (width - text_width - 10, height - text_height - 10)

            # Draw text with black border
            border_color = (0, 0, 0)  # Black
            text_color = (255, 255, 255)  # White

            # Draw border
            for offset in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                draw.text((text_position[0] + offset[0], text_position[1] + offset[1]), text, font=font,
                          fill=border_color)

            # Draw main text
            draw.text(text_position, text, font=font, fill=text_color)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot.save(f'screenshots/screenshot_{timestamp}.png')
            log_with_timestamp(f"Screenshot saved: screenshot_{timestamp}.png (for click at {click_time})")

        screenshot_thread = threading.Thread(target=delayed_screenshot)
        screenshot_thread.start()


def main():
    log_with_timestamp("Starting main function")
    driver = setup_driver()

    root = tk.Tk()
    app = AutoClickerApp(root, driver)

    try:
        wait_for_observer(driver)

        last_click_second = None
        interval = 0.001  # 1ms interval for high precision checking
        next_check = time.perf_counter() + interval

        log_with_timestamp("Entering main loop")

        def clicker_loop():
            nonlocal last_click_second, next_check
            while app.running:
                if app.clicking_enabled.get() or app.screenshot_enabled.get():
                    current = time.perf_counter()
                    if current >= next_check:
                        try:
                            time_parts = get_current_time(driver)
                            if time_parts:
                                h, m, s, ms = time_parts
                                patterns = app.config['time_patterns']
                                if app.clicking_enabled.get() and should_click(h, m, s, ms, patterns['hour'],
                                                                               patterns['minute'], patterns['second'],
                                                                               patterns['millisecond']):
                                    if s != last_click_second:
                                        pyautogui.click()
                                        click_time = f"{h}:{m}:{s}:{ms}"
                                        log_with_timestamp(f"Clicked at {click_time}")
                                        app.update_last_click(click_time)
                                        if app.screenshot_enabled.get():
                                            app.take_screenshot(click_time)
                                        last_click_second = s
                        except Exception as e:
                            if app.running:
                                log_with_timestamp(f"Error in clicker loop: {e}")
                            break

                        next_check = current + interval

                    while time.perf_counter() < next_check and app.running:
                        pass
                else:
                    # If both clicking and screenshots are disabled, sleep to reduce CPU usage
                    # This does have the caveat of not being able to "respond immediately" but eh.
                    time.sleep(0.1)

            log_with_timestamp("Clicker loop ended")

        clicker_thread = threading.Thread(target=clicker_loop, daemon=True)
        clicker_thread.start()

        root.mainloop()

    except Exception as e:
        log_with_timestamp(f"An error occurred: {e}")
    finally:
        app.running = False
        time.sleep(0.2)
        driver.quit()
        log_with_timestamp("Driver quit")
        log_file.close()


if __name__ == "__main__":
    main()
