from enum import Enum
import math
import time
from typing import Optional
from typing_extensions import Self
from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator
import selenium
import selenium.webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chromium.options import ChromiumOptions
from py_spring import Component, Properties

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select  # for dropdown menu selection
from selenium.common.exceptions import (
    NoSuchElementException as SeleniumNoSuchElementException,
    NoAlertPresentException as SeleniumNoAlertPresentException,
    UnexpectedAlertPresentException as SeleniumUnexpectedAlertPresentException,
)
from undetected_chromedriver import Chrome as UndetectedChrome

from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.alert import Alert


class DriverMode(str, Enum):
    Local = "local"
    Remote = "remote"


class SeleniumProperties(Properties):
    __key__: str = "selenium"
    remote_host: str
    mode: DriverMode
    chrome_binary_path: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def check_chrome_binary_path(self) -> Self:
        if self.mode == DriverMode.Local and self.chrome_binary_path is None:
            raise ValueError("chrome_binary_path is required when mode is local")
        return self


class SeleniumDriverService(Component):
    properties: SeleniumProperties

    def __init__(self) -> None:
        self.driver_pool: dict[str, WebDriver] = {}

    def destroy(self) -> None:
        try:
            logger.info("[WEBDRIVER CLOSE] Waitting 3 seconds to close webdriver")
            time.sleep(3)
        finally:
            logger.info(f"[WEBDRIVER CLOSE] Close {len(self.driver_pool)} webdrivers")
            for key, driver in self.driver_pool.items():
                self._close_driver(driver, key)

    def get_driver(self, driver_key: str) -> WebDriver:
        match self.properties.mode:
            case DriverMode.Local:
                driver = self._get_local_driver()
            case DriverMode.Remote:
                driver = self._get_remote_driver()

        self.driver_pool[driver_key] = driver
        driver.maximize_window()
        return driver

    def _close_driver(self, driver: WebDriver, driver_name: str) -> None:
        try:
            logger.info(f"[WEBDRIVER CLOSE] Close webdriver: {driver}: {driver_name}")
            driver.close()
        except Exception as error:
            logger.error(f"[WEBDRIVER CLOSE] Close webdriver failed: {error}, skip")

    def close_driver(self, driver_key: str) -> None:
        if driver_key not in self.driver_pool:
            logger.warning(
                f"[DRIVER NOT FOUND] Driver not found in driver_pool: {driver_key}"
            )
            return
        driver = self.driver_pool.pop(driver_key)
        self._close_driver(driver, driver_key)

    def _get_chrome_options(self) -> selenium.webdriver.ChromeOptions:
        options = selenium.webdriver.ChromeOptions()
        # 防止 UnexpectedAlertPresentException 跳出直接阻斷,但有時可以打開看一下bug出在哪
        options.set_capability("unhandledPromptBehavior", "accept and notify")
        options.add_argument("--incognito")
        options.add_argument("--disable-smooth-scrolling")
        if self.properties.chrome_binary_path is None:
            raise ValueError("chrome_binary_path is required when mode is local")
        options.binary_location = self.properties.chrome_binary_path
        return options

    def _get_local_driver(self) -> WebDriver:
        driver = UndetectedChrome(options=self._get_chrome_options())
        return driver

    def _get_remote_driver(self) -> WebDriver:
        options = ChromiumOptions()
        logger.info(
            f"[REMOTE HOST CONNECTION] Connect to remote_host: {self.properties.remote_host}"
        )
        driver = WebDriver(
            command_executor=self.properties.remote_host,
            options=options,
            keep_alive=True,
        )
        return driver
