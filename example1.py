import argparse
import curses
import os
import sys
import time

from typing import List, Optional

from dragoncurses.component import (
    Component,
    LabelComponent,
    BorderComponent,
    ButtonComponent,
    PaddingComponent,
    DialogBoxComponent,
    ListComponent,
    PopoverMenuComponent,
    StickyComponent,
    EmptyComponent,
)
from dragoncurses.context import Color, RenderContext, BoundingRectangle
from dragoncurses.scene import Scene
from dragoncurses.loop import MainLoop, loop_config
from dragoncurses.input import InputEvent, KeyboardInputEvent, Keys


clock = None


class HelloWorldComponent(Component):

    def __init__(self) -> None:
        self.animation = 0  # type: Optional[int]

    def tick(self) -> None:
        if self.animation is not None and self.animation > 0:
            self.animation -= 1
        else:
            self.animation = None

    def render(self, context: RenderContext) -> None:
        text = "Hello, world!"

        if self.animation is None or self.animation == 0:
            context.draw_string(0, 0, text)
        else:
            context.draw_string(0, 0, text)
            context.draw_string(0, 13 - self.animation, text[13 - self.animation], invert=True)

    @property
    def dirty(self) -> bool:
        return self.animation is not None

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.SPACE:
                self.animation = 14
                return True
        return False


class WelcomeScene(Scene):

    def update_button(self, component: Component, button: str) -> None:
        component.text = "A <underline>b</underline>utton (pressed {}!)".format(button)
        component.textcolor = Color.RED if button == "LEFT" else Color.CYAN if button == "RIGHT" else Color.YELLOW

    def create(self) -> List[Component]:
        global clock
        clock = LabelComponent(get_current_time())
        return [
            StickyComponent(
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
                                ButtonComponent("A <underline>b</underline>utton (not pressed)", formatted=True).on_click(self.update_button).set_hotkey('b'),
                                ListComponent(
                                    [
                                        LabelComponent("Testing <underline>1</underline>, <invert>2</invert>, 3!", formatted=True),
                                        LabelComponent("<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w", formatted=True),
                                        LabelComponent(
                                            "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                            "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                            "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                            "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w"
                                            "<red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w",
                                            formatted=True
                                        ),
                                        LabelComponent("<invert><red>r</red><yellow>a</yellow><green>i</green><cyan>n</cyan><blue>b</blue><magenta>o</magenta>w</invert>", formatted=True),
                                    ],
                                    direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                                    size=1,
                                ),
                                EmptyComponent(),
                                LabelComponent("Some inverted text", invert=True)
                            ],
                            size=4,
                            direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                        ),
                    ],
                    size = 30,
                    direction = ListComponent.DIRECTION_LEFT_TO_RIGHT,
                ),
                location=StickyComponent.LOCATION_BOTTOM,
                size=1,
            ),
        ]

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.ESCAPE:
                self.register_component(
                    DialogBoxComponent(
                        'Are you sure you want to exit?',
                        [
                            ('&Yes', lambda component, option: self.main_loop.exit()),
                            ('&No', lambda component, option: self.unregister_component(component)),
                        ],
                    )
                )

                return True
            if event.character == Keys.ENTER:
                self.main_loop.change_scene(TestScene)
                return True
        return False


class TestScene(Scene):

    def pop_menu(self, component: Component, button: str) -> None:
        def text(text):
            component.text = text
        def color(color):
            component.textcolor = color
        def border(color):
            component.bordercolor = color

        menu = PopoverMenuComponent(
            [
                ('Set &Text', [
                    ('&Default', lambda menuentry, option: text('A ghetto <underline>m</underline>enu')),
                    ('&Others', [
                        ('Option &1', lambda menuentry, option: text('A better <underline>m</underline>enu')),
                        ('Option &2', lambda menuentry, option: text('A great <underline>m</underline>enu')),
                    ]),
                    ('Testing', [
                        ('Option &3', lambda menuentry, option: text('A bad <underline>m</underline>enu')),
                        ('Option &4', lambda menuentry, option: text('A worse <underline>m</underline>enu')),
                    ]),
                ]),
                ('-', None),
                ('Set &Red', lambda menuentry, option: color(Color.RED)),
                ('Set &Yellow', lambda menuentry, option: color(Color.YELLOW)),
                ('Set &Green', lambda menuentry, option: color(Color.GREEN)),
                ('Set &Blue', lambda menuentry, option: color(Color.BLUE)),
                ('Set &Purple', lambda menuentry, option: color(Color.MAGENTA)),
                ('-', None),
                ('Set Border', [
                    ('Regular', lambda menuentry, option: border(Color.NONE)),
                    ('Cyan', lambda menuentry, option: border(Color.CYAN)),
                ]),
            ],
            animated=True,
        )
        component.register(
            menu,
            menu.bounds.offset(3, 0),
        )

    def create(self) -> List[Component]:
        return [
            ListComponent(
                [
                    ListComponent(
                        [
                            LabelComponent("Horizontal 1"),
                            ListComponent(
                                [
                                    LabelComponent("Horizontal 2"),
                                    ButtonComponent("A ghetto <underline>m</underline>enu", textcolor=Color.MAGENTA, formatted=True).on_click(self.pop_menu).set_hotkey('m'),
                                    LabelComponent(""),
                                ],
                                direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                            ),
                            LabelComponent("Horizontal 3"),
                        ],
                        direction = ListComponent.DIRECTION_LEFT_TO_RIGHT,
                    ),
                    LabelComponent("Label 1!"),
                    PaddingComponent(BorderComponent(LabelComponent("Label 2!"), color=Color.GREEN), padding=2),
                    BorderComponent(LabelComponent("Label 3!"), style=BorderComponent.LINES, color=Color.CYAN),
                    LabelComponent("Label 4!"),
                ],
                direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
            ),
        ]

    def handle_input(self, event: InputEvent) -> bool:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.ESCAPE:
                self.register_component(
                    DialogBoxComponent(
                        'Are you sure you want to exit?',
                        [
                            ('&Yes', lambda component, option: self.main_loop.exit()),
                            ('&No', lambda component, option: self.unregister_component(component)),
                        ],
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


def main() -> int:
    parser = argparse.ArgumentParser(description="A simple curses UI library.")
    args = parser.parse_args()

    def wrapped(context) -> None:
        # Run the main program loop
        with loop_config(context):
            loop = MainLoop(context, {}, idle)
            loop.change_scene(WelcomeScene)
            loop.run()

    os.environ.setdefault('ESCDELAY', '0')
    curses.wrapper(wrapped)
    return 0


if __name__ == "__main__":
    sys.exit(main())