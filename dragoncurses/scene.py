from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .loop import MainLoop
    from .component import Component
    from .input import InputEvent
    from .context import BoundingRectangle


class Scene:

    settings = None
    main_loop = None

    def __init__(self, main_loop: "MainLoop", settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.main_loop = main_loop

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

    def tick(self) -> None:
        pass

    def handle_input(self, event: "InputEvent") -> bool:
        return False
