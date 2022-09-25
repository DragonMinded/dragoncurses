import curses
import os
import platform
import time

from contextlib import contextmanager
from _curses import error as CursesError
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Type

from .context import BoundingRectangle, RenderContext
from .component import Component, DeferredInput
from .input import (
    InputEvent,
    KeyboardInputEvent,
    MouseInputEvent,
    ScrollInputEvent,
    Buttons,
    Directions,
)
from .scene import Scene


CursesContext = Any


@contextmanager
def loop_config(context: CursesContext) -> Generator[None, None, None]:
    curses.noecho()
    curses.curs_set(0)
    curses.mouseinterval(0)
    _, oldmask = curses.mousemask(-1)
    curses.use_default_colors()

    yield

    context.clear()
    context.refresh()

    # curses.mousemask(oldmask)
    curses.curs_set(1)
    curses.echo()


def execute(
    start_scene: Type[Scene],
    settings: Optional[Dict[str, Any]] = None,
    idle_callback: Optional[Callable[["MainLoop"], None]] = None,
    realtime: bool = False,
) -> None:
    os.environ.setdefault("ESCDELAY", "25")
    os.environ["ESCDELAY"] = "25"

    def wrapped(context: CursesContext) -> None:
        # Run the main program loop
        with loop_config(context):
            loop = MainLoop(
                context,
                settings if settings is not None else {},
                idle_callback,
                realtime=realtime,
            )
            loop.change_scene(start_scene)
            loop.run()

    curses.wrapper(wrapped)


