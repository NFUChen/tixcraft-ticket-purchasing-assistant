from uuid import uuid4
from py_spring_core import DeleteMapping, GetMapping, PostMapping, RestController

from src.service.chrome.chrome_setup_service import ChomeSetupService, ChromeDeployment
from src.service.ticket_bot.commons import LoginCredential
from src.service.ticket_bot.tixcraft_ticket_assistant import Event, TixcraftTicketAssistant


class MainController(RestController):
    chrome_setup_service: ChomeSetupService
    tixcraft_ticket_assistant: TixcraftTicketAssistant

    @GetMapping("/set-up-chrome")
    def set_up_chrome(self) -> ChromeDeployment:
        namespace = f"chrome-{str(uuid4())}"
        return self.chrome_setup_service.install_chrome_chart(namespace)
    
    @DeleteMapping("/delete-chrome")
    def delete_chrome(self, namespace: str) -> dict[str, str]:
        self.chrome_setup_service.uninstall_chrome_chart(namespace)
        return {"message": f"Chrome deleted in namespace {namespace}"}

    @PostMapping("/purchase-ticket")
    def purchase_ticket(self, credential: LoginCredential, event: Event, service_ip: str) -> None:
        self.tixcraft_ticket_assistant.purchase_ticket(credential, event, service_ip)