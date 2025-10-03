import pytest
from applydir.applydir_distance import levenshtein_distance, levenshtein_similarity, sequence_matcher_similarity


def test_levenshtein_distance():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("hello", "hello") == 0
    assert levenshtein_distance("", "test") == 4
    assert levenshtein_distance("line1\nline2", "line1\nline3") == 1


def test_levenshtein_similarity():
    assert levenshtein_similarity(["hello"], ["hello"]) == 1.0
    assert levenshtein_similarity(["kitten"], ["sitting"]) == pytest.approx(0.571, abs=0.001)  # (7-3)/7 ~0.571
    assert levenshtein_similarity(["line1", "line2"], ["line1", "line3"]) == pytest.approx(
        0.909, abs=0.001
    )  # Distance 1 over max len 11
    assert levenshtein_similarity([], []) == 1.0
    assert levenshtein_similarity(["a"], []) == 0.0  # Length mismatch
    assert levenshtein_similarity(["line1\nline2"], ["line1\nline3"]) == pytest.approx(
        0.909, abs=0.001
    )  # Distance 1 over max len 11


def test_sequence_matcher_similarity():
    assert sequence_matcher_similarity(["hello"], ["hello"]) == 1.0
    assert sequence_matcher_similarity(["kitten"], ["sitting"]) == pytest.approx(
        0.615, abs=0.001
    )  # SequenceMatcher ratio: 2*4/13
    assert sequence_matcher_similarity(["line1", "line2"], ["line1", "line3"]) == pytest.approx(
        0.909, abs=0.001
    )  # SequenceMatcher ratio: 2*10/22
    assert sequence_matcher_similarity([], []) == 1.0
    assert sequence_matcher_similarity(["a"], []) == 0.0  # Length mismatch
    assert sequence_matcher_similarity(["line1\nline2"], ["line1\nline3"]) == pytest.approx(
        0.909, abs=0.001
    )  # SequenceMatcher ratio: 2*10/22
