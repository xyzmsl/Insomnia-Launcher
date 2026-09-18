def _tokenize(text):
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                buf.append(text[i])
                i += 1
            i += 1
            yield "str", "".join(buf)
        elif c == "{":
            yield "open", c
            i += 1
        elif c == "}":
            yield "close", c
            i += 1
        else:
            i += 1


def parse_vdf(text):
    tokens = list(_tokenize(text))
    pos = 0

    def parse_obj():
        nonlocal pos
        obj = {}
        while pos < len(tokens):
            kind, val = tokens[pos]
            if kind == "close":
                pos += 1
                return obj
            key = val
            pos += 1
            if pos >= len(tokens):
                return obj
            kind2, val2 = tokens[pos]
            if kind2 == "open":
                pos += 1
                obj[key] = parse_obj()
            else:
                obj[key] = val2
                pos += 1
        return obj

    return parse_obj()


def load_vdf(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return parse_vdf(fh.read())
    except OSError:
        return None