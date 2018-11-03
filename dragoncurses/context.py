import curses

from contextlib import contextmanager
from _curses import error as CursesError
from typing import Generator, Optional, List, TypeVar


class BoundingRectangle:

    def __init__(self, *, top, bottom, left, right) -> None:
        self.top = top
        self.bottom = bottom
        self.left = left
        self.right = right

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, y: int, x: int) -> bool:
        return y >= self.top and y < self.bottom and x >= self.left and x < self.right

    def offset(self, y: int, x: int) -> "BoundingRectangle":
        return BoundingRectangle(
            top=self.top + y,
            bottom=self.bottom + y,
            left=self.left + x,
            right=self.right + x,
        )

    def clip(self, bounds: "BoundingRectangle"):
        return BoundingRectangle(
            top=min(max(self.top, bounds.top), bounds.bottom),
            bottom=max(min(self.bottom, bounds.bottom), bounds.top),
            left=min(max(self.left, bounds.left), bounds.right),
            right=max(min(self.right, bounds.right), bounds.left),
        )

    def __repr__(self) -> str:
        return "BoundingRectangle(top={}, bottom={}, left={}, right={})".format(self.top, self.bottom, self.left, self.right)


class Color:
    NONE = 'none'
    RED = 'red'
    YELLOW = 'yellow'
    GREEN = 'green'
    CYAN = 'cyan'
    BLUE = 'blue'
    MAGENTA = 'magenta'
    WHITE = 'white'
    BLACK = 'black'


