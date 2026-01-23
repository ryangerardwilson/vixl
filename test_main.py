import pytest


from main import _version_tuple, _is_version_newer


@pytest.mark.parametrize(
    "version, expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("2.0", (2, 0)),
        ("", (0,)),
        ("1.2.3-beta", (1, 2, 3)),
        ("v3", (3,)),
    ],
)
def test_version_tuple(version, expected):
    assert _version_tuple(version) == expected


@pytest.mark.parametrize(
    "candidate, current, expected",
    [
        ("1.2.4", "1.2.3", True),
        ("v1.2.3", "1.2.3", False),
        ("1.2.3", "1.2.3", False),
        ("2.0", "1.9.9", True),
        ("1.10.0", "1.9.5", True),
        ("1.2.0", "1.2", False),
        ("1.2", "1.2.1", False),
    ],
)
def test_is_version_newer(candidate, current, expected):
    assert _is_version_newer(candidate, current) is expected
