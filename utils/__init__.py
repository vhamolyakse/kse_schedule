def strip_whitespace(x):
    if isinstance(x, str):
        return x.lstrip().rstrip()
    return x