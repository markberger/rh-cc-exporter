import argparse
import getpass
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import requests
import quiffen

AUTH_ENDPOINT = "https://api.robinhood.com/creditcard/auth/login/"
GRAPHQL_ENDPOINT = "https://api.robinhood.com/creditcard/graphql"
OUTPUT_FILENAME = "./rh-cc-transactions.qif"


@dataclass
class Transaction:
    """
    Represents a single credit card transaction.
    """

    id: str
    timestamp: datetime
    amount: Decimal
    flow: str
    status: str
    visibility: str
    merchant: str

    @classmethod
    def from_dict(cls, data):
        # Parse amount into exact representation
        dollars = str(data["amountMicro"])[:-6]
        cents = str(data["amountMicro"])[-6:]
        amount = Decimal(f"{dollars}.{cents}")

        # Parse timestamp from unix ms to datetime
        timestamp = datetime.fromtimestamp(data["transactionAt"] / 1000)

        return cls(
            id=data["id"],
            timestamp=timestamp,
            amount=amount,
            flow=data["flow"],
            status=data["transactionStatus"],
            visibility=data["visibility"],
            merchant=data["merchantDetails"]["merchantName"],
        )


def generate_device_token():
    """
    Generate a random device token for login.

    Copied from the robin_stocks repo by Joshua M. Fernandes:
    https://github.com/jmfernandes/robin_stocks/blob/2e127949973511692e4d54aa64f38f54ddb7cc3a/robin_stocks/robinhood/authentication.py
    """
    rands = []
    for i in range(0, 16):
        r = random.random()
        rand = 4294967296.0 * r
        rands.append((int(rand) >> ((3 & i) << 3)) & 255)

    hexa = []
    for i in range(0, 256):
        hexa.append(str(hex(i + 256)).lstrip("0x").rstrip("L")[1:])

    id = ""
    for i in range(0, 16):
        id += hexa[rands[i]]

        if (i == 3) or (i == 5) or (i == 7) or (i == 9):
            id += "-"

    return id


def fetch_auth_token():
    """
    Prompt the user for login credentials and attempt to auth.

    If successful, returns the auth_token. Otherwise raises an error.
    """
    username = input("username: ")
    password = getpass.getpass("password: ")
    mfa_code = getpass.getpass("mfa code: ")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Robinhood Credit Card/1.50.3 (iOS 18.1.1;)",
        "x-x1-client": "mobile-app-rh@1.50.3",
    }
    body = {
        "challenge_type": "sms",
        "client_id": "r1kKjKccs94gOZBJK1P4Z5JyLnBK4lFx6kI5aKkh",
        "device_label": "iPhone - iPhone 15",
        "device_token": generate_device_token(),
        "grant_type": "password",
        "mfa_code": mfa_code,
        "password": password,
        "scope": "credit-card",
        "username": username,
    }
    response = requests.post(AUTH_ENDPOINT, json=body, headers=headers)
    assert response.status_code == 200, "Auth request failed"

    results = response.json()
    return results["access_token"]


def fetch_customer_id(auth_token):
    query = """
        query CriticalDataLoaderQuery {
            authIdentity {
                id
                rhUserId
                roles
                creditCustomers {
                    id
                    capabilities {
                        feature
                        scope
                        mode
                    }
                    account {
                        id
                    }
                    displayPrimaryCard {
                        id
                    }
                    externalPrimaryCard {
                        id
                    }
                    rhAppContext {
                        id
                        customerStatuses
                    }
                }
                settings {
                    id
                    colorScheme
                    authConditions
                }
            }
        }
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "rhcardapp/1.35.0 CFNetwork/1498.700.2 Darwin/23.6.0",
        "x-x1-client": "mobile-app-rh@1.35.0",
    }
    body = {
        "query": query,
        "operationName": "CriticalDataLoaderQuery",
        "variables": {},
    }

    response = requests.post(GRAPHQL_ENDPOINT, json=body, headers=headers)
    assert response.status_code == 200, "Customer id request failed"

    results = response.json()
    return results["data"]["authIdentity"]["creditCustomers"][0]["id"]


def fetch_transactions(auth_token, customer_id, cutoff_date):
    query = """
        query TransactionListQuery(
            $q: TransactionSearchRequest!
        ) {
            transactionSearch(q: $q) {
                items {
                    id
                    amountMicro
                    originalAmountMicro
                    flow
                    transactionStatus
                    redemptionStatus
                    transactionType
                    transactionAt
                    visibility
                    merchantDetails {
                        merchantName
                        logoUrl
                    }
                    pointEarnings
                    pointMultiplier
                    links {
                        paymentId
                        creditCustomer {
                            id
                            creditCustomerId
                            name {
                                id
                                firstName
                                lastName
                            }
                        }
                    }
                    disputeDetails {
                        eligibility
                    }
                }
                cursor
            }
        }
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "rhcardapp/1.35.0 CFNetwork/1498.700.2 Darwin/23.6.0",
        "x-x1-client": "mobile-app-rh@1.35.0",
    }

    transactions = []
    cursor = None
    while True:
        body = {
            "query": query,
            "variables": {
                "q": {
                    "creditCustomerId": customer_id,
                    "filters": {"values": []},
                    "sortDetails": {"field": "TIME", "ascending": False},
                    "limit": 40,
                }
            },
            "operationName": "TransactionListQuery",
        }
        if cursor:
            body["variables"]["q"]["cursor"] = cursor

        response = requests.post(GRAPHQL_ENDPOINT, json=body, headers=headers)
        assert response.status_code == 200, "Transactions request failed"

        results = response.json()
        items = results.get("data", {}).get("transactionSearch").get("items", [])
        cursor = results.get("data", {}).get("transactionSearch").get("cursor", "")

        for item in items:
            item = Transaction.from_dict(item)
            if item.timestamp.date() < cutoff_date:
                return transactions

            transactions.append(item)


def main(cutoff_dt):
    cutoff_date = datetime.strptime(cutoff_dt, "%Y-%m-%d").date()
    auth_token = fetch_auth_token()
    customer_id = fetch_customer_id(auth_token)
    transactions = fetch_transactions(auth_token, customer_id, cutoff_date)

    qif = quiffen.Qif()
    acc = quiffen.Account(name="RH Gold", desc="RH Gold credit card")
    qif.add_account(acc)

    for transaction in transactions:
        # Robinhood app automatically hides a subset of transactions. For example
        # a merchant may perform a transaction to confirm the card details are correct.
        if transaction.visibility != "VISIBLE":
            continue

        # YNAB does not seem to respect the cleared flag so we only export
        # transactions that are posted.
        if transaction.status != "POSTED":
            continue

        direction = -1 if transaction.flow == "OUTBOUND" else 1
        qif_transaction = quiffen.Transaction(
            date=transaction.timestamp,
            amount=transaction.amount * direction,
            payee=transaction.merchant,
        )
        acc.add_transaction(qif_transaction, header=quiffen.AccountType.CREDIT_CARD)

    qif.to_qif(OUTPUT_FILENAME)


def parse_args():
    ap = argparse.ArgumentParser(
        description="Export txns from the RH credit card to a QIF file"
    )
    ap.add_argument("dt", help="Include all txns >=YYYY-MM-DD")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.dt)
