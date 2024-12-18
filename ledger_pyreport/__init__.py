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

from . import accounting
from . import ledger
from .config import config
from .model import *

import calendar
from datetime import datetime, timedelta
from decimal import Decimal
from markupsafe import Markup
import flask
import itertools

app = flask.Flask(__name__, template_folder="jinja2")


@app.route("/")
def index():
    date = datetime.now()
    pstart = ledger.financial_year(date)

    return flask.render_template("index.html", date=date, pstart=pstart)


def make_period(pstart, date, compare, cmp_period):
    pstarts = []
    dates = []
    labels = []

    for i in range(0, compare + 1):
        if cmp_period == "year":
            date2 = date.replace(year=date.year - i)
            pstarts.append(pstart.replace(year=pstart.year - i))
            dates.append(date2)
            labels.append(date2.strftime("%Y"))
        elif cmp_period == "month":
            pstart2 = pstart
            date2 = date

            for _ in range(i):
                # Go backward one month
                pstart2 = pstart2.replace(day=1) - timedelta(days=1)
                date2 = date2.replace(day=1) - timedelta(days=1)

            pstart2 = pstart2.replace(day=pstart.day)

            # Is this the last day of the month?
            is_last = calendar.monthrange(date.year, date.month)[1] == date.day
            if is_last:
                date2 = date2.replace(
                    day=calendar.monthrange(date2.year, date2.month)[1]
                )
            else:
                if date.day > calendar.monthrange(date.year, date.month)[1]:
                    date2 = date2.replace(
                        day=calendar.monthrange(date2.year, date2.month)[1]
                    )
                else:
                    date2 = date2.replace(day=date.day)

            pstarts.append(pstart2)
            dates.append(date2)
            labels.append(date2.strftime("%b %Y"))

    return pstarts, dates, labels


def describe_period(date_end, date_beg):
    if date_end == (date_beg.replace(year=date_beg.year + 1) - timedelta(days=1)):
        return "year ended {}".format(date_end.strftime("%d %B %Y"))
    elif date_beg == ledger.financial_year(date_end):
        return "financial year to {}".format(date_end.strftime("%d %B %Y"))
    else:
        return "period from {} to {}".format(
            date_beg.strftime("%d %B %Y"), date_end.strftime("%d %B %Y")
        )


@app.route("/trial")
def trial():
    date = datetime.strptime(flask.request.args["date"], "%Y-%m-%d")
    pstart = datetime.strptime(flask.request.args["pstart"], "%Y-%m-%d")
    compare = int(flask.request.args.get("compare", "0"))
    cmp_period = flask.request.args.get("cmpperiod", "year")
    cash = flask.request.args.get("cash", False)

    if compare == 0:
        # Get trial balance
        l = ledger.raw_transactions_at_date(date)
        report_commodity = l.get_commodity(config["report_commodity"])
        if cash:
            l = accounting.ledger_to_cash(l, report_commodity)
        trial_balance = accounting.trial_balance(l, date, pstart, report_commodity)

        total_dr = Amount(0, report_commodity)
        total_cr = Amount(0, report_commodity)

        for account in l.accounts.values():
            # Display in "cost basis" as we have already accounted for unrealised gains
            balance = trial_balance.get_balance(account).exchange(
                report_commodity, True
            )
            if balance > 0:
                total_dr += balance
            else:
                total_cr -= balance

        # Identify which accounts have transactions
        accounts = sorted(l.accounts.values(), key=lambda a: a.name)
        trial_balance.trn_accounts = [
            a
            for a in accounts
            if any(
                p.account == a
                for t in l.transactions
                for p in t.postings
                if t.date >= pstart and t.date <= date
            )
        ]

        return flask.render_template(
            "trial.html",
            date=date,
            pstart=pstart,
            trial_balance=trial_balance,
            accounts=accounts,
            total_dr=total_dr,
            total_cr=total_cr,
            report_commodity=report_commodity,
        )
    else:
        # Get multiple trial balances for comparison
        pstarts, dates, labels = make_period(pstart, date, compare, cmp_period)

        l = ledger.raw_transactions_at_date(date)
        report_commodity = l.get_commodity(config["report_commodity"])
        if cash:
            l = accounting.ledger_to_cash(l, report_commodity)
        trial_balances = [
            accounting.trial_balance(l.clone(), d, p, report_commodity, label=lbl)
            for d, p, lbl in zip(dates, pstarts, labels)
        ]

        # Identify which accounts have transactions in which periods
        accounts = sorted(l.accounts.values(), key=lambda a: a.name)
        for trial_balance in trial_balances:
            trial_balance.trn_accounts = [
                a
                for a in accounts
                if any(
                    p.account == a
                    for t in l.transactions
                    for p in t.postings
                    if t.date >= trial_balance.pstart and t.date <= trial_balance.date
                )
            ]

        # Delete accounts with always no transactions
        for account in accounts[:]:
            if not any(account in b.trn_accounts for b in trial_balances):
                accounts.remove(account)

        return flask.render_template(
            "trial_multiple.html",
            trial_balances=trial_balances,
            accounts=accounts,
            report_commodity=report_commodity,
            cash=cash,
        )


