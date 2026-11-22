# Publish Segment Studio on GitHub

## 1. Check what is allowed to be public

Ask the project supervisor/lab before publishing unpublished research images,
annotations, internal dataset paths or code. Do not assume you can license
the source on behalf of your lab; review [licensing](LICENSING.md) before
public release. Official Meta models and checkpoints are not
included and retain their own license/access terms.

## 2. Create an EMPTY repository on GitHub

Open <https://github.com/new>. Suggested settings:

- Repository name: `segment-studio`
- Description: `Local SAM-assisted image segmentation and mask annotation editor`
- Visibility: **Private** until you have approval to publish; change it later.
- **Do not** add GitHub's README or .gitignore during creation; they
  are already in the ZIP. Select a license later once the rights are clear.

## 3. Commit the extracted folder from PowerShell

Open a Conda terminal in your extracted `segment-studio` folder. First ensure
Git works. Installing through `SETUP_WINDOWS.ps1` creates Git in the GUI Conda
environment, so if it is not in your shell yet use:

```powershell
conda activate segment_studio
git --version
```

Then run:

```powershell
git init -b main
git add .
git status --short
```

**Review every staged filename**. No `sam3.pt`, `.pt`, `.pth`, real `.jpg` / `.png`,
research data, `segment_studio_output`, `.local/config.json`, access tokens or any
private files should appear. If they do, stop and remove them from staging and
extend `.gitignore` **before** committing.

```powershell
git commit -m "Initial Segment Studio application and Windows setup"
git remote add origin https://github.com/YOUR_USERNAME/segment-studio.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub account or organizational namespace.
GitHub may prompt you to authenticate in a browser or use a credential manager.
GitHub account passwords are not accepted as Git HTTPS authentication.

Alternatively, install [GitHub Desktop](https://desktop.github.com/) and use
**File → Add local repository** to publish the extracted directory.

## 4. Share installation instructions

Give collaborators the repository URL. They can use **Code → Download ZIP**, or:

```powershell
git clone https://github.com/YOUR_USERNAME/segment-studio.git
cd segment-studio
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

If they have approved SAM3 access, they can choose:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1 -WithSAM3
```

## 5. Update the code later

Modify and test the code locally, then:

```powershell
git status
git add segment_studio.py mask_utils.py sam_backends.py
# Or git add . after verifying nothing private is staged.
git commit -m "Improve annotation editing"
git push
```

Collaborators can update source code using `git pull`. Their downloaded models
and `.local/config.json` are ignored and should remain in place. Avoid edits
inside the ignored `external/` clones unless you intend to maintain a separate
upstream fork; such edits are not part of this repository.

If a secret was ever committed, simply deleting it from the current commit is
not enough; revoke/rotate the key and clean repository history as appropriate.
