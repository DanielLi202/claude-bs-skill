# /bs-refresh-contract

Explicitly refresh the repository binding to a reviewed bs contract release.

## Flow

1. Resolve repo root and validate current `.bootstrap.yaml` enough to read contract fields.
2. Fetch the reviewed release raw URL. Do not use a GitHub blob URL.
3. Compute sha256 of the fetched `contract.md`.
4. Update the installed skill contract only when the user explicitly selected that release.
5. Write both:
   - `.bootstrap.yaml.contract.source_tag/source_url/source_commit/source_sha256`;
   - `.bootstrap/contract.sha256`.
6. Run binding/backlog validation and the repo verify command.
7. Do not commit automatically unless the user asked this command to commit.