@app.route("/balance")
def balance():
    date = datetime.strptime(flask.request.args["date"], "%Y-%m-%d")
    pstart = datetime.strptime(flask.request.args["pstart"], "%Y-%m-%d")
    compare = int(flask.request.args.get("compare", "0"))
    cmp_period = flask.request.args.get("cmpperiod", "year")
    cash = flask.request.args.get("cash", False)

    pstarts, dates, labels = make_period(pstart, date, compare, cmp_period)

    l = ledger.raw_transactions_at_date(date)
    report_commodity = l.get_commodity(config["report_commodity"])
    if cash:
        l = accounting.ledger_to_cash(l, report_commodity)
    balance_sheets = [
        accounting.balance_sheet(
            accounting.trial_balance(l.clone(), d, p, report_commodity, label=lbl)
        )
        for d, p, lbl in zip(dates, pstarts, labels)
    ]

    # Delete accounts with always zero balances
    accounts = list(l.accounts.values())
    for account in accounts[:]:
        if all(
            b.get_balance(account).exchange(report_commodity, True).near_zero
            and b.get_total(account).exchange(report_commodity, True).near_zero
            for b in balance_sheets
        ):
            accounts.remove(account)

    return flask.render_template(
        "balance.html",
        ledger=l,
        balance_sheets=balance_sheets,
        accounts=accounts,
        config=config,
        report_commodity=report_commodity,
        cash=cash,
    )


@app.route("/pandl")
def pandl():
    date_beg = datetime.strptime(flask.request.args["date_beg"], "%Y-%m-%d")
    date_end = datetime.strptime(flask.request.args["date_end"], "%Y-%m-%d")
    compare = int(flask.request.args.get("compare", "0"))
    cmp_period = flask.request.args.get("cmpperiod", "year")
    cash = flask.request.args.get("cash", False)
    scope = flask.request.args.get("scope", "pandl")

    dates_beg, dates_end, labels = make_period(date_beg, date_end, compare, cmp_period)

    l = ledger.raw_transactions_at_date(date_end)
    report_commodity = l.get_commodity(config["report_commodity"])
    if cash:
        l = accounting.ledger_to_cash(l, report_commodity)
    pandls = [
        accounting.trial_balance(l.clone(), de, db, report_commodity, label=lbl)
        for de, db, lbl in zip(dates_end, dates_beg, labels)
    ]

    # Process separate P&L accounts
    separate_pandls = []
    for separate_pandl_name in config["separate_pandl"]:
        acc_income = l.get_account(config["income_account"] + ":" + separate_pandl_name)
        acc_expenses = l.get_account(
            config["expenses_account"] + ":" + separate_pandl_name
        )
        separate_pandls.append((acc_income, acc_expenses))

        # Unlink from parents so raw figures not counted in income/expense total
        acc_income.parent.children.remove(acc_income)
        acc_expenses.parent.children.remove(acc_expenses)

        # Add summary account
        for i, de, db in zip(range(compare + 1), dates_end, dates_beg):
            balance = (
                pandls[i].get_total(acc_income) + pandls[i].get_total(acc_expenses)
            ).exchange(report_commodity, True)

            if balance <= 0:  # Credit
                summary_account = l.get_account(
                    config["income_account"] + ":" + separate_pandl_name + " Profit"
                )
            else:
                summary_account = l.get_account(
                    config["expenses_account"] + ":" + separate_pandl_name + " Loss"
                )

            pandls[i].balances[summary_account.name] = (
                pandls[i].get_balance(summary_account) + balance
            )

    # Delete accounts with always zero balances
    accounts = list(l.accounts.values())
    for account in accounts[:]:
        if all(
            p.get_balance(account) == 0 and p.get_total(account) == 0 for p in pandls
        ):
            accounts.remove(account)

    return flask.render_template(
        "pandl.html",
        period=describe_period(date_end, date_beg),
        ledger=l,
        pandls=pandls,
        accounts=accounts,
        separate_pandls=separate_pandls,
        config=config,
        report_commodity=report_commodity,
        cash=cash,
        scope=scope,
    )


