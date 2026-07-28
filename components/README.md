# Components

This directory contains exactly three top-level Git submodules pinned by the
toolchain repository:

- `c2go-clang`
- `c2go-bind`
- `c2go-libc`

Their public remotes and exact revisions are recorded in `.gitmodules` and
`toolchain.lock.json`. Initialize them with:

```sh
git submodule update --init --recursive
```

Do not replace them with copied or symlinked local working trees. See
[../RELEASING.md](../RELEASING.md).
