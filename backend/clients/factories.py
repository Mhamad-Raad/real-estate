"""Test fixtures for clients — the one place that knows what a valid client needs.

Every test needs a `date_of_birth`, and a married one needs the full spouse set or the DB check
constraint rejects it. Centralising that means adding a required field later touches one file
instead of every test in the suite.
"""

from datetime import date

from .models import Client

DEFAULTS = {
    "full_name": "Beneficiary",
    "pid": "199001011234",
    "mother_full_name": "Mother",
    "date_of_birth": date(1990, 1, 1),
}

SPOUSE_DEFAULTS = {
    "spouse_name": "Spouse",
    "spouse_date_of_birth": date(1992, 2, 2),
    "spouse_mother_full_name": "Spouse Mother",
}


def client_data(**overrides) -> dict:
    """Valid field values for a client, as a dict — for serializer/API payload tests."""
    data = {**DEFAULTS, **overrides}
    if data.get("marital_status") == Client.MaritalStatus.MARRIED:
        data = {**SPOUSE_DEFAULTS, **data}
    return data


def make_client(**overrides) -> Client:
    return Client.objects.create(**client_data(**overrides))
