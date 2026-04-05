"""Shared utilities: progress bar and hex-string reversal."""


def progress_bar(current: float, total: float, bar_length: int = 20, suffix: str = "") -> None:
    fraction = current / total

    arrow = int(fraction * bar_length - 1) * "-" + ">"
    padding = int(bar_length - len(arrow)) * " "

    ending = (
        "\n"
        if current == total
        else "\r" if suffix == "" else f'{suffix[:117].ljust(120, " ")}\033[F'
    )

    print(f"Progress: [{arrow}{padding}] {int(fraction * 100)}%", end=ending)


def reverse_hex(hex_str: str) -> str:
    """Reverse a hex string by bytes. e.g. '0100abcd' -> 'cdab0001'."""
    pairs = [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]
    pairs.reverse()
    return "".join(pairs)
