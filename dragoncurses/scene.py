from typing import Any, Dict, Optional, Type, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .loop import MainLoop
    from .component import Component
    from .input import InputEvent
    from .context import BoundingRectangle

ComponentT = TypeVar("ComponentT", bound="Component")
SettingT = TypeVar("SettingT")


class Scene:
    def __init__(self, main_loop: "MainLoop", settings: Dict[str, Any]) -> None:
        self.settings: Dict[str, Any] = settings
        self.main_loop: "MainLoop" = main_loop
        self.__stored_components: Dict[str, "Component"] = {}

    def create(self) -> Optional["Component"]:
        return None

    def destroy(self) -> None:
        pass

    def register_component(
        self,
        component: "Component",
        location: Optional["BoundingRectangle"] = None,
        parent: Optional["Component"] = None,
    ) -> bool:
        self.main_loop.register_component(component, location, parent)
        return True

    def unregister_component(self, component: "Component") -> bool:
        self.main_loop.unregister_component(component)
        return True

    def put_reference(self, name: str, component: "ComponentT") -> "ComponentT":
        self.__stored_components[name] = component
        return component

    def get_reference(
        self, name: str, expected_type: Type["ComponentT"]
    ) -> "ComponentT":
        if name not in self.__stored_components:
            raise Exception("Invalid component reference {}".format(name))
        component = self.__stored_components[name]
        if not isinstance(component, expected_type):
            raise Exception("Invalid component reference {}".format(name))
        return component

    def put_setting(self, name: str, setting: "SettingT") -> "SettingT":
        self.settings[name] = setting
        return setting

    def get_setting(
        self,
        name: str,
        expected_type: Type["SettingT"],
        default: Optional["SettingT"] = None,
    ) -> "SettingT":
        if name not in self.settings:
            if default is not None:
                return default
            raise Exception("Invalid setting {}".format(name))
        setting = self.settings[name]
        if not isinstance(setting, expected_type):
            raise Exception("Invalid setting {}".format(name))
        return setting

    def get_optional_setting(
        self, name: str, expected_type: Type["SettingT"]
    ) -> Optional["SettingT"]:
        if name not in self.settings:
            return None
        setting = self.settings[name]
        if not isinstance(setting, expected_type):
            raise Exception("Invalid setting {}".format(name))
        return setting

    def del_setting(self, name: str) -> None:
        if name in self.settings:
            del self.settings[name]

    def tick(self) -> None:
        pass

    def handle_input(self, event: "InputEvent") -> bool:
        return False
