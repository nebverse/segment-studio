# Repository maintenance and distribution

[← Home](README.md) · [Development checks](DEVELOPMENT.md) · [Licensing](LICENSING.md)

The existing distribution repository is [nebverse/segment-studio](https://github.com/nebverse/segment-studio). Do not reinitialize it or overwrite its history. Keep the internal FireMask workspace separate from the portable Segment Studio package.

## Update an existing clone

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c feature/your-change
```

Port only tested changes, adapting environment names, relative paths and output conventions. Review [development checks](DEVELOPMENT.md). The internal development computer can use its own existing environment for lightweight tests; fresh install checks belong on a separate Windows machine.

```powershell
git status --short
git diff --check
# Stage the intended source, test and documentation files.
git add README.md
git diff --cached --stat
git diff --cached --check
git commit -m "Describe the change"
git push -u origin feature/your-change
```

The staging example is documentation-only; explicitly stage other intended files for code changes. Open a pull request, review and merge into main. Synchronize locally, then optionally delete the merged branch.

## Safe sharing

Share the repository URL with authorized collaborators and point them to [Installation](INSTALLATION.md). They can download ZIP without Git or clone and choose their model setup. They do not need the internal FireMask environment.

Review every staged file. Never commit weights, external clones, .local/config.json, tokens, research images, masks, annotation outputs or private paths. If a secret was committed, rotate/revoke it and clean history as appropriate; deleting the current copy is insufficient.

Keep private visibility until publication and licensing are approved by the relevant owners/institution. For a genuinely new repository, use GitHub's [new repository page](https://github.com/new), create an empty private repository, and initialize/push a clean source folder only after reviewing every staged filename. Do not do that for this existing repository.