class RenderContext:

    __color_table = {
        Color.NONE: 0,
    }

    def __init__(self, curses_context, off_y: int=0, off_x: int=0):
        self.__curses_context = curses_context
        self.__off_y = off_y
        self.__off_x = off_x

    def __get_color(self, forecolor: str, backcolor: str) -> int:
        colorkey = forecolor + ":" + backcolor
        if colorkey in self.__color_table:
            return self.__color_table[colorkey]

        # Figure out the next color slot
        nextcolor = len(self.__color_table.keys())

        # Figure out the curses color mapping
        if forecolor == Color.RED:
            forecurses = curses.COLOR_RED
        elif forecolor == Color.YELLOW:
            forecurses = curses.COLOR_YELLOW
        elif forecolor == Color.GREEN:
            forecurses = curses.COLOR_GREEN
        elif forecolor == Color.CYAN:
            forecurses = curses.COLOR_CYAN
        elif forecolor == Color.BLUE:
            forecurses = curses.COLOR_BLUE
        elif forecolor == Color.MAGENTA:
            forecurses = curses.COLOR_MAGENTA
        elif forecolor == Color.WHITE:
            forecurses = curses.COLOR_WHITE
        elif forecolor == Color.BLACK:
            forecurses = curses.COLOR_BLACK
        else:
            forecurses = -1

        if backcolor == Color.RED:
            backcurses = curses.COLOR_RED
        elif backcolor == Color.YELLOW:
            backcurses = curses.COLOR_YELLOW
        elif backcolor == Color.GREEN:
            backcurses = curses.COLOR_GREEN
        elif backcolor == Color.CYAN:
            backcurses = curses.COLOR_CYAN
        elif backcolor == Color.BLUE:
            backcurses = curses.COLOR_BLUE
        elif backcolor == Color.MAGENTA:
            backcurses = curses.COLOR_MAGENTA
        elif backcolor == Color.WHITE:
            backcurses = curses.COLOR_WHITE
        elif backcolor == Color.BLACK:
            backcurses = curses.COLOR_BLACK
        else:
            backcurses = -1

        # Map the color to the slot
        curses.init_pair(nextcolor, forecurses, backcurses)
        self.__color_table[colorkey] = nextcolor

        # Return the curses color mapping value
        return nextcolor

    @property
    def bounds(self) -> BoundingRectangle:
        height, width = self.__curses_context.getmaxyx()
        return BoundingRectangle(top=0, bottom=height, left=0, right=width)

    @property
    def location(self) -> BoundingRectangle:
        return self.bounds.offset(self.__off_y, self.__off_x)

    @contextmanager
    def clip(self, rect: BoundingRectangle) -> Generator["RenderContext", None, None]:
        rect = rect.clip(self.bounds)
        try:
            yield RenderContext(
                self.__curses_context.derwin(rect.height, rect.width, rect.top, rect.left),
                self.__off_y + rect.top,
                self.__off_x + rect.left,
            )
        except CursesError:
            pass

    def clear(self):
        height, width = self.__curses_context.getmaxyx()
        for y in range(height):
            self.draw_string(y, 0, " " * width)

    def draw_string(
        self,
        y: int,
        x: int,
        string: str,
        forecolor: str=Color.NONE,
        backcolor: str=Color.NONE,
        invert: bool=False,
        underline: bool=False,
    ) -> None:
        attributes = curses.color_pair(self.__get_color(forecolor, backcolor))
        if invert:
            attributes = attributes | curses.A_REVERSE
        if underline:
            attributes = attributes | curses.A_UNDERLINE

        try:
            self.__curses_context.addstr(y, x, string, attributes)
        except CursesError:
            pass

    @staticmethod
    def __split_formatted_string(string: str) -> List[str]:
        accumulator = []
        parts = []

        for ch in string:
            if ch == "<":
                if accumulator:
                    parts.append("".join(accumulator))
                    accumulator = []
                accumulator.append(ch)
            elif ch == ">":
                accumulator.append(ch)
                if accumulator[0] == "<":
                    parts.append("".join(accumulator))
                    accumulator = []
            else:
                accumulator.append(ch)

        if accumulator:
            parts.append("".join(accumulator))
        return parts

    @staticmethod
    def __sanitize(string: str) -> str:
        string = string.replace("&lt;", "<")
        string = string.replace("&lg;", ">")
        string = string.replace("&amp;", "&")
        return string

    def draw_formatted_string(
        self,
        y: int,
        x: int,
        string: str,
    ) -> None:
        displayed = False
        attributes = 0
        colors = [self.__get_color(Color.NONE, Color.NONE)]
        parts = RenderContext.__split_formatted_string(string)

        for part in parts:
            if part[:2] == "</" and part[-1:] == ">":
                # Close tag
                tag = part[2:-1].lower()
                if tag == "invert":
                    attributes = attributes & (~curses.A_REVERSE)
                elif tag == "underline":
                    attributes = attributes & (~curses.A_UNDERLINE)
                else:
                    splitcolors = tag.split(",")
                    while len(splitcolors) < 2:
                        splitcolors.append(Color.NONE)

                    color = self.__get_color(splitcolors[0], splitcolors[1])
                    if color == colors[-1] and len(colors) > 1:
                        colors = colors[:-1]
            elif part[:1] == "<" and part[-1:] == ">":
                # Open tag
                tag = part[1:-1].lower()
                if tag == "invert":
                    attributes = attributes | curses.A_REVERSE
                elif tag == "underline":
                    attributes = attributes | curses.A_UNDERLINE
                else:
                    splitcolors = tag.split(",")
                    while len(splitcolors) < 2:
                        splitcolors.append(Color.NONE)

                    colors.append(self.__get_color(splitcolors[0], splitcolors[1]))
            elif not displayed:
                # First display should be setting the text position
                displayed = True
                try:
                    self.__curses_context.addstr(y, x, RenderContext.__sanitize(part), attributes | curses.color_pair(colors[-1]))
                except CursesError:
                    break
            else:
                # The rest of the text displays should trail, for wrapping
                try:
                    self.__curses_context.addstr(RenderContext.__sanitize(part), attributes | curses.color_pair(colors[-1]))
                except CursesError:
                    break

    @staticmethod
    def formatted_string_length(
        string: str,
    ) -> int:
        # TODO: This isn't a very good place for this, but its close to the draw function so I dunno.
        length = 0
        parts = RenderContext.__split_formatted_string(string)

        for part in parts:
            if part[:1] == "<" and part[-1:] == ">":
                continue
            else:
                length += len(RenderContext.__sanitize(part))
        return length

    def clear(self) -> None:
        self.__curses_context.clear()

    def refresh(self) -> None:
        self.__curses_context.refresh()

    def getkey(self) -> Optional[str]:
        try:
            return self.__curses_context.getkey()
        except CursesError:
            return None
