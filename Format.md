# jsondb format --format help

Because the help message for the --format flag of the format subcommand is hard to read in the terminal, it's also available here as markdown document.

## -f FORMAT, --format FORMAT

A format string used to format the data entries.

The format string may contain the following macros:

`%id(WIDTH, "FILL_CHAR")`:

- WIDTH (optional): A fixed width for the id, defaults to 0
(No fixed width)
- FILL_CHAR (optional): If a fixed WIDTH is set, this fills the
padding, defaults to `"0"`
- Example: `%id(3, "0")` -> `001`, `002`, etc.

`%data(WIDTH, "FILL_CHAR")`:

- WIDTH (optional): A fixed width for the data, defaults to 0
(No fixed width)
- FILL_CHAR (optional): If a fixed WIDTH is set, this fills the
padding, defaults to `" "`
- Example: `%data(12, "⋅")` -> `"Good data⋅⋅⋅"`, `"Better data⋅"`, etc.

`%tags("SEP")`:

- SEP (required): A separator between tag
- Example: `%tags(", ")` -> `Tag1, Tag2, TagN`

`%attrs("SEP1", "SEP2")`:

- SEP1 (required): The separator between key and value
- SEP2 (required): The separator between two key-value pairs
- Example: `%attrs(": ", "; ")` -> `Key1: Value1; Key2: Value2`

The default format string is `'[%id(3)] "%data()" (%tags(", ")) (%attrs(": ","; "))'`

Which will render as:

`[000] "This is a data" (Tag1, Tag2) (Key1: Value1; Key2: Value2)`
`[001] "This is another data (Tag1) (Key1: Value1)`
