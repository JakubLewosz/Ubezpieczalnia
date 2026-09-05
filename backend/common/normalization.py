import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value).casefold().replace("ł", "l"))
    return "".join(char for char in value if char.isalnum() and not unicodedata.combining(char))
