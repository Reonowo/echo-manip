from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui
import time


def log_with_timestamp(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def setup_driver():
    log_with_timestamp("Starting setup_driver function")

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.page_load_strategy = 'eager'  # Don't wait for all resources to download
    chrome_options.add_argument("--log-level=3")  # Only show fatal errors
    log_with_timestamp("Chrome options set")

    # Use webdriver_manager to automatically download and use the correct ChromeDriver version
    service = Service(ChromeDriverManager().install())
    log_with_timestamp("ChromeDriver service created")

    # Initialize the driver
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
        console.log('Attempting to set up observer');
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

        // Notify Python that the observer is set up
        document.body.setAttribute('data-observer-ready', 'true');
    }

    // Attempt to set up the observer immediately
    setupObserver();

    // If it fails, retry every second
    const retryInterval = setInterval(() => {
        if (!document.body.hasAttribute('data-observer-ready')) {
            console.log('Retrying observer setup...');
            setupObserver();
        } else {
            clearInterval(retryInterval);
        }
    }, 1000);
    """

    log_with_timestamp("Executing JavaScript code")
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


def main():
    log_with_timestamp("Starting main function")
    driver = setup_driver()

    try:
        wait_for_observer(driver)

        last_click_second = None
        interval = 0.001  # 1ms interval for high precision checking
        next_check = time.perf_counter() + interval

        # Define your click pattern here
        hour_pattern = "XX"
        minute_pattern = "XX"
        second_pattern = ["15", "30", "45"]
        millisecond_pattern = "XX"

        log_with_timestamp("Entering main loop")
        while True:
            current = time.perf_counter()
            if current >= next_check:
                time_parts = get_current_time(driver)
                if time_parts:
                    h, m, s, ms = time_parts
                    if should_click(h, m, s, ms, hour_pattern, minute_pattern, second_pattern, millisecond_pattern):
                        if s != last_click_second:
                            pyautogui.click()
                            log_with_timestamp(f"Clicked at {h}:{m}:{s}:{ms}")
                            last_click_second = s

                next_check = current + interval

            # Busy-wait for the remaining time
            while time.perf_counter() < next_check:
                pass

    except KeyboardInterrupt:
        log_with_timestamp("Script stopped by user")
    finally:
        driver.quit()
        log_with_timestamp("Driver quit")


if __name__ == "__main__":
    main()
    # Keep the console window open
    input("Press Enter to exit...")
