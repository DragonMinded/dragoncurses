import argparse
import sys
import time

from threading import Thread
from typing import List, Optional, Union, Any

from dragoncurses.component import (
    Component,
    DeferredInput,
    LabelComponent,
    BorderComponent,
    ButtonComponent,
    PaddingComponent,
    DialogBoxComponent,
    ListComponent,
    PopoverMenuComponent,
    StickyComponent,
    EmptyComponent,
    MonochromePictureComponent,
    PictureComponent,
)
from dragoncurses.context import Color, RenderContext
from dragoncurses.scene import Scene
from dragoncurses.loop import MainLoop, execute
from dragoncurses.input import (
    InputEvent,
    KeyboardInputEvent,
    ScrollInputEvent,
    Keys,
    Directions,
    Buttons,
)
from dragoncurses.settings import Settings


Settings.enable_unicode = True


clock = None
counter = None


class HelloWorldComponent(Component):
    def __init__(self) -> None:
        super().__init__()
        self.animation = 0  # type: Optional[int]

    def tick(self) -> None:
        animation = self.animation
        if animation is not None and animation > 0:
            self.animation = animation - 1
        else:
            self.animation = None

    def render(self, context: RenderContext) -> None:
        text = "Hello, world!"

        animation = self.animation
        if animation is None or animation == 0:
            context.draw_string(0, 0, text)
        else:
            context.draw_string(0, 0, text)
            context.draw_string(0, 13 - animation, text[13 - animation], invert=True)

    @property
    def dirty(self) -> bool:
        return self.animation is not None

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.SPACE:
                self.animation = 14
                return True
        return False


class ScrollTestComponent(Component):
    def __init__(self, global_capture: bool = True) -> None:
        super().__init__()
        self.__rendered = False
        self.__count = 0
        self.__global_capture = global_capture

    def render(self, context: RenderContext) -> None:
        context.clear()
        context.draw_string(
            0, 0, "Scroll {}!".format("anywhere" if self.__global_capture else "me")
        )
        context.draw_string(1, 0, str(self.__count))
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    def _deferred_scroll_up(self) -> bool:
        self.__count -= 1
        self.__rendered = False
        return True

    def _deferred_scroll_down(self) -> bool:
        self.__count += 1
        self.__rendered = False
        return True

    def handle_input(self, event: InputEvent) -> Union[bool, DeferredInput]:
        if isinstance(event, ScrollInputEvent):
            if not self.__global_capture:
                # If we are doing hover-scroll only, capture only
                # the mouse events when we hover.
                if self.location is not None:
                    if not self.location.contains(event.y, event.x):
                        return False
                if event.direction == Directions.UP:
                    return self._deferred_scroll_up()
                if event.direction == Directions.DOWN:
                    return self._deferred_scroll_down()
            else:
                # If we are doing global scroll, capture only if
                # we haven't handled the event elsewhere.
                if event.direction == Directions.UP:
                    return self._deferred_scroll_up
                if event.direction == Directions.DOWN:
                    return self._deferred_scroll_down

        return False


class RenderCounterComponent(Component):
    def __init__(self) -> None:
        super().__init__()
        self.__rendered = False
        self.__count = 0

    def render(self, context: RenderContext) -> None:
        self.__count += 1
        context.clear()
        context.draw_string(
            0,
            0,
            "Rendered {} time{}!".format(
                self.__count, ("" if self.__count == 1 else "s")
            ),
            wrap=True,
        )
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered


