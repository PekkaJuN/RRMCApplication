"""Finnish user-facing texts of the backend. Every API error message comes from here."""

INVALID_HOST = "Pyyntö hylättiin: tuntematon osoite."
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
NO_IMAGE = "Kuitilla ei ole kuvaa."
RECEIPT_REVIEWED = "Vahvistettua kuittia ei voi poistaa. Peru vahvistus ensin."
FAILED_IMAGE_NOT_FOUND = "Kuvaa ei löydy epäonnistuneiden kansiosta."
DUPLICATE_IMAGE = "Kuva on jo tuotu toiseen kuittiin."
IMAGE_MOVE_FAILED = "Kuvaa ei voitu siirtää valmiiden kansioon. Kuittia ei luotu."
INVALID_AMOUNT = "Summa ei kelpaa."
DEPOSIT_REFUND_AMOUNT = "Pantinpalautuksen summan on oltava negatiivinen."
INVALID_DATE = "Päivämäärä ei kelpaa."
INVALID_STORE = "Kaupan nimi saa olla enintään 100 merkkiä."

# Category totals (totals spec)
INVALID_PERIOD = "Jakso on virheellinen."

NO_CATEGORY = "Ei kategoriaa"
PARTIAL = "(osittainen)"
TOTAL = "Yhteensä"

# PDF export (PDF export spec)
PERIOD_TOO_LONG = "Jakso on liian pitkä PDF-tiedostoon."
WEEKLY_TITLE = "Viikkosummat"
MONTHLY_TITLE = "Kuukausisummat"
COMPARISON_TITLE = "Budjettivertailu"
PERIOD_LABEL = "Jakso:"
CREATED = "Luotu"
CATEGORY = "Kategoria"
AMOUNT = "Summa"
PERIOD_BLOCK = "Koko jakso"
CONTINUED = "(jatkuu)"
PERIOD_KIND = "Jakson tyyppi:"
CALENDAR_MONTH = "Kalenterikuukausi"
MID_PERIOD = "15.–14."
COMPARISON_COLUMNS = ("Budjetti", "Toteutunut", "Jäljellä")
OVER_BUDGET = "Ylitetty"
NO_PURCHASES = "Ei ostoksia valitulla jaksolla."


def unreviewed_in_period(count: int) -> str:
    return f"Tarkistamattomia kuitteja jaksolla: {count}"


def unreviewed_left_out(count: int) -> str:
    return f"Tarkistamattomia kuitteja, ei mukana: {count}"


def undated_left_out(count: int) -> str:
    return f"Kuitteja ilman päivää (ei mukana): {count}"


def page_number(number: int, total: int) -> str:
    return f"Sivu {number}/{total}"


# Archiving (archiving spec)
INVALID_YEAR = "Vuosi on virheellinen."
YEAR_NOT_FINISHED = "Vain päättyneen vuoden voi arkistoida."
ARCHIVE_IMPORT_RUNNING = "Tuonti on käynnissä. Arkistoi vuosi, kun tuonti on valmis."
NOTHING_TO_ARCHIVE = "Vuodelta ei ole arkistoitavia kuitteja."
ARCHIVE_FILE_PREFIX = "arkisto"


def unreviewed_block_archiving(count: int) -> str:
    receipts = "tarkistamaton kuitti" if count == 1 else "tarkistamatonta kuittia"
    return f"Vuotta ei voi arkistoida: vuodella on {count} {receipts}."


def archived_years_note(years: list[int]) -> str:
    """The period warning of the totals and the budget comparison (archiving spec PC10)."""
    if len(years) == 1:
        return f"Arkistoitu vuosi {years[0]} ei ole mukana."
    return f"Arkistoidut vuodet {', '.join(str(year) for year in years)} eivät ole mukana."


# Monthly budget (budget spec)
NOT_A_BUDGET_ROW = "Budjetin voi asettaa vain ryhmälle tai ryhmättömälle kategorialle."
