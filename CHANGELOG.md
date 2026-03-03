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