class WelcomeScene(Scene):
    def update_button(self, component: Component, button: Buttons) -> bool:
        if isinstance(component, ButtonComponent):
            component.text = "A <underline>b</underline>utton (pressed {}!)".format(
                button.name
            )
            component.textcolor = (
                Color.RED
                if button == Buttons.LEFT
                else Color.CYAN
                if button == Buttons.RIGHT
                else Color.YELLOW
            )
        return True

    def create(self) -> Component:
        global clock
        global counter

        picture = [
            [False, False, True, False, False],
            [False, True, True, True, False],
            [True, True, False, True, True],
            [False, True, True, True, False],
            [False, False, True, False, False],
        ]
        colorpicture = [
            [
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.BLACK,
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.WHITE,
                Color.YELLOW,
                Color.BLUE,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.BLUE,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
            ],
            [
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
            ],
            [
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.RED,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.RED,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.RED,
                Color.RED,
                Color.RED,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.BLACK,
                Color.WHITE,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.YELLOW,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.WHITE,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
            ],
            [
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
                Color.BLACK,
            ],
        ]

        clock = LabelComponent(get_current_time())
        counter = LabelComponent("Threads aren't working!")
        return StickyComponent(
            StickyComponent(
                clock,
                EmptyComponent(),
                location=StickyComponent.LOCATION_RIGHT,
                size=19,
            ),
            ListComponent(
                [
                    ListComponent(
                        [
                            HelloWorldComponent(),
                            RenderCounterComponent(),
                            ButtonComponent(
                                "A <underline>b</underline>utton (not pressed)",
                                formatted=True,
                            )
                            .on_click(self.update_button)
                            .set_hotkey("b"),
                            ListComponent(
                                [
                                    LabelComponent(
                                        "Testing <underline>1</underline>, <invert>2</invert>, 3!",
                                        formatted=True,
                                    ),
                                    LabelComponent(
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w",
                                        formatted=True,
                                    ),
                                    LabelComponent(
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                        "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w",
                                        formatted=True,
                                    ),
                                    LabelComponent(
                                        "<invert><red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w</invert>",
                                        formatted=True,
                                    ),
                                ],
                                direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                                size=1,
                            ),
                            EmptyComponent(),
                            LabelComponent("Some inverted text", invert=True),
                            ScrollTestComponent(),
                            counter,
                            BorderComponent(
                                ScrollTestComponent(global_capture=False),
                                style=BorderComponent.ASCII,
                            ),
                        ],
                        size=4,
                        direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                    ),
                    ListComponent(
                        [
                            PaddingComponent(
                                MonochromePictureComponent(
                                    picture,
                                    size=MonochromePictureComponent.SIZE_FULL,
                                    forecolor=Color.CYAN,
                                    backcolor=Color.BLUE,
                                ),
                                padding=2,
                            ),
                            PaddingComponent(
                                MonochromePictureComponent(
                                    picture,
                                    size=MonochromePictureComponent.SIZE_HALF,
                                    forecolor=Color.MAGENTA,
                                    backcolor=Color.WHITE,
                                ),
                                padding=2,
                            )
                            if Settings.enable_unicode
                            else EmptyComponent(),
                        ],
                        direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                    ),
                    ListComponent(
                        [
                            PaddingComponent(
                                PictureComponent(
                                    colorpicture,
                                    size=PictureComponent.SIZE_FULL,
                                ),
                                padding=2,
                            ),
                            PaddingComponent(
                                PictureComponent(
                                    colorpicture,
                                    size=PictureComponent.SIZE_HALF,
                                ),
                                padding=2,
                            )
                            if Settings.enable_unicode
                            else EmptyComponent(),
                        ],
                        direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                    ),
                    BorderComponent(
                        LabelComponent(
                            "centered text\n\nthis is a really long string that will be wrapped",
                            centered=True,
                        ),
                        style=BorderComponent.ASCII,
                    ),
                    BorderComponent(
                        LabelComponent(
                            "formatted <red>centered</red> <blue>text</blue>\n\nthis is a really long string that will be <underline>wrapped</underline>",
                            formatted=True,
                            centered=True,
                        ),
                        style=BorderComponent.ASCII,
                    ),
                ],
                size=30,
                direction=ListComponent.DIRECTION_LEFT_TO_RIGHT,
            ),
            location=StickyComponent.LOCATION_BOTTOM,
            size=1,
        )

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character in [Keys.ESCAPE, "q"]:
                self.register_component(
                    DialogBoxComponent(
                        "Are you sure you want to exit?",
                        [
                            ("&Yes", lambda component, option: self.main_loop.exit()),
                            (
                                "&No",
                                lambda component, option: self.unregister_component(
                                    component
                                ),
                            ),
                        ],
                        escape_option="&No",
                    )
                )

                return True
            if event.character == Keys.ENTER:
                self.main_loop.change_scene(TestScene)
                return True
        return False


