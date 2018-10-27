from threading import Lock
from _curses import error as CursesError
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from .input import Buttons, Keys, MouseInputEvent, KeyboardInputEvent, DefocusInputEvent
from .context import Color, RenderContext, BoundingRectangle
from .settings import Settings

if TYPE_CHECKING:
    from .scene import Scene
    from .input import InputEvent


class ComponentException(Exception):
    pass


class Component:

    location = None
    settings = None
    scene = None
    __children = None

    def __init__(self) -> None:
        self.lock = Lock()

    def _attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.scene = scene
        self.__children = []
        self.attach(scene, settings)

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        """
        Override this in your subclass to do any attach-related handling.
        """
        pass

    def _detach(self) -> None:
        for child in self.__children:
            child._detach()
        self.detach()

    def detach(self) -> None:
        """
        Override this in your subclass to do any detach-related handling.
        """
        pass

    def register(self, component: "Component", location: "BoundingRectangle") -> None:
        self.scene.register_component(component, location, parent=self)
        self.__children.append(component)

    def unregister(self, component: "Component") -> None:
        self.scene.unregister_component(component)
        self.__children = [
            c for c in self.__children
            if id(c) != id(component)
        ]

    @property
    def dirty(self) -> bool:
        """
        Override this in your subclass to declare that you're dirty and
        need to be redrawn.
        """
        return False

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        """
        Override this in your subclass to determine the exact size of
        your component, if it can be calculated by its properties. If
        it cannot be, return None.
        """
        return None

    def tick(self) -> None:
        """
        Override this in your subclass to tick forward animations.
        """
        pass

    def _render(self, context: RenderContext, bounds: BoundingRectangle) -> None:
        with context.clip(bounds) as subcontext:
            self.location = subcontext.location
            with self.lock:
                self.render(subcontext)

    def render(self, context: RenderContext) -> None:
        """
        Override this in your subclass to render to a context.
        """
        pass

    def _handle_input(self, event: "InputEvent") -> bool:
        if isinstance(event, MouseInputEvent):
            if self.location is not None:
                if self.location.contains(event.y, event.x):
                    # Send a mouse event
                    return self.handle_input(event)
                else:
                    # Send that a mouse event happened elsewhere
                    return self.handle_input(DefocusInputEvent(event.button))
            # Should never happen, but if location isn't set we don't handle mouse
            return False
        else:
            return self.handle_input(event)

    def handle_input(self, event: "InputEvent") -> bool:
        """
        Override this in your subclass to handle input.
        """
        return False

    def __repr__(self) -> str:
        return "{}()".format(self.__class__.__name__)


class EmptyComponent(Component):
    pass


def _text_to_hotkeys(text: str) -> Tuple[str, Optional[str]]:
    hotkey = None
    last_char = None
    output = ""

    for char in text:
        if char == "&":
            # Either output it if its escaped from last time, or
            # don't output it at all waiting to see what follows it.
            if last_char == "&":
                # Escaped & character
                output = output + "&"
                last_char = None
                continue
        elif last_char == "&":
            # If we have no hotkey, capture this as the hotkey and label
            # it as such.
            if hotkey is None and char.isalnum():
                hotkey = char
                output = output + "<underline>" + char + "</underline>"
            else:
                # We already got our hotkey, or this is an invalid hotkey
                output = output + char
        else:
            # Just copy the input
            output = output + char

        # Remember this for next time
        last_char = char

    if hotkey is not None:
        return (output, hotkey.lower())
    else:
        return (output, None)


