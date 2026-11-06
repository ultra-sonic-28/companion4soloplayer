"""
Tests for the Slugify slug generator.

Covers accent removal, lowercasing, problematic-character replacement,
reserved Windows names, length truncation, and unique file-name generation.
"""

from pathlib import Path

import pytest

from companion4soloplayer.utils.slugify import Slugify


@pytest.fixture
def slugger() -> Slugify:
    """A default-configured Slugify instance."""
    return Slugify()


# ---------------------------------------------------------------------- #
# Constructor                                                            #
# ---------------------------------------------------------------------- #


def test_default_configuration() -> None:
    """Default values match the documented defaults."""
    slugger = Slugify()
    assert slugger._max_length == 200
    assert slugger._separator == "-"
    assert slugger._lowercase is True


def test_max_length_must_be_positive() -> None:
    """A non-positive max_length raises ValueError."""
    with pytest.raises(ValueError, match="max_length must be positive"):
        Slugify(max_length=0)
    with pytest.raises(ValueError, match="max_length must be positive"):
        Slugify(max_length=-5)


def test_separator_must_be_a_single_character() -> None:
    """Separator must be exactly one character."""
    with pytest.raises(ValueError, match="separator must be a single character"):
        Slugify(separator="")
    with pytest.raises(ValueError, match="separator must be a single character"):
        Slugify(separator="ab")


# ---------------------------------------------------------------------- #
# Basic slugification                                                    #
# ---------------------------------------------------------------------- #


def test_empty_input_returns_fallback(slugger: Slugify) -> None:
    """An empty string yields the fallback slug."""
    assert slugger("") == "unnamed"
    assert slugger("   ") == "unnamed"


def test_accents_are_stripped(slugger: Slugify) -> None:
    """Accented characters are transliterated to plain ASCII."""
    assert slugger("Éléphant") == "elephant"
    assert slugger("Café au lait") == "cafe-au-lait"
    assert slugger("àâäéèêëîïôöùûüÿç") == "aaaeeeeiioouuuyc"


def test_text_is_lowercased(slugger: Slugify) -> None:
    """The result is lowercased by default."""
    assert slugger("HELLO World") == "hello-world"
    assert slugger("MiXeD CaSe") == "mixed-case"


def test_lowercase_can_be_disabled() -> None:
    """lowercase = False preserves the original case."""
    slugger = Slugify(lowercase=False)
    assert slugger("HELLO World") == "HELLO-World"


def test_problematic_characters_are_replaced(slugger: Slugify) -> None:
    """Forbidden and unsafe characters become the separator."""
    assert slugger('a<b>c"d/e:f|g*h?i') == "a-b-c-d-e-f-g-h-i"
    assert slugger("path\\to\\file") == "path-to-file"


def test_control_characters_and_whitespace_are_replaced(
    slugger: Slugify,
) -> None:
    """Control characters and runs of whitespace become one separator."""
    assert slugger("a\t\tb\n\nc") == "a-b-c"
    assert slugger("a   b") == "a-b"


def test_consecutive_separators_are_collapsed(slugger: Slugify) -> None:
    """Multiple consecutive separators collapse into a single one."""
    assert slugger("a - b") == "a-b"


def test_leading_and_trailing_separators_are_stripped(slugger: Slugify) -> None:
    """Separators at the start or end are removed."""
    assert slugger("---hello---") == "hello"


def test_extension_is_preserved(slugger: Slugify) -> None:
    """The file extension is kept at the end of the slug."""
    assert slugger("My File.txt") == "my-file.txt"
    assert slugger("Report (2024).PDF") == "report-(2024).pdf"


def test_callable_interface(slugger: Slugify) -> None:
    """The instance can be called directly like sanitize()."""
    assert slugger("Hello World") == slugger.sanitize("Hello World")


# ---------------------------------------------------------------------- #
# Custom separator                                                       #
# ---------------------------------------------------------------------- #


def test_custom_separator() -> None:
    """A custom separator replaces the default dash."""
    slugger = Slugify(separator="_")
    assert slugger("My File.txt") == "my_file.txt"


