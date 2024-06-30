# jsondb-cli

A handy command line interface script for managing local JSON databases.

**THIS IS NOT RELATED TO ANY OTHER THINGS CALLED 'JSONDB' OUT THERE.**

This is designed only for small databases that can be easily accessed using a simple command line interface. The database has to fit into memory completely.

## Features

- Tags: Tag your data for easy querying
- Attributes: Attach extra data to your database entries via attributes (e.g. timestamp, etc.)
- Enforced Tags (optional): Create a list of tags you want to have in your database. Assigning other tags to data will raise an error to prevent typos and similar.
- Backups (optional): Enable backup creation to ensure your data doesn't get lost or corrupted
- Platform-independent: This is written entirely in Python, which can be run on any OS
- Portable: All data is (by default) stored in the user's Documents folder, allowing copying data between systems fairly easy, without having to dig in any external config or data folders
- Data formatting: The built-in `format` subcommand makes formatting queried data very simple
- No external dependencies except for the Python interpreter, which is available on nearly any system by default
- It's really simple

## Installing

There are multiple ways to install jsondb-cli.

### The preferred way: pipx

The recommended and most straightforward way is using [pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/TheCheese42/jsondb-cli.git
```

Now the program can be globally run using the `jsondb` command.

### Installation via pip

You can also install the tool using the python package manager `pip`. However, it's good practice to create a virtual environment before installing. `pipx` does this automatically, which is why it is preferred.

Skip this step if you want to install the jsondb-cli into your global environment. It does not require any external dependencies.

Linux/MacOS:

```sh
python -m venv .venv
source .venv/bin/activate
```

\
Windows Powershell:

```sh
python -m venv .venv
.venv/Scripts/Activate.ps1
```

Now your environment is ready for the installation:

```sh
pip install git+https://github.com/NotYou404/jsondb-cli.git
```

Now it can be invoked using the `jsondb` command.

### Running from source

If you do not want to use any package managers, you can as well clone the source code and run it using the python interpreter directly.

```sh
git clone https://github.com/NotYou404/jsondb-cli
cd jsondb-cli
```

The command to run the script is now `python -m jsondb`.

## Usage

For the full help run `jsondb -h`.

Here is an example routine to create, manage and use a database to store quotes. Tags are used to set the quote source and arguments to specify the year of the quote.

```sh
$ jsondb init quotes  # Create a database in ~/Documents/jsondb

$ jsondb modify quotes --enable-backups --enforce-tags
# Backups will be stored in ~/Documents/jsondb/.jsondb_backups_quotes/

$ jsondb modify quotes --add-tag gunther --add-tag fred --add-tag anonymous
# Create 3 new tags that can be attached to data entries

$ jsondb set quotes "I'm a nice human" -t gunther -a year:2024
# Add a new entry with the gunther tag and a year attribute set to 2024

$ jsondb set quotes "Me too" -t fred -a year:2024
$ jsondb set quotes "Everyone died, except for those, who didn't." -t anonymous -a year:2024
$ jsondb set quotes "Gunther: Who is the main character from Odyssey? Fred: Mario" -t fred -t gunther -a year:2025

$ jsondb set quotes "Ups, this wasn't intended"

$ jsondb id quotes "ups, this wasn't" --contains --case-insensitive  # Lookup ID from data literal
4
$ jsondb unset quotes 4  # Remove the accidentally added quote... Whoops

# Now what? Let's view the quotes!
$ jsondb browse quotes  # We can also filter by tags using the -f flag. Ex.: `jsondb browse quotes -f gunther`

 ID | DATA
----|------------------------------------------------------------------------------------------
000 | I'm a nice human
001 | Me too
002 | Everyone died, except for those, who didn't.
003 | Gunther: Who is the main character from Odyssey? Fred: Mario

[ID] Select entry     [N] Next     [P] Previous     [E] Exit

> 2  # Selecting ID 2

"Everyone died, except for those, who didn't."

Tags: anonymous
Attributes:
    year: 2024

[E <DATA>] Edit data
[A <TAGS>] Add tag (Can add multiple separated by whitespace)
[R <TAGS>] Remove tag (Can remove multiple separated by whitespace)
[S <ATTRS>] Set attribute (KEY:VALUE) (Can set multiple separated by whitespace)
[U <ATTRS>] Unset attribute (Can unset multiple separated by whitespace)
[D] Delete
[C] Cancel
[H] Help

> C  # Enough browsing, let's get back to our table
...
> E  # Exiting the table as well

$ jsondb query quotes -f fred
1, 3  # IDs of entries with the fred tag

$ jsondb query quotes -f fred -f gunther
3  # Has both tags

# Lastly, we can also format our data! The easiest way to do this is piping the output of query to format.
$ jsondb query quotes | jsondb format quotes  # We can change the format template as well, check jsondb format --help!
[000] "I'm a nice human" [gunther] {year: 2024}
[001] "Me too" [fred] {year: 2024}
[002] "Everyone died, except for those, who didn't." [anonymous] {year: 2024}
[003] "Gunther: Who is the main character from Odyssey? Fred: Mario" [gunther, fred] {year: 2025}

# Let's see what we have done
$ jsondb info quotes
Tags: fred, anonymous, gunther
Size: 4
Bytes: 442
Path: /home/user/Documents/jsondb/quotes.jsondb
Backups enabled: True
Tags enforced: True
```

\
And that's it!
