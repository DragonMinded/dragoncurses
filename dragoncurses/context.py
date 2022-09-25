import curses
from enum import Enum, auto

from contextlib import contextmanager
from _curses import error as CursesError
from typing import Any, Dict, Generator, Optional, List


CursesContext = Any


class BoundingRectangle:
    def __init__(self, *, top: int, bottom: int, left: int, right: int) -> None:
        self.top: int = top
        self.bottom: int = bottom
        self.left: int = left
        self.right: int = right

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

    def clip(self, bounds: "BoundingRectangle") -> "BoundingRectangle":
        return BoundingRectangle(
            top=min(max(self.top, bounds.top), bounds.bottom),
            bottom=max(min(self.bottom, bounds.bottom), bounds.top),
            left=min(max(self.left, bounds.left), bounds.right),
            right=max(min(self.right, bounds.right), bounds.left),
        )

    def __repr__(self) -> str:
        return "BoundingRectangle(top={}, bottom={}, left={}, right={})".format(
            self.top, self.bottom, self.left, self.right
        )


class Color(Enum):
    NONE = auto()
    RED = auto()
    YELLOW = auto()
    GREEN = auto()
    CYAN = auto()
    BLUE = auto()
    MAGENTA = auto()
    WHITE = auto()
    BLACK = auto()