def test_custom_separator_collapses_and_strips() -> None:
    """Collapsing and stripping honor the custom separator."""
    slugger = Slugify(separator="_")
    assert slugger("__hello__") == "hello"


# ---------------------------------------------------------------------- #
# Reserved Windows names                                                 #
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "reserved",
    [
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com9",
        "lpt1",
        "lpt9",
    ],
)
def test_reserved_windows_names_are_prefixed(slugger: Slugify, reserved: str) -> None:
    """A reserved name gets an underscore prefix."""
    assert slugger(reserved) == f"_{reserved}"


def test_reserved_names_with_extension(slugger: Slugify) -> None:
    """Reserved names are detected without their extension."""
    assert slugger("CON.txt") == "_con.txt"
    assert slugger("NUL.log") == "_nul.log"


def test_non_reserved_names_are_untouched(slugger: Slugify) -> None:
    """Names similar to, but not in, the reserved list stay unchanged."""
    assert slugger("linux") == "linux"
    assert slugger("console") == "console"
    assert slugger("data.txt") == "data.txt"


# ---------------------------------------------------------------------- #
# Length truncation                                                      #
# ---------------------------------------------------------------------- #


def test_length_is_truncated_keeping_extension(slugger: Slugify) -> None:
    """Over-long slugs are truncated while the extension is preserved."""
    slugger = Slugify(max_length=10)
    assert slugger("a-very-long-filename.txt") == "a-very.txt"


def test_length_truncation_respects_limit(slugger: Slugify) -> None:
    """The final slug never exceeds max_length (extension included)."""
    slugger = Slugify(max_length=5)
    assert len(slugger("file.txt")) <= 5
    assert slugger("file.txt") == "f.txt"


def test_max_length_shorter_than_extension() -> None:
    """When the extension alone exceeds the limit, it is trimmed."""
    slugger = Slugify(max_length=3)
    assert slugger("file.txt") == ".tx"


# ---------------------------------------------------------------------- #
# Unique file names                                                      #
# ---------------------------------------------------------------------- #


def test_unique_returns_filename_when_available(tmp_path: Path) -> None:
    """An available file name is returned unchanged."""
    slugger = Slugify()
    assert slugger.unique(tmp_path, "report.txt") == "report.txt"


def test_unique_appends_numeric_suffix(tmp_path: Path) -> None:
    """An existing file gets a -1, -2, ... suffix."""
    slugger = Slugify()
    (tmp_path / "report.txt").write_text("x", encoding="utf-8")
    assert slugger.unique(tmp_path, "report.txt") == "report-1.txt"
    (tmp_path / "report-1.txt").write_text("x", encoding="utf-8")
    assert slugger.unique(tmp_path, "report.txt") == "report-2.txt"


def test_unique_uses_custom_separator(tmp_path: Path) -> None:
    """The numeric suffix uses the instance's separator."""
    slugger = Slugify(separator="_")
    (tmp_path / "report.txt").write_text("x", encoding="utf-8")
    assert slugger.unique(tmp_path, "report.txt") == "report_1.txt"


def test_unique_with_missing_directory(tmp_path: Path) -> None:
    """A missing directory does not raise; the name is returned as-is."""
    slugger = Slugify()
    missing = tmp_path / "does-not-exist"
    assert slugger.unique(missing, "report.txt") == "report.txt"


def test_unique_preserves_extension(tmp_path: Path) -> None:
    """The extension stays at the end of the suffixed name."""
    slugger = Slugify()
    (tmp_path / "archive.tar.gz").write_text("x", encoding="utf-8")
    assert slugger.unique(tmp_path, "archive.tar.gz") == "archive.tar-1.gz"


# ---------------------------------------------------------------------- #
# Representation                                                         #
# ---------------------------------------------------------------------- #


def test_repr_shows_configuration() -> None:
    """__repr__ exposes the instance configuration."""
    slugger = Slugify(max_length=50, separator="_", lowercase=False)
    assert "max_length=50" in repr(slugger)
    assert "separator='_'" in repr(slugger)
    assert "lowercase=False" in repr(slugger)
