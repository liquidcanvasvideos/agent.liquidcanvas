import os
import time
import shutil
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _get_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _build_chrome_options() -> Options:
    options = Options()

    headless = _get_bool_env("SOCIAL_SELENIUM_HEADLESS", True)
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=Translate,BackForwardCache,AcceptCHFrame")
    options.add_argument("--window-size=1280,900")

    user_data_dir = os.getenv("SOCIAL_SELENIUM_USER_DATA_DIR")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    profile_dir = os.getenv("SOCIAL_SELENIUM_PROFILE_DIR")
    if profile_dir:
        options.add_argument(f"--profile-directory={profile_dir}")

    chrome_binary = os.getenv("SOCIAL_SELENIUM_CHROME_BINARY")
    if not chrome_binary:
        chrome_binary = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
            or shutil.which("chrome")
        )
    if chrome_binary:
        options.binary_location = chrome_binary

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


def _create_driver() -> webdriver.Chrome:
    options = _build_chrome_options()

    chromedriver_path = os.getenv("SOCIAL_SELENIUM_CHROMEDRIVER")
    if not chromedriver_path:
        chromedriver_path = shutil.which("chromedriver")
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    page_load_timeout = int(os.getenv("SOCIAL_SELENIUM_PAGELOAD_TIMEOUT_SECONDS", "60"))
    script_timeout = int(os.getenv("SOCIAL_SELENIUM_SCRIPT_TIMEOUT_SECONDS", "60"))
    if page_load_timeout > 0:
        driver.set_page_load_timeout(page_load_timeout)
    if script_timeout > 0:
        driver.set_script_timeout(script_timeout)

    return driver


def _safe_get(driver: webdriver.Chrome, url: str) -> None:
    try:
        driver.get(url)
    except TimeoutException as e:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
        raise TimeoutException(f"Timeout loading page: {url}") from e


def _ensure_not_logged_out(driver: webdriver.Chrome, platform: str) -> None:
    try:
        current = (driver.current_url or "").lower()
    except Exception:
        return

    if platform == "instagram":
        if "accounts/login" in current or "/challenge" in current:
            raise RuntimeError(
                "Instagram requires login/checkpoint in Selenium session. Configure SOCIAL_SELENIUM_USER_DATA_DIR/profile or login cookies."
            )
    if platform == "facebook":
        if "login" in current or "checkpoint" in current:
            raise RuntimeError(
                "Facebook requires login/checkpoint in Selenium session. Configure SOCIAL_SELENIUM_USER_DATA_DIR/profile or login cookies."
            )
    if platform == "tiktok":
        if "login" in current:
            raise RuntimeError(
                "TikTok requires login in Selenium session. Configure SOCIAL_SELENIUM_USER_DATA_DIR/profile or login cookies."
            )


def _wait_click_any(driver: webdriver.Chrome, xpaths: list[str], timeout: int = 20) -> None:
    last_err: Optional[Exception] = None
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            el.click()
            return
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("No clickable element found")


def _wait_present_any(driver: webdriver.Chrome, selectors: list[tuple[str, str]], timeout: int = 20):
    last_err: Optional[Exception] = None
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
            return el
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("No element found")


def _normalize_url(platform: str, profile: Any) -> str:
    url = getattr(profile, "profile_url", None) or ""
    username = getattr(profile, "username", "") or ""

    if url:
        return url

    platform_lower = (platform or "").lower()
    if platform_lower == "instagram" and username:
        return f"https://www.instagram.com/{username}/"
    if platform_lower == "tiktok" and username:
        if username.startswith("@"):
            username = username[1:]
        return f"https://www.tiktok.com/@{username}"
    if platform_lower == "facebook" and username:
        return f"https://www.facebook.com/{username}"

    return ""


