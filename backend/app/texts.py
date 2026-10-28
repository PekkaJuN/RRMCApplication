"""Finnish user-facing texts of the backend. Every API error message comes from here."""

NOT_FOUND = "Pyydettyä kohdetta ei löydy."
INVALID_REQUEST = "Pyyntö on virheellinen."
INTERNAL_ERROR = "Odottamaton virhe. Katso lisätiedot palvelimen lokista."
DUPLICATE_PRODUCT_NAME = "Samanniminen tuote on jo olemassa."
DUPLICATE_CATEGORY_NAME = "Samanniminen ryhmä tai kategoria on jo olemassa."
INVALID_PARENT = "Kategorian voi lisätä vain ryhmään, eikä ryhmä voi kuulua toiseen ryhmään."
UNKNOWN_CATEGORY = "Kategoriaa ei löydy."
NOT_A_CATEGORY = "Tuotteen voi lisätä vain kategoriaan, ei ryhmään."
CATEGORY_HAS_PRODUCTS = "Kategoriaa, jossa on tuotteita, ei voi muuttaa ryhmäksi."


def category_in_use(product_count: int) -> str:
    products = "tuote" if product_count == 1 else "tuotetta"
    return f"Kategoriaa käyttää {product_count} {products}."


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
