# Components

This directory is intentionally empty in the pre-release scaffold.

After the controlled `c2gohq` repositories exist, it will contain exactly
three top-level Git submodules:

- `c2go-clang`
- `c2go-bind`
- `c2go-libc`

Do not copy or symlink local working trees into this directory. Activate the
submodules only with reachable remotes and reviewed immutable commits, following
[../RELEASING.md](../RELEASING.md).
