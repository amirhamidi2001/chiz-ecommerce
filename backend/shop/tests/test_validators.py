import pytest
from django.core.exceptions import ValidationError
from shop.validators import _compute_ean13_check_digit, validate_ean13

# A real, well-known EAN-13 (Kinder Bueno chocolate bar) commonly used as
# a reference example for EAN-13 checksum validation. First 12 digits:
# "400638133393", correct check digit: "1".
VALID_EAN13 = "4006381333931"


class TestComputeEan13CheckDigit:
    """Unit-test the checksum math in isolation from the public validator."""

    def test_computes_known_correct_check_digit(self):
        assert _compute_ean13_check_digit("400638133393") == 1

    def test_all_zero_digits_check_digit_is_zero(self):
        assert _compute_ean13_check_digit("000000000000") == 0

    def test_check_digit_is_always_a_single_digit(self):
        for first_12 in ["123456789012", "999999999999", "000000000001"]:
            digit = _compute_ean13_check_digit(first_12)
            assert 0 <= digit <= 9


class TestValidateEan13:

    def test_valid_barcode_does_not_raise(self):
        validate_ean13(VALID_EAN13)  # must not raise

    def test_wrong_checksum_raises(self):
        bad = VALID_EAN13[:12] + "2"  # correct check digit is "1", not "2"
        with pytest.raises(ValidationError):
            validate_ean13(bad)

    def test_transposed_digits_are_caught_by_checksum(self):
        """
        The whole point of a real checksum (vs. a bare 13-digit regex):
        swapping two digits in the middle of an otherwise-valid barcode
        must be caught.
        """
        # Swap the 3rd and 4th digits of VALID_EAN13's data portion.
        transposed = VALID_EAN13[:2] + VALID_EAN13[3] + VALID_EAN13[2] + VALID_EAN13[4:]
        assert transposed != VALID_EAN13
        with pytest.raises(ValidationError):
            validate_ean13(transposed)

    @pytest.mark.parametrize(
        "bad_value",
        [
            "400638133",  # too short
            "40063813339311",  # too long (14 digits)
            "400638133393x",  # contains a letter
            "4006-38133393",  # contains a non-digit separator
            "             ",  # whitespace only
        ],
    )
    def test_non_13_digit_values_raise(self, bad_value):
        with pytest.raises(ValidationError):
            validate_ean13(bad_value)

    def test_error_has_expected_code(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_ean13("not-a-barcode")
        assert exc_info.value.code == "invalid_ean13"

    def test_accepts_integer_like_input_via_str_coercion(self):
        """
        Model CharField values always arrive as strings in practice, but
        the validator explicitly str()-coerces its input, so it should
        not blow up if handed an int with the right digits/checksum.
        """
        validate_ean13(int(VALID_EAN13))  # must not raise