class LabelComponent(Component):

    def __init__(self, text: str = "", *, color: Optional[str] = None, invert: bool = False, formatted: bool = False) -> None:
        super().__init__()
        self.__text = text
        self.__color = color or Color.NONE
        self.__invert = invert
        self.__rendered = False
        self.__formatted = formatted

    def render(self, context: RenderContext) -> None:
        if self.__invert:
            # Fill the entire label so that it is fully inverted
            for line in range(context.bounds.height):
                context.draw_string(line, 0, " " * context.bounds.width, invert=True)
        else:
            # Erase the background because labels aren't clear.
            context.clear()

        # Display differently depending on if the test is formatted or not
        if self.__formatted:
            if self.__invert:
                pre = "<invert>"
                post = "</invert>"
            else:
                pre = ""
                post = ""
            if self.color != Color.NONE:
                pre = pre + "<{}>".format(self.__color.lower())
                post = "</{}>".format(self.__color.lower()) + post
            context.draw_formatted_string(0, 0, pre + self.__text + post)
        else:
            context.draw_string(0, 0, self.__text, color=self.__color, invert=self.__invert)

        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    def __get_text(self) -> str:
        return self.__text

    def __set_text(self, text: str) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__text == text)
            self.__text = text

    text = property(__get_text, __set_text)

    def __get_color(self) -> str:
        return self.__color

    def __set_color(self, color: str) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__color == color)
            self.__color = color

    color = property(__get_color, __set_color)

    def __get_invert(self) -> bool:
        return self.__invert

    def __set_invert(self, invert: bool) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__invert == invert)
            self.__invert = invert

    invert = property(__get_invert, __set_invert)

    def __repr__(self) -> str:
        return "LabelComponent(text={})".format(self.__text)


class ClickableComponent(Component):

    callback = None

    def on_click(self, callback: Callable[[Component, str], None]) -> "self":
        self.callback = callback
        return self

    def handle_input(self, event: "InputEvent") -> bool:
        # Overrides handle_input instead of _handle_input because this is
        # meant to be used as either a mixin. This handles input entirely,
        # instead of intercepting it, so thus overriding the public function.
        if isinstance(event, MouseInputEvent):
            if self.callback is not None:
                self.callback(self, event.button)
            # We still handled this regardless of notification
            return True

        return super().handle_input(event)


class HotkeyableComponent(Component):

    hotkey = None

    def set_hotkey(self, key: str) -> "self":
        if key.isalnum():
            self.hotkey = key.lower()
        return self

    def handle_input(self, event: "InputEvent") -> bool:
        # Overrides handle_input instead of _handle_input because this is
        # meant to be used as either a mixin. This handles input entirely,
        # instead of intercepting it, so thus overriding the public function.
        if self.hotkey is not None:
            if isinstance(event, KeyboardInputEvent):
                if event.character != self.hotkey:
                    # Wrong input, defer to other mixins
                    return super().handle_input(event)

                callback = getattr(self, 'callback', None)
                if callback is not None:
                    callback(self, Buttons.KEY)

                # We still handled this regardless of notification
                return True

        return super().handle_input(event)


class ButtonComponent(HotkeyableComponent, ClickableComponent, Component):

    def __init__(self, text: str = "", *, textcolor: Optional[str] = None, bordercolor: Optional[str] = None, formatted: bool = False) -> None:
        super().__init__()
        self.__label = LabelComponent(text, color=textcolor, formatted=formatted)
        self.__border = BorderComponent(
            PaddingComponent(self.__label, horizontalpadding=1),
            style=BorderComponent.DOUBLE if Settings.enable_unicode else BorderComponent.ASCII,
            color=bordercolor,
        )

    def render(self, context: RenderContext) -> None:
        self.__border._render(context, context.bounds)

    @property
    def dirty(self) -> bool:
        return self.__border.dirty or self.__label.dirty

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__border._attach(scene, settings)

    def detach(self) -> None:
        self.__border._detach()

    def tick(self) -> None:
        self.__border.tick()

    def __get_text(self) -> str:
        return self.__label.text  # pyre-ignore Pyre doesn't understand properties...

    def __set_text(self, text: str) -> None:
        with self.lock:
            self.__label.text = text

    text = property(__get_text, __set_text)

    def __get_textcolor(self) -> str:
        return self.__label.color  # pyre-ignore Pyre doesn't understand properties...

    def __set_textcolor(self, color: str) -> None:
        with self.lock:
            self.__label.color = color

    textcolor = property(__get_textcolor, __set_textcolor)

    def __get_bordercolor(self) -> str:
        return self.__border.color  # pyre-ignore Pyre doesn't understand properties...

    def __set_bordercolor(self, color: str) -> None:
        with self.lock:
            self.__border.color = color

    bordercolor = property(__get_bordercolor, __set_bordercolor)

    def __repr__(self) -> str:
        return "ButtonComponent(text={})".format(self.__label.text)


