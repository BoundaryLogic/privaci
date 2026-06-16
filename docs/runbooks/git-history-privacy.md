# Runbook: Keeping personal emails out of git history

PrivaCI commits should carry only project or GitHub `noreply` email addresses,
never a contributor's personal email. A CI guard enforces this on every push,
and this page explains how to satisfy it.

## Automated check

```bash
python scripts/check_git_emails.py
```

The script scans every ref reachable from `HEAD` and allows only:

- `*@users.noreply.github.com` and `*@noreply.github.com`
- `*@boundarylogic.io` (org addresses)

CI runs this on every push to `main`. If it fails, a commit (author/committer
field or a `Co-authored-by:` trailer) contains a disallowed address.

## Prevent it: configure git before committing

1. Enable **Keep my email addresses private** in your GitHub settings.
2. Enable **Block command line pushes that expose my email**.
3. Set your local `user.email` to your GitHub `noreply` address:

   ```bash
   git config user.email "12345678+you@users.noreply.github.com"
   ```

## Fix it: rewrite the offending commits

Use `git filter-repo` (not `filter-branch`) with a mailmap and, if a personal
address appears in commit *message* bodies, a message replacement:

```bash
pip install git-filter-repo

# .mailmap — map old personal emails to your noreply address
# old@personal.com <12345678+you@users.noreply.github.com>

git filter-repo --mailmap .mailmap --replace-message expressions.txt --force
```

`expressions.txt` example (rewrites message bodies):

```text
regex:.*@personal\.com==<redacted>
```

Force-push the rewritten branch after coordinating with collaborators.

## Related

- `scripts/check_git_emails.py` — the guard this runbook remediates.