def send_instagram_dm(profile: Any, message: str) -> Dict[str, Any]:
    dry_run = _get_bool_env("SOCIAL_SEND_DRY_RUN", False)

    driver = _create_driver()
    try:
        url = _normalize_url("instagram", profile)
        if not url:
            return {"success": False, "error": "Missing Instagram profile URL/username"}

        _safe_get(driver, url)
        _ensure_not_logged_out(driver, "instagram")

        if dry_run:
            return {"success": True, "sent_body": message, "thread_id": f"ig_{getattr(profile, 'id', 'unknown')}"}

        _wait_click_any(
            driver,
            [
                "//div[@role='button' and .//div[normalize-space()='Message']]",
                "//a[contains(@href, '/direct/t/') and normalize-space()='Message']",
                "//button[.//div[normalize-space()='Message']]",
                "//div[normalize-space()='Message' and @role='button']",
            ],
            timeout=25,
        )

        input_el = _wait_present_any(
            driver,
            [
                (By.XPATH, "//div[@role='textbox']"),
                (By.XPATH, "//textarea"),
            ],
            timeout=25,
        )

        input_el.click()
        input_el.send_keys(message)
        input_el.send_keys(Keys.ENTER)

        time.sleep(2)

        return {"success": True, "sent_body": message, "thread_id": f"ig_{getattr(profile, 'id', 'unknown')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def send_facebook_message(profile: Any, message: str) -> Dict[str, Any]:
    dry_run = _get_bool_env("SOCIAL_SEND_DRY_RUN", False)

    driver = _create_driver()
    try:
        url = _normalize_url("facebook", profile)
        if not url:
            return {"success": False, "error": "Missing Facebook profile URL/username"}

        _safe_get(driver, url)
        _ensure_not_logged_out(driver, "facebook")

        if dry_run:
            return {"success": True, "sent_body": message, "thread_id": f"fb_{getattr(profile, 'id', 'unknown')}"}

        _wait_click_any(
            driver,
            [
                "//div[@role='button' and .//*[contains(normalize-space(), 'Message')]]",
                "//a[@role='link' and .//*[contains(normalize-space(), 'Message')]]",
                "//span[contains(normalize-space(), 'Message')]/ancestor::div[@role='button'][1]",
            ],
            timeout=25,
        )

        input_el = _wait_present_any(
            driver,
            [
                (By.XPATH, "//div[@role='textbox']"),
                (By.XPATH, "//textarea"),
            ],
            timeout=25,
        )

        input_el.click()
        input_el.send_keys(message)
        input_el.send_keys(Keys.ENTER)

        time.sleep(2)

        return {"success": True, "sent_body": message, "thread_id": f"fb_{getattr(profile, 'id', 'unknown')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def send_tiktok_dm(profile: Any, message: str) -> Dict[str, Any]:
    dry_run = _get_bool_env("SOCIAL_SEND_DRY_RUN", False)

    driver = _create_driver()
    try:
        url = _normalize_url("tiktok", profile)
        if not url:
            return {"success": False, "error": "Missing TikTok profile URL/username"}

        _safe_get(driver, url)
        _ensure_not_logged_out(driver, "tiktok")

        if dry_run:
            return {"success": True, "sent_body": message, "thread_id": f"tt_{getattr(profile, 'id', 'unknown')}"}

        _wait_click_any(
            driver,
            [
                "//button[.//*[contains(normalize-space(), 'Message')]]",
                "//div[@role='button' and .//*[contains(normalize-space(), 'Message')]]",
            ],
            timeout=25,
        )

        input_el = _wait_present_any(
            driver,
            [
                (By.XPATH, "//div[@role='textbox']"),
                (By.XPATH, "//textarea"),
            ],
            timeout=25,
        )

        input_el.click()
        input_el.send_keys(message)
        input_el.send_keys(Keys.ENTER)

        time.sleep(2)

        return {"success": True, "sent_body": message, "thread_id": f"tt_{getattr(profile, 'id', 'unknown')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            driver.quit()
        except Exception:
            pass