class BorderComponent(Component):

    SOLID = 'SOLID'
    ASCII = 'ASCII'
    SINGLE = 'SINGLE'
    DOUBLE = 'DOUBLE'

    def __init__(self, component: Component, *, style: Optional[str] = None, color: Optional[str] = None) -> None:
        super().__init__()
        self.__component = component
        self.__style = style or BorderComponent.SOLID
        self.__color = color or Color.NONE
        self.__drawn = False

        if self.__style in [self.SINGLE, self.DOUBLE] and not Settings.enable_unicode:
            raise ComponentException("Unicode is not enabled, cannot use {} border style!".format(self.__style))

    @property
    def dirty(self) -> bool:
        return (not self.__drawn) or self.__component.dirty

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        innerbounds = self.__component.bounds
        if innerbounds is None:
            return None
        return BoundingRectangle(
            top=0,
            bottom=(innerbounds.height + 2) if (innerbounds.height > 0) else 0,
            left=0,
            right=(innerbounds.width + 2) if (innerbounds.width > 0) else 0,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__drawn = True

        context.clear()

        for x in range(context.bounds.width):
            if self.__style == BorderComponent.SOLID:
                context.draw_string(0, x, " ", invert=True, color=self.__color)
                context.draw_string(context.bounds.height - 1, x, " ", invert=True, color=self.__color)
            elif self.__style == BorderComponent.ASCII:
                context.draw_string(0, x, "-", color=self.__color)
                context.draw_string(context.bounds.height - 1, x, "-", color=self.__color)
            elif self.__style == BorderComponent.SINGLE:
                context.draw_string(0, x, "\u2500", color=self.__color)
                context.draw_string(context.bounds.height - 1, x, "\u2500", color=self.__color)
            elif self.__style == BorderComponent.DOUBLE:
                context.draw_string(0, x, "\u2550", color=self.__color)
                context.draw_string(context.bounds.height - 1, x, "\u2550", color=self.__color)
            else:
                raise ComponentException("Invalid border style {}".format(self.__style))

        for y in range(1, context.bounds.height - 1):
            if self.__style == BorderComponent.SOLID:
                context.draw_string(y, 0, " ", invert=True, color=self.__color)
                context.draw_string(y, context.bounds.width - 1, " ", invert=True, color=self.__color)
            elif self.__style == BorderComponent.ASCII:
                context.draw_string(y, 0, "|", color=self.__color)
                context.draw_string(y, context.bounds.width - 1, "|", color=self.__color)
            elif self.__style == BorderComponent.SINGLE:
                context.draw_string(y, 0, "\u2502", color=self.__color)
                context.draw_string(y, context.bounds.width - 1, "\u2502", color=self.__color)
            elif self.__style == BorderComponent.DOUBLE:
                context.draw_string(y, 0, "\u2551", color=self.__color)
                context.draw_string(y, context.bounds.width - 1, "\u2551", color=self.__color)
            else:
                raise ComponentException("Invalid border style {}".format(self.__style))

        if self.__style == BorderComponent.ASCII:
            context.draw_string(0, 0, "+", color=self.__color)
            context.draw_string(0, context.bounds.width - 1, "+", color=self.__color)
            context.draw_string(context.bounds.height - 1, 0, "+", color=self.__color)
            context.draw_string(context.bounds.height - 1, context.bounds.width - 1, "+", color=self.__color)
        elif self.__style == BorderComponent.SINGLE:
            context.draw_string(0, 0, "\u250C", color=self.__color)
            context.draw_string(0, context.bounds.width - 1, "\u2510", color=self.__color)
            context.draw_string(context.bounds.height - 1, 0, "\u2514", color=self.__color)
            context.draw_string(context.bounds.height - 1, context.bounds.width - 1, "\u2518", color=self.__color)
        elif self.__style == BorderComponent.DOUBLE:
            context.draw_string(0, 0, "\u2554", color=self.__color)
            context.draw_string(0, context.bounds.width - 1, "\u2557", color=self.__color)
            context.draw_string(context.bounds.height - 1, 0, "\u255A", color=self.__color)
            context.draw_string(context.bounds.height - 1, context.bounds.width - 1, "\u255D", color=self.__color)

        if context.bounds.width > 2 and context.bounds.height > 2:
            self.__component._render(
                context,
                BoundingRectangle(
                    top=context.bounds.top + 1,
                    bottom=context.bounds.bottom - 1,
                    left=context.bounds.left + 1,
                    right=context.bounds.right - 1
                ),
            )

    def __get_color(self) -> str:
        return self.__color

    def __set_color(self, color: str) -> None:
        with self.lock:
            self.__drawn = False if not self.__drawn else (self.__color == color)
            self.__color = color

    color = property(__get_color, __set_color)

    def handle_input(self, event: "InputEvent") -> bool:
        return self.__component._handle_input(event)

    def __repr__(self) -> str:
        return "BorderComponent({})".format(repr(self.__component))


class ListComponent(Component):

    DIRECTION_TOP_TO_BOTTOM = 'top_to_bottom'
    DIRECTION_LEFT_TO_RIGHT = 'left_to_right'

    def __init__(self, components: List[Component], *, direction: str, size: Optional[int]=None) -> None:
        super().__init__()
        self.__components = components
        self.__size = size
        self.__direction = direction

    @property
    def dirty(self) -> bool:
        return any(component.dirty for component in self.__components)

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        perpendicular = 0
        element_size = self.__get_size(None)
        if element_size is None:
            return None

        for component in self.__components:
            innerbounds = component.bounds
            if innerbounds is None:
                return None

            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                perpendicular = max(perpendicular, innerbounds.width)
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                perpendicular = max(perpendicular, innerbounds.height)
            else:
                raise ComponentException("Invalid direction {}".format(self.__direction))

        if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
            return BoundingRectangle(
                top=0,
                bottom=len(self.__components) * element_size,
                left=0,
                right=perpendicular,
            )
        elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
            return BoundingRectangle(
                top=0,
                bottom=perpendicular,
                left=0,
                right=len(self.__components) * element_size,
            )
        else:
            raise ComponentException("Invalid direction {}".format(self.__direction))

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        for component in self.__components:
            component._attach(scene, settings)

    def detach(self) -> None:
        for component in self.__components:
            component._detach()

    def tick(self) -> None:
        for component in self.__components:
            component.tick()

    def __get_size(self, context: Optional[RenderContext]) -> Optional[int]:
        if self.__size is None:
            if context is None:
                return None
            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                size = int(context.bounds.height / len(self.__components))
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                size = int(context.bounds.width / len(self.__components))
            else:
                raise ComponentException("Invalid direction {}".format(self.__direction))
        else:
            size = self.__size
        if size < 1:
            size = 1
        return size

    def render(self, context: RenderContext) -> None:
        if not self.__components:
            return

        size = self.__get_size(context)
        if size is None:
            raise Exception('Logic error!')

        offset = 0
        for component in self.__components:
            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                if offset >= context.bounds.height:
                    break

                componenttop = context.bounds.top + offset
                componentbottom = context.bounds.top + offset + size
                if componentbottom > context.bounds.bottom:
                    componentbottom = context.bounds.bottom

                bounds = BoundingRectangle(
                    top=componenttop,
                    bottom=componentbottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                )
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                if offset >= context.bounds.width:
                    break

                componentleft = context.bounds.left + offset
                componentright = context.bounds.left + offset + size
                if componentright > context.bounds.right:
                    componentright = context.bounds.right

                bounds = BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=componentleft,
                    right=componentright,
                )
            else:
                raise ComponentException("Invalid direction {}".format(self.__direction))

            offset += size
            component._render(context, bounds)

    def handle_input(self, event: "InputEvent") -> bool:
        for component in self.__components:
            handled = component._handle_input(event)
            if handled:
                return True
        return False

    def __repr__(self) -> str:
        return "ListComponent({}, direction={})".format(",".join(repr(c) for c in self.__components), self.__direction)


