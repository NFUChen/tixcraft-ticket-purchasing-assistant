import datetime
import os
from typing import Optional

from loguru import logger
from src.commons.selenium_driver_service import (
    WebDriver,
    expected_conditions,
    WebDriverWait,
    WebElement,
    Select,
    Alert,
    By,
)
from src.commons.selenium_driver_service import (
    SeleniumNoAlertPresentException,
    SeleniumUnexpectedAlertPresentException,
    SeleniumNoSuchElementException,
)


def is_element_exists_by(driver: WebDriver, by: str, searched_element: str) -> bool:
    try:
        driver.find_element(by, searched_element)
    except SeleniumNoSuchElementException:
        return False
    return True


def element_wait_until_clickable(
    driver: WebDriver,
    max_wait_n_seconds: float,
    by: str,
    element_name_clicked: str,
) -> None:
    WebDriverWait(driver, max_wait_n_seconds).until(
        expected_conditions.element_to_be_clickable((by, element_name_clicked))
    )


def select_by_visible_text(element: WebElement, text: str) -> None:
    Select(element).select_by_visible_text(text)


def alert_present_with_error(
    driver: WebDriver, alert_text: str = ""
) -> Optional[Alert]:
    try:
        alert_obj = driver.switch_to.alert
        logger.warning(f"[ALERT PRESENTING] Alert: {alert_obj.text}")
        if alert_text == "":
            return
        if alert_text in alert_obj.text:
            return alert_obj
    except SeleniumUnexpectedAlertPresentException:
        return
    except SeleniumNoAlertPresentException:
        return

    return


def wait_until_element_is_visible(
    driver: WebDriver, max_wait_n_seconds: float, by: str, element_name: str
) -> WebElement:
    return WebDriverWait(driver, max_wait_n_seconds).until(
        expected_conditions.visibility_of_element_located((by, element_name))
    )


def brwoser_scroll_to_bottom(driver: WebDriver) -> None:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


def browser_scroll_to_element(driver: WebDriver, element: WebElement) -> None:
    driver.execute_script("arguments[0].scrollIntoView();", element)


def capture_driver_state(driver: WebDriver, error: Exception) -> None:
    error_file_dir = f"./error/{datetime.datetime.now()}"
    if not os.path.isdir(error_file_dir):
        os.makedirs(error_file_dir)
    driver.save_screenshot(f"{error_file_dir}/screenshot.png")
    current_full_html = str(
        driver.find_element(By.XPATH, "//body").get_attribute("outerHTML")
    )
    with open(f"{error_file_dir}/error.txt", "w") as file:
        file.write(str(error))
    with open(f"{error_file_dir}/html.html", "w") as file:
        file.write(current_full_html)
    logger.error(f"[ERROR] {error}")
