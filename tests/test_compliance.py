from datetime import date
import pytest
from backend.services.compliance import expected_due_date, derive_outcome

def test_due_date_calendar_days():
    assert expected_due_date(date(2026,1,31),30)==date(2026,3,2)

def test_outcome_derived_from_measurement():
    assert derive_outcome(10.05,10,-0.1,0.1)==(pytest.approx(0.05),"PASS")
    assert derive_outcome(10.2,10,-0.1,0.1)==(pytest.approx(0.2),"FAIL")

def test_interval_must_be_positive():
    with pytest.raises(ValueError): expected_due_date(date(2026,1,1),0)