class StickyComponent(Component):

    LOCATION_TOP = 'top'
    LOCATION_BOTTOM = 'bottom'
    LOCATION_LEFT = 'left'
    LOCATION_RIGHT = 'right'

    def __init__(self, stickycomponent: Component, othercomponent: Component, *, location: str, size: int) -> None:
        super().__init__()
        self.__components = [stickycomponent, othercomponent]
        self.__size = size
        self.__location = location

    @property
    def dirty(self) -> bool:
        return any(component.dirty for component in self.__components)

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        stickybounds, otherbounds = self.__components[0].bounds, self.__components[1].bounds
        if stickybounds is None or otherbounds is None:
            return None

        if self.__location in [self.LOCATION_TOP, self.LOCATION_BOTTOM]:
            return BoundingRectangle(
                top=0,
                bottom=otherbounds.height + self.__size,
                left=0,
                right=max(stickybounds.width, otherbounds.width),
            )
        elif self.__location in [self.LOCATION_LEFT, self.LOCATION_RIGHT]:
            return BoundingRectangle(
                top=0,
                bottom=max(stickybounds.height, otherbounds.height),
                left=0,
                right=otherbounds.width + self.__size,
            )
        else:
            raise ComponentException("Invalid location {}".format(self.__location))

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        for component in self.__components:
            component._attach(scene, settings)

    def detach(self) -> None:
        for component in self.__components:
            component._detach()

    def tick(self) -> None:
        for component in self.__components:
            component.tick()

    def __get_size(self) -> int:
        size = self.__size
        if size < 1:
            size = 1
        return size

    def render(self, context: RenderContext) -> None:
        size = self.__get_size()

        # Set up the bounds for the sticky component then the other component.
        # Has the same traversal order as self.__components on purpose.
        if self.__location == self.LOCATION_TOP:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.top + size,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top + size,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                )
            ]
        elif self.__location == self.LOCATION_BOTTOM:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.bottom - size,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom - size,
                    left=context.bounds.left,
                    right=context.bounds.right,
                )
            ]
        elif self.__location == self.LOCATION_LEFT:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.left + size,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left + size,
                    right=context.bounds.right,
                )
            ]
        elif self.__location == self.LOCATION_RIGHT:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.right - size,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right - size,
                )
            ]
        else:
            raise ComponentException("Invalid location {}".format(self.__location))

        for i in range(len(self.__components)):
            component = self.__components[i]
            cbounds = bounds[i]
            if cbounds.width > 0 and cbounds.height > 0:
                component._render(context, cbounds)

    def handle_input(self, event: "InputEvent") -> bool:
        for component in self.__components:
            handled = component._handle_input(event)
            if handled:
                return True
        return False

    def __repr__(self) -> str:
        return "StickyComponent({}, location={})".format(",".join(repr(c) for c in self.__components), self.__location)


