# wallhelper

- `PRODUCT.md` is the product and design brief (users, principles, anti-references); read it before changing the window or its copy.
- Open work is in GitHub issues (`gh issue list`). What was done and why, and the choices that are deliberate, are `decision` issues; recurring traps are `gotcha` issues. Search before revisiting a choice: `gh issue list --label decision --state all --search <term>` (same for `gotcha`).
- Run tests only through `make test`; they delete files and refuse to run against a real collection.
