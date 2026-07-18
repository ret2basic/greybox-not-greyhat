from __future__ import annotations


def mask_non_code(text: str, language: str) -> str:
    """Replace comments and string literal contents with spaces while preserving offsets/newlines."""

    result = list(text)
    length = len(text)
    index = 0
    state = "code"
    quote = ""
    triple = False
    escape = False
    hash_comments = language in {"python", "ruby"}
    slash_comments = language in {
        "javascript",
        "typescript",
        "java",
        "kotlin",
        "csharp",
        "go",
        "rust",
        "php",
        "scala",
    }

    def blank(position: int) -> None:
        if text[position] not in "\r\n":
            result[position] = " "

    while index < length:
        character = text[index]
        following = text[index + 1] if index + 1 < length else ""

        if state == "line-comment":
            blank(index)
            if character in "\r\n":
                state = "code"
            index += 1
            continue

        if state == "block-comment":
            blank(index)
            if character == "*" and following == "/":
                blank(index + 1)
                index += 2
                state = "code"
            else:
                index += 1
            continue

        if state == "string":
            blank(index)
            if triple and text.startswith(quote * 3, index):
                blank(index)
                if index + 1 < length:
                    blank(index + 1)
                if index + 2 < length:
                    blank(index + 2)
                index += 3
                state = "code"
                triple = False
                escape = False
                continue
            if escape:
                escape = False
                index += 1
                continue
            if character == "\\":
                escape = True
                index += 1
                continue
            if not triple and character == quote:
                state = "code"
            index += 1
            continue

        if hash_comments and character == "#":
            blank(index)
            state = "line-comment"
            index += 1
            continue
        if slash_comments and character == "/" and following == "/":
            blank(index)
            blank(index + 1)
            state = "line-comment"
            index += 2
            continue
        if slash_comments and character == "/" and following == "*":
            blank(index)
            blank(index + 1)
            state = "block-comment"
            index += 2
            continue
        if character in ("'", '"', "\x60"):
            quote = character
            triple = language in {"python", "ruby"} and text.startswith(character * 3, index)
            blank(index)
            if triple:
                blank(index + 1)
                blank(index + 2)
                index += 3
            else:
                index += 1
            state = "string"
            escape = False
            continue
        index += 1
    return "".join(result)


def match_starts_in_code(masked_text: str, offset: int) -> bool:
    return 0 <= offset < len(masked_text) and not masked_text[offset].isspace()


def match_contains_code(masked_text: str, start: int, end: int) -> bool:
    return any(not character.isspace() for character in masked_text[start:end])