class PaddingComponent(Component):

    def __init__(self, component: Component, **kwargs) -> None:
        super().__init__()
        self.__component = component
        self.__leftpad = 0
        self.__rightpad = 0
        self.__toppad = 0
        self.__bottompad = 0

        if 'padding' in kwargs:
            self.__leftpad = self.__rightpad = self.__toppad = self.__bottompad = kwargs['padding']
        if 'verticalpadding' in kwargs:
            self.__toppad = self.__bottompad = kwargs['verticalpadding']
        if 'horizontalpadding' in kwargs:
            self.__leftpad = self.__rightpad = kwargs['horizontalpadding']
        if 'leftpadding' in kwargs:
            self.__leftpad = kwargs['leftpadding']
        if 'rightpadding' in kwargs:
            self.__rightpad = kwargs['rightpadding']
        if 'toppadding' in kwargs:
            self.__toppad = kwargs['toppadding']
        if 'bottompadding' in kwargs:
            self.__bottompad = kwargs['bottompadding']

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        innerbounds = self.__component.bounds
        if innerbounds is None:
            return None
        return BoundingRectangle(
            top=0,
            bottom=(innerbounds.height + self.__toppad + self.__bottompad) if (innerbounds.height > 0) else 0,
            left=0,
            right=(innerbounds.width + self.__leftpad + self.__rightpad) if (innerbounds.width > 0) else 0,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        bounds = BoundingRectangle(
            top=context.bounds.top + self.__toppad,
            bottom=context.bounds.bottom - self.__bottompad,
            left=context.bounds.left + self.__leftpad,
            right=context.bounds.right - self.__rightpad,
        )

        if bounds.width <= 0 or bounds.height <= 0:
            return

        self.__component._render(context, bounds)

    def handle_input(self, event: "InputEvent") -> bool:
        return self.__component._handle_input(event)

    def __repr__(self) -> str:
        return "PaddingComponent({})".format(repr(self.__component))


class DialogBoxComponent(Component):

    def __init__(self, text: str, options: Tuple[str, Callable[[], None]], *, padding: int = 5) -> None:
        super().__init__()
        self.__text = text
        self.__padding = padding

        buttons = []
        def __cb(button, option, callback):
            if button == Buttons.LEFT or button == Buttons.KEY:
                callback(self, option)

        for option, callback in options:
            text, hotkey = _text_to_hotkeys(option)
            entry = ButtonComponent(text, formatted=True).on_click(
                lambda component, button, option=option, callback=callback: __cb(button, option, callback),
            )
            if hotkey is not None:
                entry = entry.set_hotkey(hotkey)
            buttons.append(PaddingComponent(entry, horizontalpadding=1))

        self.__component = PaddingComponent(
            BorderComponent(
                PaddingComponent(
                    StickyComponent(
                        ListComponent(buttons, direction=ListComponent.DIRECTION_LEFT_TO_RIGHT),
                        LabelComponent(self.__text),
                        size=3,
                        location=StickyComponent.LOCATION_BOTTOM,
                    ),
                    padding=1,
                ),
            ),
            padding=self.__padding,
        )

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__component._render(context, context.bounds)

    def handle_input(self, event: "InputEvent") -> bool:
        self.__component._handle_input(event)
        # Swallow events, since we don't want this to be closeable or to allow clicks
        # behind it.
        return True

    def __repr__(self) -> str:
        return "DialogBoxComponent(text={})".format(self.__text)


class MenuEntryComponent(HotkeyableComponent, ClickableComponent, Component):

    def __init__(self, text: str = "", *, expandable: bool = False) -> None:
        super().__init__()
        self.__text = text
        self.__expandable = expandable
        self.__rendered = False
        self.__animating = False
        self.__animation_spot = 0

    def render(self, context: RenderContext) -> None:
        context.clear()
        invert = self.__animating and (self.__animation_spot & 1) != 0
        if invert:
            # Fill the entire label so that it is fully inverted
            for line in range(context.bounds.height):
                context.draw_string(line, 0, " " * context.bounds.width, invert=True)
        else:
            context.clear()
        if invert:
            pre = "<invert>"
            post = "</invert>"
        else:
            pre = ""
            post = ""
        context.draw_formatted_string(0, 0, pre + " " + self.__text + " " + post)
        if self.__expandable:
            context.draw_formatted_string(0, context.bounds.width - 2, pre + " >" + post)
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=1,
            left=0,
            right=RenderContext.formatted_string_length(self.__text) + (3 if self.__expandable else 2),
        )

    def tick(self) -> None:
        self.__animation_spot += 1
        if self.__animating:
            self.__rendered = False

    def __get_animating(self) -> bool:
        return self.__animating

    def __set_animating(self, animating: bool) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__animating == animating)
            self.__animating = animating
            self.__animation_spot = 1

    animating = property(__get_animating, __set_animating)

    @property
    def text(self) -> str:
        return self.__text

    def __repr__(self) -> str:
        return "MenuEntryComponent(text={})".format(self.__text)


