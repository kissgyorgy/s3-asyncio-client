# Changelog

All notable changes to S3 Asyncio Client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation with MkDocs Material
- GitHub Actions workflow for automated testing
- Performance benchmarking suite
- Integration tests for multiple S3-compatible services

### Changed
- Improved error messages with more context
- Enhanced multipart upload with progress tracking

### Deprecated
- None

### Removed
- None

### Fixed
- None

### Security
- None

## [0.1.0] - 2024-01-15

### Added
- Initial release of S3 Asyncio Client
- Core S3 operations:
  - `put_object`: Upload objects to S3
  - `get_object`: Download objects from S3
  - `head_object`: Get object metadata
  - `list_objects`: List objects in bucket with pagination
  - `generate_presigned_url`: Create time-limited URLs
- Multipart upload support for large files
- AWS Signature Version 4 authentication
- Support for S3-compatible services (MinIO, DigitalOcean Spaces, etc.)
- Comprehensive exception hierarchy:
  - `S3Error`: Base exception class
  - `S3ClientError`: 4xx client errors
  - `S3ServerError`: 5xx server errors
  - `S3NotFoundError`: 404 not found errors
  - `S3AccessDeniedError`: 403 access denied errors  
  - `S3InvalidRequestError`: 400 bad request errors
- Async context manager support
- Full test suite with pytest and moto
- Type hints throughout the codebase
- Modern Python packaging with uv and pyproject.toml
- Code quality tools: ruff for linting and formatting

### Technical Details
- Python 3.11+ support
- Built on aiohttp for async HTTP operations
- Minimal dependencies (only aiohttp required)
- Comprehensive error handling and parsing
- Virtual hosted-style and path-style URL support
- Proper HTTP session management with connection pooling

---

## Release Notes Template

When creating new releases, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features and capabilities

### Changed  
- Changes to existing functionality

### Deprecated
- Features that will be removed in future versions

### Removed
- Features removed in this version

### Fixed
- Bug fixes

### Security
- Security improvements and fixes
```

## Version History

| Version | Release Date | Python | Key Features |
|---------|--------------|--------|---------------|
| 0.1.0   | 2024-01-15   | 3.11+  | Initial release with core S3 operations |

## Migration Guide

### From 0.x to 1.0

*No migration needed yet - this will be populated when we reach 1.0*

## Roadmap

### Planned for 0.2.0
- [ ] Object versioning support
- [ ] Server-side encryption options
- [ ] Bucket operations (create, delete, list buckets)
- [ ] Object tagging support
- [ ] Advanced multipart upload features (resume, progress callbacks)

### Planned for 0.3.0
- [ ] Streaming upload and download
- [ ] Batch operations optimization
- [ ] Enhanced S3 Select support
- [ ] Cross-region replication utilities

### Planned for 1.0.0
- [ ] Stable API guarantee
- [ ] Performance optimizations
- [ ] Advanced authentication methods
- [ ] Comprehensive S3 feature parity

## Breaking Changes Policy

We follow semantic versioning strictly:

- **PATCH versions** (0.1.1, 0.1.2): Bug fixes only, no breaking changes
- **MINOR versions** (0.2.0, 0.3.0): New features, backward compatible
- **MAJOR versions** (1.0.0, 2.0.0): Breaking changes allowed

### What Constitutes a Breaking Change

- Removing or renaming public API methods
- Changing method signatures (parameters, return types)
- Changing exception types or hierarchy
- Changing default behavior
- Removing support for Python versions

### Deprecation Policy

Before removing features:

1. **Deprecation Warning**: Feature marked as deprecated with warning
2. **Migration Guide**: Documentation on how to migrate
3. **Grace Period**: At least one minor version before removal
4. **Final Removal**: Only in major version releases

## Contributing to Changelog

When contributing:

1. **Add entries** to the `[Unreleased]` section
2. **Use appropriate categories**: Added, Changed, Deprecated, Removed, Fixed, Security
3. **Write clear descriptions**: Explain what changed and why
4. **Reference issues/PRs**: Include links where relevant
5. **Consider users**: Write from the user's perspective

### Example Entry

```markdown
### Added
- New `copy_object` method for server-side object copying (#123)
- Support for custom S3 endpoints with path-style URLs (#145)

### Fixed  
- Fixed multipart upload progress calculation for large files (#156)
- Resolved connection leak in error scenarios (#167)
```

## Release Process

1. **Update version** in `pyproject.toml`
2. **Move unreleased items** to new version section
3. **Update version table** and release date
4. **Create git tag**: `git tag v0.1.0`
5. **Push changes**: `git push && git push --tags`
6. **GitHub Actions** will handle the rest (PyPI release, docs deploy)

---

*This changelog is automatically included in the documentation and package releases.*