class MainLoop:

    TICK_DELTA = 1 / 12

    class _ExitScene(Scene):
        pass

    def __init__(
        self,
        context: CursesContext,
        settings: Dict[str, Any],
        idle_callback: Optional[Callable[["MainLoop"], None]] = None,
        realtime: bool = False,
    ) -> None:
        if not realtime and idle_callback:
            raise Exception("Cannot have idle callback without realtime mode!")
        if realtime:
            context.nodelay(1)
        else:
            context.nodelay(0)
        self.context = RenderContext(context)
        self.settings = settings
        self.scene: Optional[Scene] = None
        self.components: List[Component] = []
        self.registered_components: List[
            Tuple[Component, Optional[BoundingRectangle], Optional[Component]]
        ] = []
        self.__next_scene: Optional[Scene] = None
        self.__dirty: bool = False
        self.__idle = idle_callback
        self.__last_tick: float = 0.0
        self.__mousestate: Dict[Buttons, Tuple[Tuple[int, int], float]] = {
            Buttons.LEFT: ((-1, -1), -1),
            Buttons.MIDDLE: ((-1, -1), -1),
            Buttons.RIGHT: ((-1, -1), -1),
        }

    def change_scene(self, scene: Type[Scene]) -> None:
        if self.__next_scene is None:
            self.__next_scene = scene(self, self.settings)

    def exit(self) -> None:
        self.__next_scene = MainLoop._ExitScene(self, self.settings)

    def register_component(
        self,
        component: Component,
        location: Optional[BoundingRectangle],
        parent: Optional[Component],
    ) -> None:
        if parent is not None and location is None:
            raise Exception("Must provide a location when providing a parent!")

        if self.scene is not None:
            component._attach(self.scene, self.settings)
            self.registered_components.append((component, location, parent))
            self.__dirty = True

    def unregister_component(self, component: Component) -> None:
        found_components = [
            c for c in self.registered_components if id(c[0]) == id(component)
        ]
        self.registered_components = [
            c for c in self.registered_components if id(c[0]) != id(component)
        ]
        for (component, _, _) in found_components:
            component._detach()
            self.__dirty = True

    def run(self) -> None:
        # Some redraw optimizations don't seem to work on Windows.
        on_windows: bool = platform.system() == "Windows"

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
                    newcomponent = self.scene.create()
                    self.components = [newcomponent] if newcomponent else []

                # Actualize each component
                if self.scene:
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
                self.__dirty
                or any(component.dirty for component in self.components)
                or any(
                    component.dirty for (component, _, _) in self.registered_components
                )
            ):
                if on_windows or self.__dirty:
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
                        parentlocation = (
                            parent.location
                            if parent.location is not None
                            else self.context.bounds
                        )
                    if location is None:
                        location = self.context.bounds
                    component._render(
                        self.context,
                        location.offset(parentlocation.top, parentlocation.left).clip(
                            self.context.bounds
                        ),
                    )
                self.context.refresh()
            self.__dirty = False

            # Finally, handle input to the scene, then to the components
            event: Optional[InputEvent] = None
            if self.scene:
                key = self.context.getkey()
            else:
                key = None

            if key is not None:
                if key == "KEY_RESIZE":
                    # We assume that a refresh is effectively free, so we don't
                    # attempt to calculate how long to wait next time based on
                    # forgetting to do this loop.
                    self.__dirty = True
                elif key == "KEY_MOUSE":
                    try:
                        _, x, y, _, mask = curses.getmouse()
                        if mask == curses.BUTTON1_PRESSED:
                            self.__mousestate[Buttons.LEFT] = ((x, y), time.time())
                        elif mask == curses.BUTTON2_PRESSED:
                            self.__mousestate[Buttons.MIDDLE] = ((x, y), time.time())
                        elif mask == curses.BUTTON3_PRESSED:
                            self.__mousestate[Buttons.RIGHT] = ((x, y), time.time())
                        elif mask == curses.BUTTON4_PRESSED:
                            event = ScrollInputEvent(x, y, Directions.UP)
                        elif mask == curses.BUTTON1_RELEASED:
                            if (
                                self.__mousestate[Buttons.LEFT][0] == (x, y)
                                and (time.time() - self.__mousestate[Buttons.LEFT][1])
                                < 1.0
                            ):
                                event = MouseInputEvent(x, y, Buttons.LEFT)
                        elif mask == curses.BUTTON2_RELEASED:
                            if (
                                self.__mousestate[Buttons.MIDDLE][0] == (x, y)
                                and (time.time() - self.__mousestate[Buttons.MIDDLE][1])
                                < 1.0
                            ):
                                event = MouseInputEvent(x, y, Buttons.MIDDLE)
                        elif mask == curses.BUTTON3_RELEASED:
                            if (
                                self.__mousestate[Buttons.RIGHT][0] == (x, y)
                                and (time.time() - self.__mousestate[Buttons.RIGHT][1])
                                < 1.0
                            ):
                                event = MouseInputEvent(x, y, Buttons.RIGHT)
                        elif mask == curses.REPORT_MOUSE_POSITION or mask == 0x200000:
                            event = ScrollInputEvent(x, y, Directions.DOWN)
                    except CursesError:
                        pass
                else:
                    event = KeyboardInputEvent(key)

                if event is not None:
                    handled: bool = False
                    deferred: List[DeferredInput] = []

                    # First, handle registered components
                    # Registered components are usually some sort of popover, so prioritize
                    # newest (topmost) over oldest (bottommost).
                    for (component, _, _) in reversed(self.registered_components):
                        # Bail if we've already handled this input
                        if handled:
                            break
                        _handled = component._handle_input(event)

                        # If this control wants to be deferred, add it to the list
                        # and then try the next control. Otherwise, handle the input
                        # as normal.
                        if isinstance(_handled, bool):
                            handled = _handled
                        else:
                            deferred.append(_handled)

                    # Now, handle standard drawn components
                    for component in self.components:
                        # Bail if we've already handled this input
                        if handled:
                            break
                        _handled = component._handle_input(event)

                        # If this control wants to be deferred, add it to the list
                        # and then try the next control. Otherwise, handle the input
                        # as normal.
                        if isinstance(_handled, bool):
                            handled = _handled
                        else:
                            deferred.append(_handled)

                    # Now, call deferred components, prioritizing the first
                    # one we find.
                    if not handled and deferred:
                        for callback in deferred:
                            # Bail if we've already handled this inpuit
                            if handled:
                                break

                            # Run the control's deferred input callback
                            handled = callback()

                    # Finally, handle scene-global input
                    if not handled and self.scene is not None:
                        handled = self.scene.handle_input(event)

            if self.scene and event is None and not self.__dirty:
                # Call the idle timeout function so main application can do work
                if self.__idle is not None:
                    self.__idle(self)
