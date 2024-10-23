import json
import threading
import time
from typing import ClassVar, Optional
from loguru import logger
from py_spring_core import Component
from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.commons.utils import timer
from src.commons import web_driver_utils
from src.commons.selenium_driver_service import (
    SeleniumDriverService,
    WebDriver,
    By,
    WebElement,
)
from src.commons.selenium_driver_service import (
    SeleniumNoSuchElementException,
)
from src.service.ticket_bot.google_login_handler import (
    GoogleLoginHandler,
)
from src.repository.repository import LoginTokenRepository
from src.service.ticket_bot.commons import DriverKey, LoginCredential
from src.service.ticket_bot.word_similarity_calculator import WordSimilarityCalculator
from src.service.ticket_bot.verification_code_decipher import VerificationCodeDecipher


"""
Cookie Signature:
{"domain": "tixcraft.com", "httpOnly": true, "name": "SID", "path": "/", "sameSite": "None", "secure": true, "value": "xxx"}
"""

class Event(BaseModel):
    event_key_word: str
    seat_key_word: str
    number_of_tickets: int
    delivery_key_words: list[str]
    payment_key_words: list[str]

    event_datetime: str
    exclude_key_words: list[str] = Field(default_factory=list)

    def as_view(self) -> str:
        return (
            f"Event: {self.event_key_word}\n"
            f"Seat: {self.seat_key_word}\n"
            f"Number of Tickets: {self.number_of_tickets}\n"
            f"Delivery Methods: {', '.join(self.delivery_key_words)}\n"
            f"Payment Methods: {', '.join(self.payment_key_words)}\n"
            f"Event Date and Time: {self.event_datetime}\n"
            f"Exclude Keywords: {', '.join(self.exclude_key_words)}"
        )




class EventContext(BaseModel):
    event_datetime: str

    event_name: str
    destination: str
    status: str
    url: str

    @computed_field
    @property
    def is_available(self) -> bool:
        available_identifiers = ["可購票", "可報名", "Find tickets"]
        return self.status in available_identifiers and self.url != ""


class VerificationCode(BaseModel):
    code: str

    @computed_field
    @property
    def is_valid(self) -> bool:
        if len(self.code) != 4:
            return False
        for char in self.code:
            if not char.isalpha():
                return False
        return True


class SeatContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    seat_name: str
    status: str
    element: WebElement

    @computed_field
    @property
    def is_available(self) -> bool:
        available_identifiers = ["available", "remaining", "熱賣中"]
        lowercase_status = self.status.lower()
        for _id in available_identifiers:
            if _id in lowercase_status:
                return True
        return False