@app.route("/cashflow")
def cashflow():
    date_beg = datetime.strptime(flask.request.args["date_beg"], "%Y-%m-%d")
    date_end = datetime.strptime(flask.request.args["date_end"], "%Y-%m-%d")
    compare = int(flask.request.args.get("compare", "0"))
    cmp_period = flask.request.args.get("cmpperiod", "year")
    method = flask.request.args["method"]

    dates_beg, dates_end, labels = make_period(date_beg, date_end, compare, cmp_period)

    l = ledger.raw_transactions_at_date(date_end)
    report_commodity = l.get_commodity(config["report_commodity"])

    cash_accounts = [a for a in l.accounts.values() if a.is_cash]

    # Calculate opening and closing cash
    opening_balances = []
    closing_balances = []
    cashflows = []
    profits = []
    for de, db, lbl in zip(dates_end, dates_beg, labels):
        tb = accounting.trial_balance(
            l.clone(), db - timedelta(days=1), db, report_commodity
        )
        opening_balances.append(
            sum((tb.get_balance(a) for a in cash_accounts), Balance()).exchange(
                report_commodity, True
            )
        )

        tb = accounting.trial_balance(l.clone(), de, db, report_commodity)
        closing_balances.append(
            sum((tb.get_balance(a) for a in cash_accounts), Balance()).exchange(
                report_commodity, True
            )
        )

        if method == "direct":
            # Determine transactions affecting cash assets
            cashflows.append(
                accounting.account_flows(
                    tb.ledger, de, db, cash_accounts, True, label=lbl
                )
            )
        else:
            # Determine net profit (loss)
            profits.append(
                -(
                    tb.get_total(tb.ledger.get_account(config["income_account"]))
                    + tb.get_total(tb.ledger.get_account(config["expenses_account"]))
                    + tb.get_total(tb.ledger.get_account(config["oci_account"]))
                ).exchange(report_commodity, True)
            )

            # Determine transactions affecting equity, liabilities and non-cash assets
            noncash_accounts = [
                a
                for a in l.accounts.values()
                if a.is_equity or a.is_liability or (a.is_asset and not a.is_cash)
            ]
            cashflows.append(
                accounting.account_flows(
                    tb.ledger, de, db, noncash_accounts, False, label=lbl
                )
            )

    # Delete accounts with always zero balances
    accounts = list(l.accounts.values())
    for account in accounts[:]:
        if all(
            p.get_balance(account) == 0 and p.get_total(account) == 0 for p in cashflows
        ):
            accounts.remove(account)

    if method == "direct":
        return flask.render_template(
            "cashflow_direct.html",
            period=describe_period(date_end, date_beg),
            ledger=l,
            cashflows=cashflows,
            opening_balances=opening_balances,
            closing_balances=closing_balances,
            accounts=accounts,
            config=config,
            report_commodity=report_commodity,
        )
    else:
        return flask.render_template(
            "cashflow_indirect.html",
            period=describe_period(date_end, date_beg),
            ledger=l,
            cashflows=cashflows,
            profits=profits,
            opening_balances=opening_balances,
            closing_balances=closing_balances,
            accounts=accounts,
            config=config,
            report_commodity=report_commodity,
        )


