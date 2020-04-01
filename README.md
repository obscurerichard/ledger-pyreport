# ledger-pyreport

ledger-pyreport is a lightweight Flask webapp for generating interactive and printable accounting reports from [ledger-cli](https://www.ledger-cli.org/) data.

## Reports

* Trial balance, and comparative trial balance
* Balance sheet, and comparative balance sheet
* Income statement, and comparative income statement
* General ledger
* Account transactions, with or without itemisation of commodities
* Transaction detail, with or without itemisation of commodities

## Features

* Correctly values assets/liabilities at market value, and income/expenses at cost (pursuant to [AASB 121](https://www.aasb.gov.au/admin/file/content105/c9/AASB121_08-15_COMPfeb16_01-19.pdf)/[IAS 21](https://www.ifrs.org/issued-standards/list-of-standards/ias-21-the-effects-of-changes-in-foreign-exchange-rates/) para 39)
* Correctly computes unrealised gains ([even when Ledger does not](https://yingtongli.me/blog/2020/03/31/ledger-gains.html))
* Accounts for both profit and loss, and other comprehensive income
* Simulates annual closing of books, with presentation of income/expenses on the balance sheet as retained earnings and current year earnings
* Can simulate cash basis accounting, using FIFO methodology to recode transactions involving liabilities and non-cash assets

## Background, demo and screenshots

See [https://yingtongli.me/blog/2020/03/31/ledger-pyreport.html](https://yingtongli.me/blog/2020/03/31/ledger-pyreport.html) for further discussion.

## Usage

Install the dependencies from PyPI, optionally in a virtual environment: (Commands presented for Linux/Mac)

```
virtualenv venv
. venv/bin/activate
pip install -r requirements.txt
```

Copy *config.example.yml* to *config.yml* (or set the *LEDGER_PYREPORT_CONFIG* environment variable to the path to the config file).

Run as per a usual Flask app, for example:

```
FLASK_APP=ledger_pyreport python -m flask run
```

## Notes on Ledger setup

ledger-pyreport expects each of assets, liabilities, equity, income and expenses to be setup in Ledger as a separate top-level account. These accounts should contain a zero balance, with all transactions in child accounts.

Additionally, ledger-pyreport expects the next level of assets and liabilities to be categories of asset and liability (e.g. *Assets:Current*, *Liabilities:Non-current*). These, too, should contain a zero balance.

Ledger-pyreport by default observes the convention that positive amounts in Ledger represent debits, and negative amounts in Ledger represent credits.
