"""
Slug generation utilities.

Convert arbitrary strings into portable, file-system- and URL-safe slugs.

The :class:`Slugify` class strips accents, lowercases the text (optionally),
replaces every run of problematic characters with a configurable separator,
and guards against reserved Windows names and over-long results.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Final

__all__ = ["Slugify"]

# Characters forbidden on Windows or unsafe in file names / URLs, plus every
# control character and whitespace. Runs of these characters are collapsed
# into a single separator.
_PROBLEMATIC_CHARS_RE: Final[re.Pattern[str]] = re.compile(r'[<>:"/\\|?*\x00-\x1f\s]+')

# Windows reserved device names (without extension). A file whose base name
# is exactly one of these cannot be created on Windows.
_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)

_DEFAULT_MAX_LENGTH: Final[int] = 200
_DEFAULT_SEPARATOR: Final[str] = "-"
_DEFAULT_FALLBACK: Final[str] = "unnamed"


class Slugify:
    """Turns a string into a portable slug.

    A slug is a simplified string that is safe to use as a file name or in a
    URL: accents are transliterated to ASCII, the text is lowercased
    (optionally), and every run of problematic characters is replaced by a
    single separator.

    Usage::

        from companion4soloplayer.utils.slugify import Slugify

        slugger = Slugify()
        slug = slugger("Mon Fichier (2024)!.txt")
        # slug == "mon-fichier-2024.txt"

    Args:
        max_length: Maximum length of the resulting slug. The file extension,
            when present, is preserved and counts toward this limit. Must be
            positive.
        separator: Single character used to replace runs of problematic
            characters. Defaults to ``"-"``.
        lowercase: When ``True`` (default), the result is converted to
            lowercase.

    Raises:
        ValueError: If ``max_length`` is not positive or ``separator`` is not
            a single non-empty character.
    """

    def __init__(
        self,
        *,
        max_length: int = _DEFAULT_MAX_LENGTH,
        separator: str = _DEFAULT_SEPARATOR,
        lowercase: bool = True,
    ) -> None:
        if max_length <= 0:
            raise ValueError(f"max_length must be positive, got {max_length!r}")
        if not isinstance(separator, str) or len(separator) != 1:
            raise ValueError(f"separator must be a single character, got {separator!r}")

        self._max_length = max_length
        self._separator = separator
        self._lowercase = lowercase

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def __call__(self, text: str) -> str:
        """Convert *text* into a slug.

        This is an alias for :meth:`sanitize`, allowing instances to be used
        directly as callables.

        Args:
            text: The raw string to slugify.

        Returns:
            A portable slug. Returns ``"unnamed"`` when the input is empty or
            produces an empty result after sanitization.
        """
        return self.sanitize(text)

    def sanitize(self, text: str) -> str:
        """Sanitize *text* into a portable file-name slug.

        The transformation performs, in order:

        1. Unicode normalization (NFKD) so accents become plain ASCII.
        2. Optional lowercasing.
        3. Replacement of runs of problematic characters by the separator.
        4. Collapsing of consecutive separators into a single one.
        5. Stripping of leading and trailing separators.
        6. Prefixing reserved Windows names with an underscore.
        7. Truncation to ``max_length`` while preserving the extension.
        8. Fallback to ``"unnamed"`` when the result would be empty.

        Args:
            text: The raw string to sanitize.

        Returns:
            A portable slug safe for use as a file name.
        """
        if not text:
            return _DEFAULT_FALLBACK

        # 1. Normalize Unicode (accents -> ASCII).
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

        # 2. Lowercase.
        if self._lowercase:
            ascii_text = ascii_text.lower()

        # 3. Replace runs of problematic characters with the separator.
        slug = _PROBLEMATIC_CHARS_RE.sub(self._separator, ascii_text)

        # 4. Collapse consecutive separators into a single one.
        slug = re.sub(re.escape(self._separator) + r"{2,}", self._separator, slug)

        # 5. Strip leading and trailing separators.
        slug = slug.strip(self._separator)

        # 6. Guard reserved Windows names (checked without extension).
        name_without_ext = slug.split(".")[0]
        if name_without_ext in _RESERVED_NAMES:
            slug = f"_{slug}"

        # 7. Limit length while preserving the extension.
        if len(slug) > self._max_length:
            name, ext = os.path.splitext(slug)
            available = self._max_length - len(ext)
            if available <= 0:
                # The extension alone is longer than the limit: keep what fits.
                return ext[: self._max_length] or _DEFAULT_FALLBACK
            name = name[:available]
            slug = name + ext

        # 8. Fallback when the result is empty.
        if not slug:
            return _DEFAULT_FALLBACK

        return slug

    def unique(
        self,
        directory: str | os.PathLike[str],
        filename: str,
    ) -> str:
        """Return a file name that does not yet exist in *directory*.

        If *filename* is already taken, a numeric suffix is appended before
        the extension (``name-1.ext``, ``name-2.ext``, ...).

        Args:
            directory: Folder in which to check for existing files.
            filename: Candidate file name.

        Returns:
            *filename* if available, otherwise the first non-conflicting
            variant built with the instance's separator.
        """
        directory_path = Path(directory)
        base_path = directory_path / filename
        if not base_path.exists():
            return filename

        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate_name = f"{name}{self._separator}{counter}{ext}"
            if not (directory_path / candidate_name).exists():
                return candidate_name
            counter += 1

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"max_length={self._max_length!r}, "
            f"separator={self._separator!r}, "
            f"lowercase={self._lowercase!r})"
        )
