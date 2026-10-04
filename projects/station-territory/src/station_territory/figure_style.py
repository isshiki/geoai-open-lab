"""Small, unobtrusive author signature for article figures.

Required source attribution belongs in a separate, legible caption. This
signature does not replace attribution or imply ownership of source data.
"""

SIGNATURE = "masahiko.info"
SIGNATURE_URL = "https://masahiko.info/"


def add_signature(figure):
    """Place the author's link in the upper-right title row.

    Reserve the upper title row and keep the title left-aligned. PNG keeps
    the text; vector backends that support URLs also retain the hyperlink.
    Repeated calls update the same artist instead of stacking watermarks.
    """
    for artist in figure.texts:
        if artist.get_gid() == "author-signature":
            return artist
    artist = figure.text(
        0.94, 0.94, SIGNATURE,
        ha="right", va="center", fontsize=13, color="#777777", alpha=0.85,
        transform=figure.transFigure,
    )
    artist.set_gid("author-signature")
    artist.set_url(SIGNATURE_URL)
    return artist
