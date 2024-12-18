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

# Extension to move pending postings to a pending transactions account

_ledger_raw_transactions_at_date = ledger.raw_transactions_at_date


def ledger_raw_transactions_at_date(*args, **kwargs):
    l = _ledger_raw_transactions_at_date(*args, **kwargs)

    for transaction in l.transactions:
        for posting in transaction.postings:
            if posting.state == Posting.State.PENDING:
                posting.account = l.get_account(
                    "Liabilities:Current:Pending Transactions"
                )

    return l


ledger.raw_transactions_at_date = ledger_raw_transactions_at_date
