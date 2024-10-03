from enum import Enum
import json
from re import T
import time
from typing import ClassVar
from loguru import logger
from py_spring_core import Component
from pydantic import BaseModel
import selenium
import selenium.webdriver

from src.commons.selenium_driver_service import (
    SeleniumDriverService,
    WebDriver,
    By,
    Keys,
    WebDriverWait,
    expected_conditions,
    ActionChains,
    WebElement,
)
from src.repository.common import LoginTokenRead, TixcraftApiSource
from src.repository.models import LoginToken
from src.repository.repository import LoginTokenRepository
from src.service.ticket_bot.commons import DriverKey

RawToken = str


class GoogleLoginCredential(BaseModel):
    """
    Remember to disable 2FA for the account you want to use to login
    """

    email: str
    password: str


class GoogleLoginHandler(Component):
    SESSION_ID: ClassVar[str] = "SID"
    driver_service: SeleniumDriverService
    tixcraft_api_source: TixcraftApiSource
    token_repo: LoginTokenRepository

    def login(self, credential: GoogleLoginCredential) -> LoginTokenRead:
        token = self.token_repo.get_token_by_email(credential.email)
        logger.info(f"[TOKEN REGRIVED] Email: {credential.email} with token: {token}")
        if token is None or token.is_expired:
            if token is None:
                logger.warning(
                    f"[TOKEN NOT FOUND] Token not found for email: {credential.email}"
                )
            else:
                logger.warning(
                    f"[TOKEN EXPIRED] Token for email: {credential.email} is expired"
                )
            driver = self.driver_service.get_driver(DriverKey.GOOGLE)
            raw_token = self._login_with_driver(driver=driver, credential=credential)
            token = LoginToken(token=raw_token, email=credential.email)
            logger.success(
                f"[TOKEN CREATED] Token created for email: {credential.email}"
            )
            self.driver_service.close_driver(DriverKey.GOOGLE)
            logger.info("[DRIVER CLOSED] Google driver closed")
            new_token = self.token_repo.save_token(token)
            return new_token
        logger.success(f"[TOKEN REUSED] Token reused for email: {credential.email}")
        return token

    def _get_session_id_from_cookies(self, driver: WebDriver) -> str:
        sid_cookie = driver.get_cookie(self.SESSION_ID)
        if sid_cookie is None:
            raise ValueError("SID cookie not found")
        return json.dumps(sid_cookie)

    def _login_with_driver(
        self, driver: WebDriver, credential: GoogleLoginCredential
    ) -> RawToken:
        driver.get(self.tixcraft_api_source.google_login_url)
        self._enter_credentials(driver, credential)

        token = self._get_session_id_from_cookies(driver)
        return token

    def _is_under_reCaptcha(self, driver: WebDriver) -> bool:
        return (
            "https://accounts.google.com/v3/signin/challenge/recaptcha"
            in driver.current_url
        )

    def _handle_reCaptcha(self, driver: WebDriver) -> None:
        logger.info(f"[RECAPTCHA] Handling reCaptcha")
        self._click_not_a_bot_button(driver)
        while True:
            logger.info(f"[RECAPTCHA] Waiting for user to solve...")
            time.sleep(3)
            if not self._is_under_reCaptcha(driver):
                logger.success(f"[RECAPTCHA] reCaptcha solved...")
                break

    def _find_iframe(self, driver: WebDriver) -> WebElement:
        captcha_iframe = WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        return captcha_iframe

    # def _click_audio_play_button(self, driver: WebDriver) -> None:
    #     logger.info(f"[RECAPTCHA] Click audio play button")
    #     # driver.switch_to.frame('c-xsgh29r4he3')
    #     captcha_iframe = self._find_iframe(driver)
    #     logger.info(f"[RECAPTCHA] Found iframe: {captcha_iframe}")
    #     driver.switch_to.frame(captcha_iframe)
    #     time.sleep(3)
    #     audiobutton = driver.find_element(By.XPATH, '//*[@id="recaptcha-audio-button"]')
    #     driver.find_element(By.ID, 'rc-imageselect')

    #     driver.find_element(By.TAG_NAME, "a")
    #     audiobutton.click()

    def _click_not_a_bot_button(self, driver: WebDriver) -> None:
        logger.info(f"[RECAPTCHA] Click not a bot button")
        # find iframe
        captcha_iframe = self._find_iframe(driver)
        ActionChains(driver).move_to_element(captcha_iframe).click().perform()

        # click im not robot
        captcha_box = WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located(
                (By.ID, "g-recaptcha-response")
            )
        )
        driver.execute_script("arguments[0].click()", captcha_box)

    def _handle_redirect(self, driver: WebDriver) -> None:
        tixcraft_url = "https://tixcraft.com"
        while tixcraft_url not in driver.current_url:
            logger.info(f"[REDIRECT] Waiting for redirect...")
            time.sleep(3)
        logger.success(
            f"[REDIRECT] Redirected to {tixcraft_url}, waiting for page to load..."
        )
        time.sleep(10)

    def _enter_credentials(
        self, driver: WebDriver, credential: GoogleLoginCredential
    ) -> None:
        account_element = driver.find_element(By.ID, "identifierId")
        account_element.send_keys(credential.email)
        account_element.send_keys(Keys.RETURN)
        time.sleep(5)

        # in case reCaptcha may happen
        if self._is_under_reCaptcha(driver):
            logger.warning(
                f"[RECAPTCHA] reCaptcha detected, waiting for user to solve..."
            )
            self._handle_reCaptcha(driver)
            time.sleep(3)

        password_element = driver.find_element(By.NAME, "Passwd")
        password_element.send_keys(credential.password)
        password_element.send_keys(Keys.RETURN)
        time.sleep(5)

        self._handle_redirect(driver)
