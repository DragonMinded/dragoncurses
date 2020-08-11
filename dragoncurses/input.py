class Keys:
    ENTER = chr(10)
    ESCAPE = chr(27)
    SPACE = " "
    TAB = "\t"
    DELETE = "KEY_DC"
    BACKSPACE = "KEY_BACKSPACE"
    UP = "KEY_UP"
    DOWN = "KEY_DOWN"
    LEFT = "KEY_LEFT"
    RIGHT = "KEY_RIGHT"
    PGUP = "KEY_PPAGE"
    PGDN = "KEY_NPAGE"
    HOME = "KEY_HOME"
    END = "KEY_END"


class Buttons:
    LEFT = "LEFT"
    MIDDLE = "MIDDLE"
    RIGHT = "RIGHT"
    KEY = "KEY"


class Directions:
    UP = "UP"
    DOWN = "DOWN"


class InputEvent:
    pass


class KeyboardInputEvent(InputEvent):
    def __init__(self, character: str) -> None:
        self.character = character

    def __repr__(self) -> str:
        return "KeyboardInputEvent(character={})".format(self.character)


class MouseInputEvent(InputEvent):
    def __init__(self, x: int, y: int, button: str) -> None:
        self.x = x
        self.y = y
        self.button = button

    def __repr__(self) -> str:
        return "MouseInputEvent(x={}, y={}, button={})".format(self.x, self.y, self.button)


class ScrollInputEvent(InputEvent):
    def __init__(self, x: int, y: int, direction: str) -> None:
        self.x = x
        self.y = y
        self.direction = direction

    def __repr__(self) -> str:
        return "ScrollInputEvent(x={}, y={}, direction={})".format(self.x, self.y, self.direction)


class DefocusInputEvent(InputEvent):
    def __init__(self, button: str) -> None:
        self.button = button

    def __repr__(self) -> str:
        return "DefocusInputEvent(button={})".format(self.button)