class MenuSeparatorComponent(Component):

    def __init__(self) -> None:
        super().__init__()
        self.__rendered = False

    def render(self, context: RenderContext) -> None:
        context.clear()
        context.draw_string(0, 0, ("\u2500" if Settings.enable_unicode else "-") * context.bounds.width)
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=1,
            left=0,
            right=0,
        )

    def __repr__(self) -> str:
        return "MenuSeparatorComponent()"


class PopoverMenuComponent(Component):

    def __init__(self, options: List[Tuple[str, Any]], *, animated: bool = False) -> None:
        super().__init__()
        self.__parent = None
        self.__children = []
        self.__animated = animated
        self.__closecb = None
        self.__closedelay = 0

        entries = []
        def __cb(component, button, option, callback):
            if self.__is_closing():
                return
            if button == Buttons.LEFT or button == Buttons.KEY:
                if self.__animated:
                    def __closeaction():
                        callback(self, option)
                        self.__close()
                    # Delayed close
                    component.animating = True
                    self.__closecb = __closeaction
                    self.__closedelay = 12
                else:
                    callback(self, option)
                    self.__close()

        def __new_menu(button, position, entries):
            if button == Buttons.LEFT or button == Buttons.KEY:
                menu = PopoverMenuComponent(entries, animated=self.__animated)
                menu.__parent = self
                self.register(menu, menu.bounds.offset(position, self.bounds.width))
                self.__children.append(menu)

        position = 0
        for option, callback in options:
            position += 1
            if option == "-":
                # Separator
                entries.append(MenuSeparatorComponent())
            elif isinstance(callback, list):
                # Submenu
                text, hotkey = _text_to_hotkeys(option)
                entry = MenuEntryComponent(text, expandable=True).on_click(
                    lambda component, button, position=position, entries=callback: __new_menu(button, position - 1, entries)
                )
                if hotkey is not None:
                    entry = entry.set_hotkey(hotkey)
                entries.append(entry)
            else:
                # Menu Entry
                text, hotkey = _text_to_hotkeys(option)
                entry = MenuEntryComponent(text).on_click(
                    lambda component, button, option=option, callback=callback: __cb(component, button, option, callback)
                )
                if hotkey is not None:
                    entry = entry.set_hotkey(hotkey)
                entries.append(entry)

        self.__component = BorderComponent(
            ListComponent(
                entries,
                direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                size=1,
            ),
        )
        self.__entries = entries

    def __close(self, *, close_parent: bool = True) -> None:
        self.unregister(self)
        if self.__parent is not None and close_parent:
            self.__parent.__close()
        for child in self.__children:
            # Kill our link so we don't recurse indefinitely
            child.__parent = None
            child.__close()

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=len(self.__entries) + 2,
            left=0,
            right=max(e.bounds.width for e in self.__entries) + 2,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        if self.__animated and self.__closedelay > 0:
            self.__closedelay -= 1
        if self.__closedelay == 0 and self.__closecb is not None:
            self.__closecb()
            self.__closecb = None
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__component._render(context, context.bounds)

    def __is_closing(self) -> bool:
        if self.__closecb is not None:
            return True
        if self.__parent is not None and self.__parent.__closecb is not None:
            return True
        for child in self.__children:
            if child.__closecb is not None:
                return True
        return False

    def handle_input(self, event: "InputEvent") -> bool:
        # If we're closing, swallow ALL inputs so we can't double-choose
        if self.__is_closing():
            return True

        handled = self.__component._handle_input(event)
        if self.__parent is not None:
            # Allow closing submenus by clicking other menu entries.
            if isinstance(event, DefocusInputEvent):
                self.__close(close_parent=False)
            # Treat mouse events as handled, since we don't want to close on
            # border clicks which are otherwise unhandled.
            if isinstance(event, MouseInputEvent):
                handled = True

            # Top level will handle outside clicks
            return handled

        if not handled:
            # Make sure that we close if we're clicked out of or escape is pressed.
            if isinstance(event, KeyboardInputEvent):
                if event.character == Keys.ESCAPE:
                    self.__close()
            elif isinstance(event, DefocusInputEvent):
                self.__close()

        # Swallow events, since we don't want this to be closeable or to allow clicks
        # behind it.
        return True

    def __repr__(self) -> str:
        return "PopoverMenuComponent({})".format(",".join(self.__entries))


