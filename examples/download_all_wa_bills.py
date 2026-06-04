import json

from ausbills import Jurisdiction, get_bills


if __name__ == "__main__":
    bills = [bill.as_dict() for bill in get_bills(Jurisdiction.WA, include_details=True)]
    print(json.dumps(bills, indent=2))
