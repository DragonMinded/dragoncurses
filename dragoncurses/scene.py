from typing import Any, Dict, Optional, Type, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .loop import MainLoop
    from .component import Component
    from .input import InputEvent
    from .context import BoundingRectangle

ComponentT = TypeVar("ComponentT", bound="Component")


class Scene:

    def __init__(self, main_loop: "MainLoop", settings: Dict[str, Any]) -> None:
        self.settings: Dict[str, Any] = settings
        self.main_loop: "MainLoop" = main_loop
        self.__stored_components: Dict[str, "Component"] = {}

    def create(self) -> Optional["Component"]:
        return None

    def destroy(self) -> None:
        pass

    def register_component(self, component: "Component", location: Optional["BoundingRectangle"] = None, parent: Optional["Component"] = None) -> bool:
        self.main_loop.register_component(component, location, parent)
        return True

    def unregister_component(self, component: "Component") -> bool:
        self.main_loop.unregister_component(component)
        return True

    def put_reference(self, name: str, component: "ComponentT") -> "ComponentT":
        self.__stored_components[name] = component
        return component

    def get_reference(self, name: str, expected_type: Type["ComponentT"]) -> "ComponentT":
        if name not in self.__stored_components:
            raise Exception("Invalid component reference {}".format(name))
        component = self.__stored_components[name]
        if not isinstance(component, expected_type):
            raise Exception("Invalid component reference {}".format(name))
        return component

    def tick(self) -> None:
        pass

    def handle_input(self, event: "InputEvent") -> bool:
        return False
