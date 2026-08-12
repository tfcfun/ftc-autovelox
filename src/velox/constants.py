"""Closed value sets. An unknown value quarantines a row rather than passing through."""

SCHEMA_VERSION = 1

# The 107 Italian province codes. Unknown codes are quarantined, never accepted,
# so an omission here surfaces loudly instead of corrupting a row.
PROVINCE_CODES = frozenset("""
AG AL AN AO AP AQ AR AT AV BA BG BI BL BN BO BR BS BT BZ
CA CB CE CH CL CN CO CR CS CT CZ EN FC FE FG FI FM FR GE
GO GR IM IS KR LC LE LI LO LT LU MB MC ME MI MN MO MS MT
NA NO NU OR PA PC PD PE PG PI PN PO PR PT PU PV PZ RA RC
RE RG RI RM RN RO SA SI SO SP SR SS SU SV TA TE TN TO TP
TR TS TV UD VA VB VC VE VI VR VT VV
""".split())

# Region names as they appear in the Documenti block of the source page.
REGIONS = (
    "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia", "Friuli",
    "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte",
    "Puglia", "Sardegna", "Sicilia", "Toscana", "Trentino", "Umbria",
    "Valle d'Aosta", "Veneto",
)

# Compass words used in the fixed-installation PDFs, mapped to bearings in degrees.
DIRECTION_BEARINGS = {
    "nord": 0, "nord-est": 45, "est": 90, "sud-est": 135,
    "sud": 180, "sud-ovest": 225, "ovest": 270, "nord-ovest": 315,
}
