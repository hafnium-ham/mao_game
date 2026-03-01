"""Terminal colors for Mao game display."""


class Colors:
    """ANSI color codes for terminal output."""

    # Reset
    RESET = "\033[0m"

    # Text colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright text colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"


def colorize(text: str, color: str, style: str = None) -> str:
    """
    Apply color and optional style to text.

    Args:
        text: Text to colorize.
        color: ANSI color code.
        style: Optional ANSI style code.

    Returns:
        Colorized text string.
    """
    result = color
    if style:
        result += style
    result += text + Colors.RESET
    return result


def red(text: str) -> str:
    """Make text red."""
    return colorize(text, Colors.RED)


def green(text: str) -> str:
    """Make text green."""
    return colorize(text, Colors.GREEN)


def yellow(text: str) -> str:
    """Make text yellow."""
    return colorize(text, Colors.YELLOW)


def blue(text: str) -> str:
    """Make text blue."""
    return colorize(text, Colors.BLUE)


def cyan(text: str) -> str:
    """Make text cyan."""
    return colorize(text, Colors.CYAN)


def bold(text: str) -> str:
    """Make text bold."""
    return colorize(text, Colors.RESET, Colors.BOLD)


def dim(text: str) -> str:
    """Make text dim."""
    return colorize(text, Colors.RESET, Colors.DIM)