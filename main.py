from py_spring_core import PySpringApplication
from py_spring_model import provide_py_spring_model

def main():
    app = PySpringApplication("./app-config.json", entity_providers=[provide_py_spring_model()])
    app.run()

if __name__ == "__main__":
    main()