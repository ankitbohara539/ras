"""The pure arithmetic behind the public transparency page."""

from app.services.stats_service import median_hours


class TestMedianHours:
    def test_no_data_yet(self) -> None:
        assert median_hours([]) is None

    def test_single_ticket(self) -> None:
        assert median_hours([12.0]) == 12.0

    def test_odd_count_takes_the_middle_value(self) -> None:
        assert median_hours([1.0, 5.0, 100.0]) == 5.0

    def test_even_count_averages_the_middle_two(self) -> None:
        assert median_hours([2.0, 4.0, 6.0, 8.0]) == 5.0

    def test_rounds_to_one_decimal(self) -> None:
        assert median_hours([1.0, 2.0, 3.33333]) == 2.0

    def test_a_few_slow_outliers_do_not_drag_the_median(self) -> None:
        """The point of a median over a mean: one ticket open for a year
        should not make every other ward look slow."""
        fast = [4.0, 6.0, 8.0, 10.0, 12.0]
        assert median_hours(fast + [24 * 365]) == 9.0
