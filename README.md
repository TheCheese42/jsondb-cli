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
