"""
Drapeaux nationaux pour les joueurs.

Source : flagcdn.com (couverture totale via codes ISO 3166-1 alpha-2).
Mapping : code 3 lettres FBref → code ISO 2 lettres flagcdn.com.
"""
from __future__ import annotations

# ── Mapping FBref 3-lettres → ISO 2-lettres (flagcdn.com) ────────────────────
FBREF_TO_ISO2: dict[str, str] = {
    # Europe
    "ALB": "al",   # Albania
    "AND": "ad",   # Andorra
    "ARM": "am",   # Armenia
    "AUT": "at",   # Austria
    "AZE": "az",   # Azerbaijan
    "BEL": "be",   # Belgium
    "BIH": "ba",   # Bosnia-Herzegovina
    "BLR": "by",   # Belarus
    "BUL": "bg",   # Bulgaria
    "CRO": "hr",   # Croatia
    "CYP": "cy",   # Cyprus
    "CZE": "cz",   # Czech Republic
    "DEN": "dk",   # Denmark
    "ENG": "gb-eng",  # England
    "ESP": "es",   # Spain
    "EST": "ee",   # Estonia
    "FIN": "fi",   # Finland
    "FRA": "fr",   # France
    "GEO": "ge",   # Georgia
    "GER": "de",   # Germany
    "GRE": "gr",   # Greece
    "HUN": "hu",   # Hungary
    "IRL": "ie",   # Ireland
    "ISL": "is",   # Iceland
    "ISR": "il",   # Israel
    "ITA": "it",   # Italy
    "KOS": "xk",   # Kosovo
    "KVX": "xk",   # Kosovo (FBref code)
    "LAT": "lv",   # Latvia
    "LIE": "li",   # Liechtenstein
    "LTU": "lt",   # Lithuania
    "LUX": "lu",   # Luxembourg
    "MDA": "md",   # Moldova
    "MKD": "mk",   # North Macedonia
    "MLT": "mt",   # Malta
    "MNE": "me",   # Montenegro
    "NED": "nl",   # Netherlands
    "NIR": "gb-nir",  # Northern Ireland
    "NOR": "no",   # Norway
    "POL": "pl",   # Poland
    "POR": "pt",   # Portugal
    "ROU": "ro",   # Romania
    "RUS": "ru",   # Russia
    "SCO": "gb-sct",  # Scotland
    "SRB": "rs",   # Serbia
    "SUI": "ch",   # Switzerland
    "SVK": "sk",   # Slovakia
    "SVN": "si",   # Slovenia
    "SWE": "se",   # Sweden
    "TUR": "tr",   # Turkey
    "UKR": "ua",   # Ukraine
    "WAL": "gb-wls",  # Wales
    # Amériques
    "ARG": "ar",   # Argentina
    "BOL": "bo",   # Bolivia
    "BRA": "br",   # Brazil
    "CAN": "ca",   # Canada
    "CHI": "cl",   # Chile
    "CHL": "cl",   # Chile (alt)
    "COL": "co",   # Colombia
    "CRC": "cr",   # Costa Rica
    "CUB": "cu",   # Cuba
    "DOM": "do",   # Dominican Republic
    "ECU": "ec",   # Ecuador
    "GLP": "gp",   # Guadeloupe
    "GUF": "gf",   # French Guiana
    "GUY": "gy",   # Guyana
    "HAI": "ht",   # Haiti
    "HON": "hn",   # Honduras
    "JAM": "jm",   # Jamaica
    "MEX": "mx",   # Mexico
    "MSR": "ms",   # Montserrat
    "MTQ": "mq",   # Martinique
    "NCA": "ni",   # Nicaragua
    "PAN": "pa",   # Panama
    "PAR": "py",   # Paraguay
    "PER": "pe",   # Peru
    "PUR": "pr",   # Puerto Rico
    "SUR": "sr",   # Suriname
    "TRI": "tt",   # Trinidad & Tobago
    "URU": "uy",   # Uruguay
    "USA": "us",   # USA
    "VEN": "ve",   # Venezuela
    # Afrique
    "ALG": "dz",   # Algeria
    "ANG": "ao",   # Angola
    "BDI": "bi",   # Burundi
    "BEN": "bj",   # Benin
    "BFA": "bf",   # Burkina Faso
    "BOT": "bw",   # Botswana
    "CAP": "cv",   # Cape Verde (alt)
    "CGO": "cg",   # Republic of Congo
    "CMR": "cm",   # Cameroon
    "COD": "cd",   # DR Congo
    "COM": "km",   # Comoros
    "CPV": "cv",   # Cape Verde
    "CTA": "cf",   # Central African Republic
    "DJI": "dj",   # Djibouti
    "EGY": "eg",   # Egypt
    "EQG": "gq",   # Equatorial Guinea
    "ETH": "et",   # Ethiopia
    "GAB": "ga",   # Gabon
    "GAM": "gm",   # Gambia
    "GHA": "gh",   # Ghana
    "GNB": "gw",   # Guinea-Bissau
    "GUI": "gn",   # Guinea
    "KEN": "ke",   # Kenya
    "LBR": "lr",   # Liberia
    "LBY": "ly",   # Libya
    "MAD": "mg",   # Madagascar
    "MAR": "ma",   # Morocco
    "MLI": "ml",   # Mali
    "MOZ": "mz",   # Mozambique
    "MRT": "mr",   # Mauritania
    "MTN": "mr",   # Mauritania (alt)
    "NGA": "ng",   # Nigeria
    "RWA": "rw",   # Rwanda
    "SEN": "sn",   # Senegal
    "SLE": "sl",   # Sierra Leone
    "SOM": "so",   # Somalia
    "SSD": "ss",   # South Sudan
    "SUD": "sd",   # Sudan
    "SWZ": "sz",   # Eswatini
    "TAN": "tz",   # Tanzania
    "TOG": "tg",   # Togo
    "TUN": "tn",   # Tunisia
    "UGA": "ug",   # Uganda
    "ZAM": "zm",   # Zambia
    "ZIM": "zw",   # Zimbabwe
    "ZAF": "za",   # South Africa
    "RSA": "za",   # South Africa (alt)
    # Asie & Océanie
    "AUS": "au",   # Australia
    "BAN": "bd",   # Bangladesh
    "BHR": "bh",   # Bahrain
    "BRN": "bn",   # Brunei
    "CHN": "cn",   # China
    "IDN": "id",   # Indonesia
    "IND": "in",   # India
    "IRN": "ir",   # Iran
    "IRQ": "iq",   # Iraq
    "JOR": "jo",   # Jordan
    "JPN": "jp",   # Japan
    "KOR": "kr",   # South Korea
    "KSA": "sa",   # Saudi Arabia
    "KWT": "kw",   # Kuwait
    "LBN": "lb",   # Lebanon
    "MAS": "my",   # Malaysia
    "MYA": "mm",   # Myanmar
    "NZL": "nz",   # New Zealand
    "OMA": "om",   # Oman
    "PAK": "pk",   # Pakistan
    "PHI": "ph",   # Philippines
    "QAT": "qa",   # Qatar
    "SGP": "sg",   # Singapore
    "SYR": "sy",   # Syria
    "THA": "th",   # Thailand
    "UAE": "ae",   # UAE
    "UZB": "uz",   # Uzbekistan
    "VIE": "vn",   # Vietnam
    "YEM": "ye",   # Yemen
}


def get_flag_url(fbref_code: str, size: int = 20) -> str | None:
    """
    Retourne l'URL flagcdn.com pour un code FBref 3 lettres.
    size : largeur en pixels (20, 40, 80, 160…).
    Retourne None si code inconnu.
    """
    if not fbref_code:
        return None
    code = str(fbref_code).strip().upper()
    iso2 = FBREF_TO_ISO2.get(code)
    if not iso2:
        return None
    return f"https://flagcdn.com/w{size}/{iso2}.png"


def flag_img_html(fbref_code: str, size: int = 16, style: str = "") -> str:
    """
    Retourne une balise <img> HTML pour afficher le drapeau.
    Retourne une chaîne vide si le code est inconnu.
    """
    url = get_flag_url(fbref_code, size=max(size * 2, 20))  # 2x pour la netteté
    if not url:
        return ""
    base_style = (
        f"width:{size}px;height:{int(size * 0.67)}px;"
        "object-fit:cover;border-radius:2px;vertical-align:middle;"
        "display:inline-block;margin-right:4px"
    )
    combined = f"{base_style};{style}" if style else base_style
    return (
        "<img src='" + url + "' "
        "style='" + combined + "' "
        "onerror=\"this.style.display='none'\">"
    )
