#   ledger-pyreport
#   Copyright © 2020  Lee Yingtong Li (RunasSudo)
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import csv
import hashlib
import re
import subprocess
from datetime import datetime, timedelta
from decimal import Decimal

from .config import config
from .model import *

# Helper commands to run Ledger


def run_ledger(*args):
    ledger_args = (
        [
            "ledger",
            "--args-only",
            "--file",
            config["ledger_file"],
            "--date-format",
            "%Y-%m-%d",
            "--unround",
        ]
        + config["ledger_args"]
        + list(args)
    )
    proc = subprocess.Popen(
        ledger_args, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate()

    if stderr:
        raise Exception(stderr)

    return stdout


def run_ledger_date(date, *args):
    if date is None:
        return run_ledger(*args)
    return run_ledger("--end", (date + timedelta(days=1)).strftime("%Y-%m-%d"), *args)


# General financial logic


def financial_year(date):
    pstart = date.replace(day=1, month=7)
    if pstart > date:
        pstart = pstart.replace(year=pstart.year - 1)
    return pstart


# Ledger logic

csv.register_dialect("ledger", doublequote=False, escapechar="\\", strict=True)

RE_COMMODITY1 = re.compile(r"([0123456789.,-]+)( *)(.+)")
RE_COMMODITY2 = re.compile(r"(.+?)( *)([0123456789.,-]+)")


def parse_amount(amount):
    if "{" in amount:
        amount_str = amount[: amount.index("{")].strip()
        price_str = amount[amount.index("{") + 1 : amount.index("}")].strip()
    else:
        amount_str = amount
        price_str = None

    if amount_str[0] in list("0123456789-"):
        # Commodity follows number
        result = RE_COMMODITY1.match(amount_str)
        amount_num = Decimal(result.group(1).replace(",", ""))
        commodity = Commodity(
            result.group(3).strip('"'), False, len(result.group(2)) > 0
        )
    else:
        # Commodity precedes number
        result = RE_COMMODITY2.match(amount_str)
        amount_num = Decimal(result.group(3).replace(",", ""))
        commodity = Commodity(
            result.group(1).strip('"'), True, len(result.group(2)) > 0
        )

    if price_str:
        commodity.price = parse_amount(price_str)

    return Amount(amount_num, commodity)


def get_pricedb():
    output = run_ledger(
        "prices",
        "--prices-format",
        "%(quoted(format_date(date))),%(quoted(display_account)),%(quoted(display_amount))\n",
    )

    prices = []

    reader = csv.reader(output.splitlines(), dialect="ledger")
    for date_str, commodity, price_str in reader:
        prices.append(
            (
                datetime.strptime(date_str, "%Y-%m-%d"),
                commodity.strip('"'),
                parse_amount(price_str),
            )
        )

    return prices


def raw_transactions_at_date(date):
    ledger = Ledger(date)
    ledger.prices = get_pricedb()

    output = run_ledger_date(
        date,
        "csv",
        "--csv-format",
        "%(quoted(parent.id)),%(quoted(format_date(date))),%(quoted(parent.code)),%(quoted(payee)),%(quoted(account)),%(quoted(display_amount)),%(quoted(comment)),%(quoted(state)),%(quoted(note))\n",
    )

    uuids = set()

    reader = csv.reader(output.splitlines(True), dialect="ledger")
    for (
        trn_id,
        date_str,
        code,
        payee,
        account_str,
        amount_str,
        comment,
        state_str,
        note_str,
    ) in reader:
        if not ledger.transactions or trn_id != ledger.transactions[-1].id:
            if trn_id in uuids:
                digest = hashlib.sha256()
                digest.update(trn_id.encode("utf-8"))
                digest.update(date_str.encode("utf-8"))
                digest.update(payee.encode("utf-8"))
                uuid = digest.hexdigest()
            else:
                uuid = trn_id

            metadata = {}
            for line in note_str.splitlines():
                line = line.strip()
                if ": " in line:
                    metadata[line.split(": ")[0]] = line.split(": ")[1].strip()

            transaction = Transaction(
                ledger,
                trn_id,
                datetime.strptime(date_str, "%Y-%m-%d"),
                payee,
                code,
                uuid,
                metadata,
            )
            ledger.transactions.append(transaction)

            uuids.add(uuid)
        else:
            # Transaction ID matches: continuation of previous transaction
            transaction = ledger.transactions[-1]

        if ";" in comment:
            comment = comment[comment.index(";") + 1 :].strip()

        amount = parse_amount(amount_str)
        posting = Posting(
            transaction,
            ledger.get_account(account_str),
            amount,
            comment=comment,
            state=Posting.State(int(state_str)),
        )
        transaction.postings.append(posting)

        if amount.commodity.name not in ledger.commodities:
            ledger.commodities[amount.commodity.name] = amount.commodity.strip_price()

    ledger.transactions.sort(key=lambda t: t.date)

    return ledger