class MonochromePictureComponent(Component):

    SIZE_FULL = "SIZE_FULL"
    SIZE_HALF = "SIZE_HALF"

    def __init__(self, data: List[List[bool]], *, size: Optional[str] = None, color: Optional[str] = None) -> None:
        super().__init__()
        self.__color = color or Color.NONE
        self.__size = size or self.SIZE_FULL
        if self.__size == self.SIZE_HALF and not Settings.enable_unicode:
            raise ComponentException("Unicode is not enabled, cannot use {} drawing style!".format(self.__size))
        self.__rendered = False
        self.__set_data_impl(data)

    @property
    def bounds(self) -> BoundingRectangle:
        if self.__size == self.SIZE_FULL:
            return BoundingRectangle(
                top=0,
                bottom=self.__height,
                left=0,
                right=self.__width,
            )
        elif self.__size == self.SIZE_HALF:
            return BoundingRectangle(
                top=0,
                bottom=int((self.__height + 1) / 2),
                left=0,
                right=int((self.__width + 1) / 2),
            )
        else:
            raise ComponentException("Invalid size {}".format(self.__size))

    def render(self, context: RenderContext) -> None:
        if self.__size == self.SIZE_FULL:
            for row in range(self.__height):
                for column in range(self.__width):
                    if Settings.enable_unicode:
                        char = "\u2588" if self.__data[row][column] else " "
                        invert = False
                    else:
                        invert = self.__data[row][column]
                        char = " "

                    context.draw_string(row, column, char, invert=invert, color=self.__color)

        if self.__size == self.SIZE_HALF:
            for row in range(int((self.__height + 1) / 2)):
                for column in range(int((self.__width + 1) / 2)):
                    # Grab a quad that represents what graphic to draw
                    quad = (
                        self.__data[row * 2][(column * 2):((column * 2) + 2)] +
                        self.__data[(row * 2) + 1][(column * 2):((column * 2) + 2)]
                    )
                    quad = "".join("1" if v else "0" for v in quad)

                    # Look it up
                    if quad == "0000":
                        char = " "
                    elif quad == "0001":
                        char = "\u2597"
                    elif quad == "0010":
                        char = "\u2598"
                    elif quad == "0011":
                        char = "\u2584"
                    elif quad == "0100":
                        char = "\u259D"
                    elif quad == "0101":
                        char = "\u2590"
                    elif quad == "0110":
                        char = "\u259E"
                    elif quad == "0111":
                        char = "\u259F"
                    elif quad == "1000":
                        char = "\u2598"
                    elif quad == "1001":
                        char = "\u259A"
                    elif quad == "1010":
                        char = "\u258C"
                    elif quad == "1011":
                        char = "\u2599"
                    elif quad == "1100":
                        char = "\u2580"
                    elif quad == "1101":
                        char = "\u259C"
                    elif quad == "1110":
                        char = "\u259B"
                    elif quad == "1111":
                        char = "\u2588"
                    else:
                        raise Exception("Logic error, invalid quad '{}'!".format(quad))

                    # Render it
                    context.draw_string(row, column, char, color=self.__color)

        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    def __get_data(self) -> List[List[bool]]:
        return self.__data

    def __set_data_impl(self, data: List[List[bool]]) -> None:
        self.__height = len(data)
        self.__width = max(len(p) for p in data)

        # Chunk our graphics data into groups of 2
        self.__data = data

        if self.__size == self.SIZE_HALF:
            # First, do the easy part of making sure the height is divisible by 2
            if (len(self.__data) & 1) == 1:
                self.__data = [*self.data, []]

            # Now, do the hard part of making sure the width is divisible by 2
            if (self.__width & 1) == 1:
                desired_width = self.__width + 1
            else:
                desired_width = self.__width
        else:
            desired_width = self.__width

        for i in range(len(self.__data)):
            if len(self.__data[i]) < desired_width:
                self.__data[i] = [*self.__data[i], *([False] * (desired_width - len(self.__data[i])))]

    def __set_data(self, data: List[List[bool]]) -> None:
        with self.lock:
            self.__set_data_impl(data)

    data = property(__get_data, __set_data)

    def __get_color(self) -> str:
        return self.__color

    def __set_color(self, color: str) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__color == color)
            self.__color = color

    color = property(__get_color, __set_color)