@app.route("/transactions")
def transactions():
    date_beg = datetime.strptime(flask.request.args["date_beg"], "%Y-%m-%d")
    date_end = datetime.strptime(flask.request.args["date_end"], "%Y-%m-%d")
    account = flask.request.args.get("account", None)
    cash = flask.request.args.get("cash", False)
    commodity = flask.request.args.get("commodity", False)

    # General ledger
    l = ledger.raw_transactions_at_date(date_end)
    report_commodity = l.get_commodity(config["report_commodity"])
    if cash:
        l = accounting.ledger_to_cash(l, report_commodity)

    # Unrealized gains
    l = accounting.trial_balance(l, date_end, date_beg, report_commodity).ledger

    if not account:
        # General Ledger
        transactions = [
            t for t in l.transactions if t.date <= date_end and t.date >= date_beg
        ]

        total_dr = sum(
            (p.amount for t in transactions for p in t.postings if p.amount > 0),
            Balance(),
        ).exchange(report_commodity, True)
        total_cr = sum(
            (p.amount for t in transactions for p in t.postings if p.amount < 0),
            Balance(),
        ).exchange(report_commodity, True)

        return flask.render_template(
            "transactions.html",
            date_beg=date_beg,
            date_end=date_end,
            period=describe_period(date_end, date_beg),
            account=None,
            ledger=l,
            transactions=transactions,
            total_dr=total_dr,
            total_cr=total_cr,
            report_commodity=report_commodity,
            cash=cash,
        )
    elif commodity:
        # Account Transactions with commodity detail
        account = l.get_account(account)
        transactions = [
            t
            for t in l.transactions
            if t.date <= date_end
            and t.date >= date_beg
            and any(p.account == account for p in t.postings)
        ]

        # Use trial_balance_raw because ledger is already adjusted for unrealised gains, etc.
        opening_balance = (
            accounting.trial_balance_raw(l, date_beg - timedelta(days=1), date_beg)
            .get_balance(account)
            .clean()
        )
        closing_balance = (
            accounting.trial_balance_raw(l, date_end, date_beg)
            .get_balance(account)
            .clean()
        )

        def matching_posting(transaction, amount):
            return next(
                (
                    p
                    for p in transaction.postings
                    if p.account == account and p.amount.commodity == amount.commodity
                ),
                None,
            )

        return flask.render_template(
            "transactions_commodity.html",
            date_beg=date_beg,
            date_end=date_end,
            period=describe_period(date_end, date_beg),
            account=account,
            ledger=l,
            transactions=transactions,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            report_commodity=report_commodity,
            cash=cash,
            timedelta=timedelta,
            matching_posting=matching_posting,
        )
    else:
        # Account Transactions
        account = l.get_account(account)
        transactions = [
            t.perspective_of(account)
            for t in l.transactions
            if t.date <= date_end
            and t.date >= date_beg
            and any(p.account == account for p in t.postings)
        ]

        opening_balance = (
            accounting.trial_balance_raw(l, date_beg - timedelta(days=1), date_beg)
            .get_balance(account)
            .exchange(report_commodity, True)
        )
        closing_balance = (
            accounting.trial_balance_raw(l, date_end, date_beg)
            .get_balance(account)
            .exchange(report_commodity, True)
        )

        return flask.render_template(
            "transactions.html",
            date_beg=date_beg,
            date_end=date_end,
            period=describe_period(date_end, date_beg),
            account=account,
            ledger=l,
            transactions=transactions,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            report_commodity=report_commodity,
            cash=cash,
            timedelta=timedelta,
        )


@app.route("/transaction")
def transaction():
    date = datetime.strptime(flask.request.args["date"], "%Y-%m-%d")
    pstart = datetime.strptime(flask.request.args["pstart"], "%Y-%m-%d")
    uuid = flask.request.args["uuid"]
    cash = flask.request.args.get("cash", False)
    commodity = flask.request.args.get("commodity", False)
    split = flask.request.args.get("split", False)

    # General ledger
    l = ledger.raw_transactions_at_date(None)
    report_commodity = l.get_commodity(config["report_commodity"])
    if cash:
        l = accounting.ledger_to_cash(l, report_commodity)

    l = accounting.trial_balance(l, date, pstart, report_commodity).ledger

    transaction = next((t for t in l.transactions if str(t.uuid) == uuid))

    if split:
        postings = transaction.split(report_commodity)
        transaction = Transaction(
            l,
            transaction.id,
            transaction.date,
            transaction.description,
            transaction.code,
            transaction.uuid,
        )
        transaction.postings = [p for r in postings for p in r]

    if commodity:
        total_dr = sum(
            (p.amount for p in transaction.postings if p.amount > 0), Balance()
        ).clean()
        total_cr = sum(
            (p.amount for p in transaction.postings if p.amount < 0), Balance()
        ).clean()
        totals = itertools.zip_longest(total_dr.amounts, total_cr.amounts)
        return flask.render_template(
            "transaction_commodity.html",
            ledger=l,
            transaction=transaction,
            totals=totals,
            total_dr=total_dr.exchange(report_commodity, True),
            total_cr=total_cr.exchange(report_commodity, True),
            report_commodity=report_commodity,
            cash=cash,
            split=split,
            date=date,
            pstart=pstart,
        )
    else:
        total_dr = sum(
            (p.amount for p in transaction.postings if p.amount > 0), Balance()
        ).exchange(report_commodity, True)
        total_cr = sum(
            (p.amount for p in transaction.postings if p.amount < 0), Balance()
        ).exchange(report_commodity, True)
        return flask.render_template(
            "transaction.html",
            ledger=l,
            transaction=transaction,
            total_dr=total_dr,
            total_cr=total_cr,
            report_commodity=report_commodity,
            cash=cash,
            split=split,
            date=date,
            pstart=pstart,
        )


# Template filters