class TixcraftTicketAssistant(Component):
    EVENT_URL: ClassVar[str] = "https://tixcraft.com/activity"
    TICKET_ENTRY_BASE_URL: ClassVar[str] = "https://tixcraft.com/ticket/ticket"
    PURCHASE_BUTTON_TEXT_IDS: ClassVar[list[str]] = ["Buy Tickets", "立即購票"]

    driver_service: SeleniumDriverService
    token_repo: LoginTokenRepository
    google_login_handler: GoogleLoginHandler
    code_decipher: VerificationCodeDecipher

    def __create_cookie(self, token: str) -> dict[str, str | bool]:
        return {
            "name": "SID",
            "value": token,
            "domain": "tixcraft.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None",
        }

    def async_purchase_ticket(self, credential: LoginCredential, event: Event) -> None:
        threading.Thread(target= lambda: self.purchase_ticket(credential, event)).start()
        

    @timer
    def purchase_ticket(self, credential: LoginCredential, event: Event) -> None:
        logger.info(
            f"[PURCHASE TICKET] Start purchasing ticket for event:\n {event.as_view()}"
        )
        try:
            logger.info(
                f"[PURCHASE TICKET] Start purchasing ticket for event: {event.event_key_word}"
            )
            token_read = self.token_repo.get_token_by_email(credential.email)
            
            if token_read is None:
                logger.error(
                    f"[PURCHASE TICKET] Token not found for email: {credential.email}"
                )
                return

            driver = self.driver_service.get_driver(DriverKey.TIXCRAFT)
            self._go_to_activities_page(driver)
            tixcraft_cookie = self.__create_cookie(token_read.token)
            self._load_token(driver, tixcraft_cookie)
            is_found_entry_page = self._go_to_ticket_purchasing_enty_page(driver, event)
            if not is_found_entry_page:
                logger.error("[PURCHASE TICKET] Event not found, skipping current purchase")
                return
            optional_event_context = (self._keep_click_buttton_purchase_ticket_until_ticket_is_available(event=event, driver=driver) )
            if optional_event_context is None:
                logger.error("[PURCHASE TICKET] Event not found")
                return
            logger.success(
                f"[PURCHASE TICKET] Event: {optional_event_context.event_name} is available"
            )
            start_time = time.time()
            self._select_seat(driver, optional_event_context, event)
            self._fill_purchase_form(driver, event)
            self._select_target_payment_method(driver, event)
            self._select_target_delivery_method(driver, event)
            self._click_checkout_button(driver)
            end_time = time.time()
            logger.success(f"[PURCHASE TICKET] Ticket is purchased, time spent: {end_time - start_time:.2f} seconds")
        except Exception as error:
            web_driver_utils.capture_driver_state(driver, error)

    def _select_ticket_quantity(self, driver: WebDriver, number_of_ticket: int) -> None:
        logger.info(f"[PURCHASE TICKET] Selecting ticket quantity: {number_of_ticket}")
        select_element = driver.find_element(By.CLASS_NAME, "mobile-select")
        max_tickets = int(
            select_element.text.strip().split("\n")[-1]
        )  # ["1", "2", "3"] -> "3"
        if number_of_ticket > max_tickets:
            logger.warning(
                f"[PURCHASE TICKET] Number of ticket is greater than max tickets: {number_of_ticket} > {max_tickets}, select max tickets"
            )
            web_driver_utils.select_by_visible_text(select_element, str(max_tickets))
            return
        web_driver_utils.select_by_visible_text(select_element, str(number_of_ticket))

    def _click_agree_cehckbox(self, driver: WebDriver) -> None:
        checkbox = driver.find_element(By.ID, "TicketForm_agree")
        checkbox.click()

    def _fill_purchase_form(self, driver: WebDriver, event: Event) -> None:
        potential_alert_erro = (
            """The verification code that you entered is incorrect. Please try again."""
        )
        self._select_ticket_quantity(driver, event.number_of_tickets)
        self._click_agree_cehckbox(driver)
        self._retry_passing_verification_codes(driver)
        self._submit_purchase_form(driver)
        optional_alert = web_driver_utils.alert_present_with_error(
            driver, potential_alert_erro
        )
        if optional_alert is not None:
            logger.error("[PURCHASE TICKET] Verification code is incorrect, retry...")
            optional_alert.accept()
            logger.info("[PURCHASE TICKET] Accepting alert...")
            self._fill_purchase_form(driver, event)

    def _submit_purchase_form(self, driver: WebDriver) -> None:
        logger.info("[PURCHASE TICKET] Submitting purchase form")
        submit_button = driver.find_element(By.CLASS_NAME, "btn-green")
        submit_button.click()
        time.sleep(0.5)

    def _retry_passing_verification_codes(self, driver: WebDriver) -> bool:
        while True:
            image_binary = self._screen_shot_verification_code(driver)
            code = self.code_decipher.detect_verification_code(image_binary)
            logger.info(f"[VERIFICATION CODE] Detected code: {code}")
            verification_code = VerificationCode(code=code)
            if not verification_code.is_valid:
                logger.error("[VERIFICATION CODE] Code is invalid")
                self._get_verification_code_element(driver).click()
                time.sleep(0.5)
                continue
            self._enter_verification_code(driver, code)
            break
        return True

    def _get_verification_code_element(self, driver: WebDriver) -> WebElement:
        return driver.find_element(By.ID, "TicketForm_verifyCode-image")

    def _enter_verification_code(self, driver: WebDriver, code: str) -> None:
        code_element = driver.find_element(By.ID, "TicketForm_verifyCode")
        code_element.send_keys(code)

    def _screen_shot_verification_code(self, driver: WebDriver) -> bytes:
        image_binary = self._get_verification_code_element(driver).screenshot_as_png
        return image_binary
    def _select_seat(
        self, driver: WebDriver, event_context: EventContext, event: Event
    ) -> Optional[SeatContext]:
        driver.get(event_context.url)
        logger.info(f"[PURCHASE TICKET] Go to event page: {event_context.event_name}")
        if self.TICKET_ENTRY_BASE_URL in driver.current_url:
            logger.info(
                "[PURCHASE TICKET] Already in ticket entry page, skipping seat selection..."
            )
            return
        web_driver_utils.wait_until_element_is_visible(driver, 30, By.CLASS_NAME, "area-list")
        all_seats = driver.find_element(By.CLASS_NAME, "area-list").find_elements(
            By.TAG_NAME, "a"
        )
        logger.info(
            f"[PURCHASE TICKET] Selecting seats:\n {[seat.text for seat in all_seats]}"
        )
        contexts: list[SeatContext] = []
        for seat in all_seats:
            status = seat.find_element(By.TAG_NAME, "font").text
            context = SeatContext(seat_name=seat.text, status=status, element=seat)
            contexts.append(context)

        calculator = WordSimilarityCalculator(
            event.seat_key_word, [context.seat_name for context in contexts]
        )
        optional_seat_context = None
        candidate_word = calculator.highest_similarity()
        for context in contexts:
            if context.seat_name == candidate_word:
                optional_seat_context = context
        if optional_seat_context is None:
            logger.error("[PURCHASE TICKET] Seat not found")
            return
        logger.success(
            f"[PURCHASE TICKET] Seat: {optional_seat_context.seat_name} is available"
        )
        web_driver_utils.browser_scroll_to_element(
            driver, optional_seat_context.element
        )
        time.sleep(1)
        optional_seat_context.element.click()
        logger.success(
            f"[PURCHASE TICKET] Seat: {optional_seat_context.seat_name} is selected, waiting for redirect to another page"
        )
        web_driver_utils.wait_until_element_is_visible(
            driver, 10, By.ID, "TicketForm_verifyCode-image"
        )
    def _keep_click_buttton_purchase_ticket_until_ticket_is_available(
        self, driver: WebDriver, event: Event
    ) -> Optional[EventContext]:
        # 持續點擊立即購票直到可以購票為止, 須小心對server短時間一直狂發request
        while True:
            logger.info(
                "[PURCHASE TICKET] Keep clicking purchase button until ticket is available"
            )

            purchase_button = driver.find_element(By.CLASS_NAME, "buy")
            web_driver_utils.browser_scroll_to_element(driver, purchase_button)
            is_found_purchase_button = False
            for _id in self.PURCHASE_BUTTON_TEXT_IDS:
                if _id in purchase_button.text:
                    is_found_purchase_button = True
                    purchase_button.click()
                    time.sleep(1)
                    break
            if not is_found_purchase_button:
                raise ValueError(
                    f"Button text is not in {self.PURCHASE_BUTTON_TEXT_IDS}"
                )
            purchase_button.click()
            time.sleep(1.5)
            contexts = self._get_all_event_context_from_page(driver)
            if self._is_ticket_can_be_ordered(contexts):
                # 等待購買按鈕可以按為止 (可防止下面日期抓不到的問題)
                break
        logger.success("[PURCHASE TICKET] Ticket is available")

        for ctx in contexts:
            if not ctx.is_available:
                continue
            logger.info(f"[PURCHASE TICKET] Event: {ctx.event_name} is available")
            if event.event_datetime in ctx.event_datetime:
                return ctx

    def _is_ticket_can_be_ordered(self, contexts: list[EventContext]) -> bool:
        for context in contexts:
            if context.is_available:
                return True
        return False

    def _get_all_event_context_from_page(self, driver: WebDriver) -> list[EventContext]:
        try:
            event_context_container = driver.find_element("id", "gameList")
            event_rows = event_context_container.find_elements(By.TAG_NAME, "tr")
            contexts = []
            for row in event_rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                evne_datetime, event_name, destination, status = cells
                url = status.find_element(By.TAG_NAME, "button").get_attribute(
                    "data-href"
                )
                event_context = EventContext(
                    event_datetime=evne_datetime.text,
                    event_name=event_name.text,
                    destination=destination.text,
                    status=status.text,
                    url=url or "",
                )
                contexts.append(event_context)
            return contexts
        except SeleniumNoSuchElementException:
            logger.error("[EVENT CONTEXT] Event context not found")
            return []

    def _go_to_ticket_purchasing_enty_page(
        self, driver: WebDriver, event: Event
    ) -> bool:
        logger.info(f"[EVENT PAGE] Go to event entry page: {event.event_key_word}")
        all_anchor_tags:dict[str, WebElement] = {
            tag.text: tag 
            for tag in driver.find_element(By.ID, "all").find_elements(By.TAG_NAME, "a") 
        }
        target_events: dict[str, WebElement] = {}
        
        for tag_text, tag in all_anchor_tags.items():
            if event.event_key_word in tag_text:
                target_events[tag_text] = tag

        popped_tags: set[str] = set()
        for tag_text in target_events.keys():
            for excluded_keyword in event.exclude_key_words:
                if excluded_keyword in tag_text:
                    popped_tags.add(tag_text)
                    break
        for tag_text in popped_tags:
            target_events.pop(tag_text)

        if len(target_events.keys()) == 0:
            logger.error(f"[EVENT NOT FOUND] Event {event.event_key_word} not found")
            return False
        target_event_url = list(target_events.values()).pop().get_attribute("href")
        if target_event_url is None:
            raise Exception(f"[EVENT URL NOT FOUND] Event {event.event_key_word} url not found")
        driver.get(target_event_url)
        logger.info(f"[EVENT PAGE] Go to event page: {event.event_key_word}")
        # 等待立即購票按鈕出現
        web_driver_utils.wait_until_element_is_visible(
            driver, 10, By.CLASS_NAME, "buy"
        )
        return True
        

    def _go_to_activities_page(self, driver: WebDriver) -> None:
        driver.get(self.EVENT_URL)
        self._accept_cookie_policy(driver)
        web_driver_utils.brwoser_scroll_to_bottom(driver)

    def _accept_cookie_policy(self, driver: WebDriver) -> None:
        time.sleep(1)
        if web_driver_utils.is_element_exists_by(driver, By.ID, "onetrust-accept-btn-handler"):
            logger.info("[COOKIE POLICY ACCEPTANCE] Accepting cookie policy...")
            try:
                accept_btn = driver.find_element("id", "onetrust-accept-btn-handler")
                accept_btn.click()
            except Exception as error:
                logger.error(f"[COOKIE POLICY ACCEPTANCE] {error}")
                return
            time.sleep(2)

    def _load_token(self, driver: WebDriver, injected_cookie: dict[str, str | bool]) -> None:
        logger.info("[COOKIE] Loading token...")
        for cookie in driver.get_cookies():
            if cookie["name"] != injected_cookie["name"]:
                continue
            logger.info(f"[COOKIE] {cookie}")
            cookie["value"] = injected_cookie["value"]
            driver.delete_cookie(cookie["name"])
            driver.add_cookie(cookie)
        driver.refresh()

    def _select_target_delivery_method(self, driver: WebDriver, event: Event) -> None:
        logger.info("[DELIVERY METHOD] Selecting delivery method...")
        web_driver_utils.wait_until_element_is_visible(
            driver, 10, By.CLASS_NAME, "pay-column"
        )  # 等待下方取票方式出現
        delivery_method_label_elements = driver.find_element(
            By.ID, "shipmentList"
        ).find_elements("tag name", "label")
        for keyword in event.delivery_key_words:
            for element in delivery_method_label_elements:
                if keyword in element.text:
                    element.click()
                    logger.info(
                        f"[DELIVERY METHOD] Selecting delivery method: {keyword}"
                    )
                    return

    def _select_target_payment_method(self, driver: WebDriver, event: Event) -> None:
        logger.info("[PAYMENT METHOD] Waiting for payment method to appear...")
        web_driver_utils.wait_until_element_is_visible(driver, 300, By.ID, "paymentBox")
        logger.info("[PAYMENT METHOD] Selecting payment method...")
        payment_method_label_elements = driver.find_element(
            By.ID, "paymentBox"
        ).find_elements(By.TAG_NAME, "label")
        for keyword in event.payment_key_words:
            for element in payment_method_label_elements:
                if keyword in element.text:
                    element.click()
                    time.sleep(0.5)
                    logger.info(f"[PAYMENT METHOD] Selecting payment method: {keyword}")
                    web_driver_utils.browser_scroll_to_element(driver, element)
                    return

    def _click_checkout_button(self, driver: WebDriver) -> None:
        logger.info("[CHECKOUT BUTTON] Waiting for checkout button to appear...")
        web_driver_utils.wait_until_element_is_visible(
            driver, 10, By.ID, "submitButton"
        )
        logger.info("[CHECKOUT BUTTON] Clicking checkout button")
        logger.info("[CHECKOUT BUTTON] Waiting for 0.5 seconds for scrolling...")
        checkout_button = driver.find_element(By.ID, "submitButton")
        web_driver_utils.browser_scroll_to_element(driver, checkout_button)
        checkout_button.click()
