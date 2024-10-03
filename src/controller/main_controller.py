from py_spring import RestController


class MainController(RestController):
    def register_routes(self) -> None:
        @self.router.get("/")
        def get_root():
            return "Hello World"
