# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Project setup
- Versioned prefix /rest/v1/ for all endpoints except authentication
  callbacks.
- Endpoints /frontend/search and /frontend/view.
- OAuth2 authentication against Academiccloud with routes under /auth
  without the /rest/v1 prefix.
- Endpoint /matches identifying work efi candidates for merging.
- Submission intake validation with the packaged `avefi_validate` rules:
  JSON Schema, field limits, identifiers, local references, dangling
  records, the placeholder issuer, Removed items without a PID, and
  reference cycles.
- A flat `422` response for rejected submissions with `invalid`,
  `dependants`, `truncated`, the validator fingerprint, and capped
  diagnostics.
- The validator/schema fingerprint is stored on accepted submission jobs.

### Changed

- Scheduler ordering is derived from the validator's directed relations.
  Symmetric `same_as` and `is_copy_of` links are references only, and Item
  `same_as` is tracked so PIDs are rewritten without creating a dependency
  cycle.