@app.template_filter("a")
def filter_amount(amt, link=None):
    if amt.near_zero:
        amt_str = "0.00"
        is_pos = True
    elif amt >= 0:
        amt_str = "{:,.2f}".format(amt.amount).replace(
            ",", "&#8239;"
        )  # Narrow no-break space
        is_pos = True
    else:
        amt_str = "{:,.2f}".format(-amt.amount).replace(",", "&#8239;")
        is_pos = False

    if link:
        if is_pos:
            return Markup(
                '<a href="{}"><span title="{}">{}</span></a>&nbsp;'.format(
                    link, amt.tostr(False), amt_str
                )
            )
        else:
            return Markup(
                '<a href="{}"><span title="{}">({})</span></a>'.format(
                    link, amt.tostr(False), amt_str
                )
            )
    else:
        if is_pos:
            return Markup(
                '<span class="copyable-amount" title="{}">{}</span>&nbsp;'.format(
                    amt.tostr(False), amt_str
                )
            )
        else:
            return Markup(
                '<span class="copyable-amount" title="{}">({})</span>'.format(
                    amt.tostr(False), amt_str
                )
            )


@app.template_filter("b")
def filter_amount_positive(amt):
    return Markup(
        '<span class="copyable-amount" title="{}">{:,.2f}</span>'.format(
            amt.tostr(False), amt.amount
        ).replace(",", "&#8239;")
    )


@app.template_filter("bc")
def filter_commodity_positive(amt):
    if amt.commodity.is_prefix:
        return Markup(
            '<span class="copyable-amount" title="{}">{}{}{:,.2f}</span>'.format(
                amt.tostr(False),
                amt.commodity.name,
                " " if amt.commodity.is_space else "",
                amt.amount,
            ).replace(",", "&#8239;")
        )
    else:
        return Markup(
            '<span class="copyable-amount" title="{}">{:,.2f}{}{}</span>'.format(
                amt.tostr(False),
                amt.amount,
                " " if amt.commodity.is_space else "",
                amt.commodity.name,
            ).replace(",", "&#8239;")
        )


@app.template_filter("bt")
def filter_commodity_table_positive(amt, show_price, link=None):
    result = []
    if amt.commodity.is_prefix:
        amt_str = filter_commodity_positive(amt)
        cur_str = ""
    else:
        amt_str = "{:,.2f}".format(amt.amount).replace(",", "&#8239;")
        cur_str = amt.commodity.name

    amt_full = amt.tostr(False)

    result.append(
        '<td style="text-align: right;"><a href="{}"><span class="copyable-amount" title="{}">{}</span></a></td>'.format(
            link, amt_full, amt_str
        )
        if link
        else '<td style="text-align: right;"><span class="copyable-amount" title="{}">{}</span></td>'.format(
            amt_full, amt_str
        )
    )
    result.append(
        '<td><span class="copyable-amount" title="{}">{}</span></td>'.format(
            amt_full, cur_str
        )
    )

    if show_price:
        if amt.commodity.price:
            result.append(
                "<td>{{{}}}</td>".format(filter_commodity_positive(amt.commodity.price))
            )
        else:
            result.append("<td></td>")

    return Markup("".join(result))


# Debug views


@app.route("/debug/imbalances")
def debug_imbalances():
    date = datetime.strptime(flask.request.args["date"], "%Y-%m-%d")
    pstart = datetime.strptime(flask.request.args["pstart"], "%Y-%m-%d")
    cash = flask.request.args.get("cash", False)

    l = ledger.raw_transactions_at_date(date)
    report_commodity = l.get_commodity(config["report_commodity"])
    if cash:
        l = accounting.ledger_to_cash(l, report_commodity)

    transactions = [
        t
        for t in l.transactions
        if t.date <= date
        and t.date >= pstart
        and not sum((p.amount for p in t.postings), Balance())
        .exchange(report_commodity, True)
        .near_zero
    ]

    total_dr = sum(
        (p.amount for t in transactions for p in t.postings if p.amount > 0), Balance()
    ).exchange(report_commodity, True)
    total_cr = sum(
        (p.amount for t in transactions for p in t.postings if p.amount < 0), Balance()
    ).exchange(report_commodity, True)

    return flask.render_template(
        "transactions.html",
        date=date,
        pstart=pstart,
        period=describe_period(date, pstart),
        account=None,
        ledger=l,
        transactions=transactions,
        total_dr=total_dr,
        total_cr=total_cr,
        report_commodity=report_commodity,
        cash=cash,
    )


# Load extensions
for ext_name in config["extensions"]:
    with open(ext_name, "r") as f:
        exec(f.read())