class TestScene(Scene):
    def pop_menu(self, component: Component, button: Buttons) -> bool:
        if not isinstance(component, ButtonComponent):
            raise Exception("Logic error, somehow got callback with wrong component?")
        localcomponent: ButtonComponent = component

        def text(text: str) -> None:
            localcomponent.text = text

        def color(color: Color) -> None:
            localcomponent.textcolor = color

        def border(color: Color) -> None:
            localcomponent.bordercolor = color

        menu = PopoverMenuComponent(
            [
                (
                    "Set &Text",
                    [
                        (
                            "&Default",
                            lambda menuentry, option: text(
                                "A popover <underline>m</underline>enu"
                            ),
                        ),
                        (
                            "&Others",
                            [
                                (
                                    "Option &1",
                                    lambda menuentry, option: text(
                                        "A better <underline>m</underline>enu"
                                    ),
                                ),
                                (
                                    "Option &2",
                                    lambda menuentry, option: text(
                                        "A great <underline>m</underline>enu"
                                    ),
                                ),
                            ],
                        ),
                        (
                            "Testing",
                            [
                                (
                                    "Option &3",
                                    lambda menuentry, option: text(
                                        "A bad <underline>m</underline>enu"
                                    ),
                                ),
                                (
                                    "Option &4",
                                    lambda menuentry, option: text(
                                        "A worse <underline>m</underline>enu"
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
                ("-", None),
                ("Set &Red", lambda menuentry, option: color(Color.RED)),
                ("Set &Yellow", lambda menuentry, option: color(Color.YELLOW)),
                ("Set &Green", lambda menuentry, option: color(Color.GREEN)),
                ("Set &Blue", lambda menuentry, option: color(Color.BLUE)),
                ("Set &Purple", lambda menuentry, option: color(Color.MAGENTA)),
                ("-", None),
                (
                    "Set Border",
                    [
                        ("Regular", lambda menuentry, option: border(Color.NONE)),
                        ("Cyan", lambda menuentry, option: border(Color.CYAN)),
                    ],
                ),
            ],
            animated=True,
        )
        localcomponent.register(
            menu,
            menu.bounds.offset(3, 0),
        )
        return True

    def create(self) -> Component:
        return ListComponent(
            [
                ListComponent(
                    [
                        LabelComponent("Horizontal 1"),
                        ListComponent(
                            [
                                LabelComponent("Horizontal 2"),
                                ButtonComponent(
                                    "A popover <underline>m</underline>enu",
                                    textcolor=Color.MAGENTA,
                                    formatted=True,
                                )
                                .on_click(self.pop_menu)
                                .set_hotkey("m"),
                            ],
                            direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                            size=3,
                        ),
                        LabelComponent("Horizontal 3"),
                    ],
                    direction=ListComponent.DIRECTION_LEFT_TO_RIGHT,
                ),
                LabelComponent(
                    "This is a label with a lot of stuff that should word-wrap!\n"
                    + "I've placed a few tabs and stuff here so we know it works!\n"
                    + "What about some tabs? Let's do some tab-related activities~"
                ),
                PaddingComponent(
                    BorderComponent(
                        LabelComponent("Label 2!"), bordercolor=Color.GREEN
                    ),
                    padding=2,
                ),
                ListComponent(
                    [
                        BorderComponent(
                            LabelComponent("Label 3!"),
                            style=BorderComponent.ASCII,
                            bordercolor=Color.CYAN,
                        ),
                        BorderComponent(
                            LabelComponent("Label 4!"), style=BorderComponent.SINGLE
                        )
                        if Settings.enable_unicode
                        else EmptyComponent(),
                        BorderComponent(
                            LabelComponent("Label 5!"), style=BorderComponent.DOUBLE
                        )
                        if Settings.enable_unicode
                        else EmptyComponent(),
                    ],
                    direction=ListComponent.DIRECTION_LEFT_TO_RIGHT,
                ),
                LabelComponent(
                    "This is a <underline>label</underline> with a <invert>lot</invert> of stuff that should word-wrap!\n"
                    + "I've placed a <invert>few <green>tabs</green></invert> and stuff here so we know it works!\n"
                    + "What about some tabs? Let's do some <red>tab-related</red> activities~",
                    formatted=True,
                ),
                RenderCounterComponent(),
            ],
            direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
        )

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character in [Keys.ESCAPE, "q"]:
                self.register_component(
                    DialogBoxComponent(
                        "Are you sure you want to exit?",
                        [
                            ("&Yes", lambda component, option: self.main_loop.exit()),
                            (
                                "&No",
                                lambda component, option: self.unregister_component(
                                    component
                                ),
                            ),
                        ],
                        escape_option="&No",
                    )
                )

                return True
            if event.character == Keys.ENTER:
                self.main_loop.change_scene(WelcomeScene)
                return True
        return False


def get_current_time() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def idle(mainloop: MainLoop) -> None:
    global clock

    if clock is not None:
        clock.text = get_current_time()


def thread(exit: List[Any]) -> None:
    global counter
    val = 0

    while len(exit) == 0:
        if counter is not None:
            counter.text = "Threading works!\nCounter is {}".format(val)
            val += 1


def main() -> int:
    parser = argparse.ArgumentParser(description="A simple curses UI library.")
    parser.parse_args()

    exitthread: List[str] = []
    t = Thread(target=thread, args=(exitthread,))
    t.start()

    # Run the main program loop, starting with the welcome scene
    execute(WelcomeScene, idle_callback=idle, realtime=True)

    exitthread.append("exit")

    return 0


if __name__ == "__main__":
    sys.exit(main())
