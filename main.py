from selenium import webdriver
from selenium.webdriver.common.by import By
import pyautogui
import time


def setup_driver():
    driver = webdriver.Chrome()
    driver.get("https://clock.zone/")

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
    }

    setupObserver();
    """

    driver.execute_script(js_code)
    return driver


def time_matches_pattern(current_time, pattern):
    return all(c == p or p == 'X' for c, p in zip(current_time, pattern))


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


def main():
    driver = setup_driver()
    try:
        last_click_second = None
        interval = 0.001  # 1ms interval for high precision checking
        next_check = time.perf_counter() + interval

        while True:
            current = time.perf_counter()
            if current >= next_check:
                time_parts = get_current_time(driver)
                if time_parts:
                    h, m, s, ms = time_parts
                    if should_click(h, m, s, ms, "XX", "XX", "X5", "XX"):
                        if s != last_click_second:
                            pyautogui.click()
                            print(f"Clicked at {h}:{m}:{s}:{ms}")
                            last_click_second = s

                next_check = current + interval

            # Busy-wait for the remaining time because we need to ensure we control the CPU cycle
            while time.perf_counter() < next_check:
                pass

    except KeyboardInterrupt:
        print("Script stopped by user")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
    # Keep the console window open
    input("Press Enter to exit...")
