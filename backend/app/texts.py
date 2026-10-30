"""Finnish user-facing texts of the backend. Every API error message comes from here."""

NOT_FOUND = "Pyydettyä kohdetta ei löydy."
INVALID_REQUEST = "Pyyntö on virheellinen."
INTERNAL_ERROR = "Odottamaton virhe. Katso lisätiedot palvelimen lokista."
DUPLICATE_PRODUCT_NAME = "Samanniminen tuote on jo olemassa."
DUPLICATE_CATEGORY_NAME = "Samanniminen ryhmä tai kategoria on jo olemassa."
INVALID_PARENT = "Kategorian voi lisätä vain ryhmään, eikä ryhmä voi kuulua toiseen ryhmään."
UNKNOWN_CATEGORY = "Kategoriaa ei löydy."
NOT_A_CATEGORY = "Tuotteen voi lisätä vain kategoriaan, ei ryhmään."
CATEGORY_HAS_PRODUCTS = "Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi."
DEPOSIT_REFUND_LINE = "Pantinpalautusriville ei voi valita kategoriaa."


def category_in_use(product_count: int, line_count: int = 0) -> str:
    """Names only the counts above 0, e.g. "Kategoriaa käyttää 1 kuittirivi."."""
    parts: list[str] = []
    if product_count or not line_count:
        parts.append(f"{product_count} {'tuote' if product_count == 1 else 'tuotetta'}")
    if line_count:
        parts.append(f"{line_count} {'kuittirivi' if line_count == 1 else 'kuittiriviä'}")
    return f"Kategoriaa käyttää {' ja '.join(parts)}."


def group_not_empty(category_count: int) -> str:
    categories = "kategoria" if category_count == 1 else "kategoriaa"
    return f"Ryhmässä on {category_count} {categories}."


def invalid_name(max_length: int) -> str:
    return f"Nimen pituuden on oltava 1–{max_length} merkkiä."


IMPORT_RUNNING = "Tuonti on jo käynnissä."
FOLDERS_UNAVAILABLE = "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa."
UNSUPPORTED_FORMAT = "Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa."
READ_FAILED = "Tiedostoa ei voitu lukea."
SAVE_FAILED = "Kuitin tallennus epäonnistui."
MOVE_FAILED = "Tiedostoa ei voitu siirtää valmiiden kansioon."
UNREADABLE_IMAGE = "Kuvaa ei voitu avata."
OCR_FAILED = "Tekstin tunnistus epäonnistui."
NO_TEXT = "Kuvasta ei löytynyt tekstiä."
PARSE_FAILED = "Kuittia ei voitu tulkita."
MODEL_UNAVAILABLE = "Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi."
OCR_UNAVAILABLE = "Tekstintunnistus ei ole käytettävissä."
MODEL_LOST = (
    "Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät tuontikansioon."
)
IMAGE_MISSING = "Kuvaa ei löydy valmiiden kansiosta."
