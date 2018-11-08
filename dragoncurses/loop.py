import curses
import time

from contextlib import contextmanager
from _curses import error as CursesError
from typing import Any, Callable, Dict, Generator, Optional, Type

from .context import RenderContext
from .input import KeyboardInputEvent, MouseInputEvent, Buttons
from .scene import Scene


@contextmanager
def loop_config(context) -> Generator[None, None, None]:
    context.nodelay(1)
    curses.curs_set(0)
    _, oldmask = curses.mousemask(curses.BUTTON1_RELEASED | curses.BUTTON2_RELEASED | curses.BUTTON3_RELEASED | curses.BUTTON4_RELEASED)
    curses.use_default_colors()

    yield

    context.clear()
    context.refresh()

    curses.mousemask(oldmask)
    curses.curs_set(1)
    context.nodelay(0)


class MainLoop:

    TICK_DELTA = 1/12

    class _ExitScene(Scene):
        pass

    def __init__(self, context, settings: Dict[str, Any], idle_callback: Optional[Callable[["MainLoop"], None]] = None) -> None:
        self.context = RenderContext(context)
        self.settings = settings
        self.scene = None
        self.components = []
        self.registered_components = []
        self.__next_scene = None
        self.__dirty = False
        self.__idle = idle_callback
        self.__last_tick = 0.0

    def change_scene(self, scene: Type[Scene]) -> None:
        if self.__next_scene is None:
            self.__next_scene = scene(self, self.settings)

    def exit(self) -> None:
        self.__next_scene = MainLoop._ExitScene(self, self.settings)

    def register_component(self, component: "Component", location: Optional["BoundingRectangle"], parent: Optional["Component"]) -> None:
        if parent is not None and location is None:
            raise Exception('Must provide a location when providing a parent!')

        if self.scene is not None:
            component._attach(self.scene, self.settings)
            self.registered_components.append((component, location, parent))
            self.__dirty = True

    def unregister_component(self, component: "Component") -> None:
        found_components = [
            c for c in self.registered_components
            if id(c[0]) == id(component)
        ]
        self.registered_components = [
            c for c in self.registered_components
            if id(c[0]) != id(component)
        ]
        for (component, _, _) in found_components:
            component._detach()
            self.__dirty = True

    def run(self) -> None:
        while self.scene is not None or self.__next_scene is not None:
            # First, see if we should change the scene
            if self.__next_scene is not None:
                # Destroy the old scene if it exists
                if self.scene is not None:
                    self.scene.destroy()

                # Unregister components that were attached and left open
                for (component, _, _) in self.registered_components:
                    component._detach()

                # Detach the components from the display
                for component in self.components:
                    component._detach()

                # Transfer the next scene over
                self.scene = self.__next_scene
                self.__next_scene = None
                self.__last_tick = time.time()
                self.registered_components = []

                # Set everything to empty if we are exiting (special sentinal)
                if isinstance(self.scene, MainLoop._ExitScene):
                    self.scene = None
                    self.components = []
                else:
                    component = self.scene.create()
                    self.components = [component] if component else []

                # Actualize each component
                for component in self.components:
                    component._attach(self.scene, self.settings)

                # Always paint the first scene
                self.__dirty = True

            # Now, tick the scene
            now = time.time()
            if now - self.__last_tick > self.TICK_DELTA:
                num_ticks = int((now - self.__last_tick) / self.TICK_DELTA)
                self.__last_tick = now
                for _ in range(num_ticks):
                    if self.scene:
                        self.scene.tick()
                    for component in self.components:
                        component.tick()
                    for (component, _, _) in self.registered_components:
                        component.tick()

            # Now, see about drawing the scene
            if (
                self.__dirty or
                any(component.dirty for component in self.components) or
                any(component.dirty for (component, _, _) in self.registered_components)
            ):
                if self.__dirty:
                    # Only clear when we resize or paint a new scene. Otherwise just refresh.
                    self.context.clear()
                for component in self.components:
                    component._render(self.context, self.context.bounds)
                # Render these last, because they depend on their parent being rendered to know where to go.
                # Also, these are used for floating menus and dialogs, so they must be last.
                for (component, location, parent) in self.registered_components:
                    if parent is None:
                        parentlocation = self.context.bounds
                    else:
                        parentlocation = parent.location
                    if location is None:
                        location = self.context.bounds
                    component._render(self.context, location.offset(parentlocation.top, parentlocation.left).clip(self.context.bounds))
                self.context.refresh()
            self.__dirty = False

            # Finally, handle input to the scene, then to the components
            key = self.context.getkey()
            event = None

            if key is not None:
                if key == "KEY_RESIZE":
                    # We assume that a refresh is effectively free, so we don't
                    # attempt to calculate how long to wait next time based on
                    # forgetting to do this loop.
                    self.__dirty = True
                elif key == "KEY_MOUSE":
                    try:
                        _, x, y, _, mask = curses.getmouse()
                        if mask == curses.BUTTON1_RELEASED:
                            event = MouseInputEvent(x, y, Buttons.LEFT)
                        elif mask == curses.BUTTON2_RELEASED:
                            event = MouseInputEvent(x, y, Buttons.MIDDLE)
                        elif mask == curses.BUTTON3_RELEASED:
                            event = MouseInputEvent(x, y, Buttons.RIGHT)
                        elif mask == curses.BUTTON4_RELEASED:
                            event = MouseInputEvent(x, y, Buttons.EXTRA)
                    except CursesError:
                        pass
                else:
                    event = KeyboardInputEvent(key)

                if event is not None:
                    # First, handle registered components
                    handled = False

                    # Registered components are usually some sort of popover, so prioritize
                    # newest (topmost) over oldest (bottommost).
                    for (component, _, _) in reversed(self.registered_components):
                        if handled:
                            break
                        handled = component._handle_input(event)

                    # Now, handle standard drawn components
                    for component in self.components:
                        # Bail if we've already handled this input
                        if handled:
                            break
                        handled = component._handle_input(event)

                    # Finally, handle scene-global hotkeys
                    if not handled and self.scene is not None:
                        handled = self.scene.handle_input(event)

            
            if event is None and not self.__dirty:
                # Call the idle timeout function so main application can do work
                if self.__idle is not None:
                    self.__idle(self)
