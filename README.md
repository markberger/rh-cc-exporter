# rh-cc-exporter
Export transactions from the RH [Gold Card](https://robinhood.com/creditcard/)
to a [QIF file](https://en.wikipedia.org/wiki/Quicken_Interchange_Format) for easy
use with budgetting apps such as [YNAB](https://www.ynab.com/).

This software is in no way associated with Robinhood. Use at your own risk.

# Local use

You must enable 2fac authentication with an auth app for this tool to work.
Follow the official instructions
[here](https://robinhood.com/us/en/support/articles/twofactor-authentication/) to
get started.

Next install the python requirements with your favorite tool. Here I'll use pyenv
as an example:

```bash
$ pyenv virtualenv rh-cc-exporter
$ pyenv activate rh-cc-exporter
(rh-cc-exporter)$ pip install -r requirements.txt
```

Now run the script by providing a date in YYYY-MM-DD format. This will include all
transactions greater than or equal to this day. For example, to get all transactions
from Sept 1st, 2024 to today inclusively, input 2024-09-01.

Once you run the script, it will then prompt you for your login information and
mfa code.

```bash
(rh-cc-exporter)$ python rh-cc-exporter.py 2024-09-01
username: my_email@gmail.com
password: input_is_hidden_when_tying_here
mfa code: input_is_hidden_when_tying_here

```

If everything works the output will be generated in the same directory:
```bash
$ ls rh-cc-transactions.qif
rh-cc-transactions.qif
```
