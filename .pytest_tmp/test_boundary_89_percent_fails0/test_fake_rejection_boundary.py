
def test_rejection_pass_rate_boundary():
    """Boundary test: 89% < 90% must fail."""
    rate = 0.89
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} < 90% threshold."
    )