class RenderContext:

    __color_table: Dict[str, int] = {
        Color.NONE.name: 0,
    }

    def __init__(self, curses_context: CursesContext, off_y: int = 0, off_x: int = 0):
        self.__curses_context = curses_context
        self.__off_y = off_y
        self.__off_x = off_x

    def __get_color(self, forecolor: Color, backcolor: Color) -> int:
        colorkey = forecolor.name + ":" + backcolor.name
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
                self.__curses_context.derwin(
                    rect.height, rect.width, rect.top, rect.left
                ),
                self.__off_y + rect.top,
                self.__off_x + rect.left,
            )
        except CursesError:
            pass

    @staticmethod
    def __get_wrap_points(
        string: str, starty: int, startx: int, bounds: BoundingRectangle
    ) -> List[int]:
        locations: List[int] = []
        processed: int = 0

        while string:
            # If we've wrapped once we start at the beginning of the line. Otherwise, we
            # start where the start of the string is.
            width = bounds.width if locations else (bounds.width - starty)
            if len(string) <= width:
                # Base case where we have enough room to draw the rest of the string.
                for i in range(len(string)):
                    if string[i] == "\n":
                        locations.append(processed + i + 1)
                break

            # Find the closest wrap point (either a space/control character or a dash).
            # We constrain our search to things that could wrap in the next line, plus
            # the single character after in case it is a wrap character. That way if we
            # were about to wrap and the next character would have wrapped us, we don't
            # print it as the first character on the next line.
            possibilities = []
            i = 0
            maxiter = min(len(string), (width + 1))
            while i < maxiter:
                if string[i] == "\n":
                    # This is a manual wrap, set our location to one past it (we will
                    # rely on the fact that its still printable and let curses do whatever).
                    # Since we finish wrapping this chunk at this line, don't consider any
                    # further possibilities.
                    possibilities.append(i + 1)
                    break
                elif string[i] in [" ", "\t"]:
                    # We wrap at the end of the space block, so find the first non-space
                    # character and set that as the wrap point.
                    for j in range(i, len(string)):
                        if string[j] not in [" ", "\t"]:
                            possibilities.append(j)
                            i = j
                            break
                    else:
                        # We didn't find anything, assume that spacing is the end of the string.
                        break
                elif string[i] == "-" and i < width:
                    # We wrap after the dash as long as there isn't another dash and the
                    # characters before and after it are alphanumeric (word-break detection).
                    # We also don't want to wrap if this would have been the character on the
                    # next line (this is unlike the whitespace wrapping above) so we check the
                    # width.
                    if i > 0 and i < (len(string) - 1):
                        if string[i - 1].isalnum() and string[i + 1].isalnum():
                            possibilities.append(i + 1)
                    i += 1
                else:
                    # Regular character, don't care
                    i += 1

            if possibilities:
                last = possibilities[-1]
                locations.append(processed + last)
                string = string[last:]
                processed += last
            else:
                # Didn't find anywhere to wrap, so we give up, wrap at the exact point of
                # overflow.
                locations.append(processed + width)
                string = string[width:]
                processed += width

        return locations

    def draw_string(
        self,
        y: int,
        x: int,
        string: str,
        *,
        forecolor: Color = Color.NONE,
        backcolor: Color = Color.NONE,
        invert: bool = False,
        underline: bool = False,
        wrap: bool = False,
        centered: bool = False,
    ) -> None:
        attributes = curses.color_pair(self.__get_color(forecolor, backcolor))
        if invert:
            attributes = attributes | curses.A_REVERSE
        if underline:
            attributes = attributes | curses.A_UNDERLINE

        if wrap:
            # Wrap points takes care of carriage returns, so neuter curses ability
            # to react to them.
            wrap_points = RenderContext.__get_wrap_points(string, y, x, self.bounds)
            string = string.replace("\n", " ")
        else:
            wrap_points = []

        # Make sure we process the last bit of the string by always having a hanging
        # wrap point.
        if not wrap_points or wrap_points[-1] != len(string):
            wrap_points.append(len(string))
        last_pos = 0

        # Display each chunk in the proper spot.
        for wrap_point in wrap_points:
            chunk = string[last_pos:wrap_point]
            if x == 0:
                chunklen = len(chunk)

                # Calculate centering for this chunk
                offset = 0
                if centered:
                    if chunklen < self.bounds.width:
                        offset = int((self.bounds.width - chunklen) / 2)
            else:
                # Disable centering for this line if we start on a non-zero x
                offset = 0

            # Display it!
            try:
                self.__curses_context.addstr(y, x + offset, chunk, attributes)
            except CursesError:
                pass
            last_pos = wrap_point
            y += 1
            x = 0

    @staticmethod
    def __split_formatted_string(string: str) -> List[str]:
        accumulator: List[str] = []
        parts: List[str] = []

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
        string = string.replace("&gt;", ">")
        string = string.replace("&amp;", "&")
        return string

    def draw_formatted_string(
        self,
        y: int,
        x: int,
        string: str,
        *,
        wrap: bool = False,
        centered: bool = False,
    ) -> None:
        attributes = 0
        last_pos = 0
        length_part = 0
        colors = [self.__get_color(Color.NONE, Color.NONE)]
        parts = RenderContext.__split_formatted_string(string)
        rawtext = "".join(
            RenderContext.__sanitize(part)
            for part in parts
            if not (part[:1] == "<" and part[-1:] == ">")
        )
        if wrap:
            wrap_points = RenderContext.__get_wrap_points(rawtext, y, x, self.bounds)
            if wrap_points:
                lengths = [
                    wrap_points[0] - x,
                    *[
                        (wrap_points[i] - wrap_points[i - 1])
                        for i in range(1, len(wrap_points))
                    ],
                    len(rawtext) - wrap_points[-1],
                ]
            else:
                lengths = [len(rawtext)]

            # Only center first line if we're starting at the leftmost column.
            if centered and x == 0:
                if lengths[length_part] < self.bounds.width:
                    x += int((self.bounds.width - lengths[length_part]) / 2)
        else:
            wrap_points = []
            lengths = []
            offset = 0

            # Disable centering if we start from non-zero offset.
            if x == 0:
                chunklen = len(rawtext)
                if centered:
                    if chunklen < self.bounds.width:
                        offset = int((self.bounds.width - chunklen) / 2)

            self.__curses_context.move(y, x + offset)

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
                        splitcolors.append(Color.NONE.name)

                    color = self.__get_color(
                        Color[splitcolors[0].upper()], Color[splitcolors[1].upper()]
                    )
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
                        splitcolors.append(Color.NONE.name)

                    colors.append(
                        self.__get_color(
                            Color[splitcolors[0].upper()], Color[splitcolors[1].upper()]
                        )
                    )
            else:
                # The rest of the text displays should trail, for wrapping
                text = RenderContext.__sanitize(part)
                if wrap:
                    # Disable curses ability to react to carriage returns
                    text = text.replace("\n", " ")
                    while text:
                        if not wrap_points:
                            next_wrap_point = -1
                        else:
                            next_wrap_point = wrap_points[0] - last_pos
                        if next_wrap_point >= 0 and next_wrap_point < len(text):
                            # Only display part of the string, then go to next line
                            amount = wrap_points[0] - last_pos
                            wrap_points = wrap_points[1:]
                            try:
                                self.__curses_context.addstr(
                                    y,
                                    x,
                                    text[:amount],
                                    attributes | curses.color_pair(colors[-1]),
                                )
                            except CursesError:
                                pass
                            text = text[amount:]
                            last_pos += amount
                            y += 1
                            x = 0
                            if centered:
                                length_part += 1
                                if (
                                    len(lengths) > length_part
                                    and lengths[length_part] < self.bounds.width
                                ):
                                    x += int(
                                        (self.bounds.width - lengths[length_part]) / 2
                                    )
                        else:
                            try:
                                self.__curses_context.addstr(
                                    y,
                                    x,
                                    text,
                                    attributes | curses.color_pair(colors[-1]),
                                )
                            except CursesError:
                                pass
                            x += len(text)
                            last_pos += len(text)
                            text = ""
                else:
                    try:
                        self.__curses_context.addstr(
                            text, attributes | curses.color_pair(colors[-1])
                        )
                    except CursesError:
                        pass

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

    def formatted_string_height(
        self,
        string: str,
    ) -> int:
        # TODO: This also isn't a very good place for this, but its close to the draw function as well.
        parts = RenderContext.__split_formatted_string(string)
        rawtext = "".join(
            RenderContext.__sanitize(part)
            for part in parts
            if not (part[:1] == "<" and part[-1:] == ">")
        )
        if len(rawtext) == 0:
            return 0
        wrap_points = RenderContext.__get_wrap_points(rawtext, 0, 0, self.bounds)
        return len(wrap_points) + 1

    def clear(self) -> None:
        self.__curses_context.clear()

    def refresh(self) -> None:
        self.__curses_context.refresh()

    def getkey(self) -> Optional[str]:
        try:
            return str(self.__curses_context.getkey())
        except CursesError:
            return None
