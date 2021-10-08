# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

PyPi: [https://pypi.org/project/django-changeset/](https://pypi.org/project/django-changeset/).

## [1.1.0 - unreleased]

## [1.0.0]
### Added
- Support for Django 2.2 and 3.0
- Support for Python 3.7 and 3.8
- Added test project
### Removed
- Dropped support for Django releases prior to 2.2
- Dropped support for Python 2
- Dropped support for Python 3 releases prior to 3.5

## [1.0rc3]
### Added
- Tracking for generic relations

## [1.0rc2]
### Changed
- Updated README and docs

## [1.0rc1]
### Added
- `track_related_many` to track related fields with many to one relations
- Support for backwards relations
- Soft-delete functionality
- Tracking for many-to-many relations
- Changeset aggregation
### Changed
- Many-to-many relations are now displayed as comma separated strings
- Improved performance with bulk creates

## [0.7.1]
### Added
- Setting `DJANGO_CHANGESET_SELECT_RELATED`

## [0.7]
### Added
- Support for generic relations

## [0.6.2]
### Fixed
- Fixed issue with earliest changeset not being set

## [0.6.1]
### Added
- Support for Django 1.11

### Changed
- Better user caching

## [0.6.0]
### Added
- Support for Python 3.6

### Changed
- Increased performance

## [0.5.1]
### Changed
- Added database index for changeset type and date

## [0.5]
### Added
- Support for many to many relationships

## [0.4.4]
### Changed
- Improved performance of created_by and last_modified_by

## [0.4.3]
### Changed
- Rewrite of querysets for UUID fields in Postgres

## [0.3]
### Added
- `__all__` as an option for `track_fields` (planned)

## [0.2]
### Added
- Added `user.all_changes`
- Added `user_related_name` meta class field and `user.get_$user_related_name$()` method
### Changed
- `track_related` fields should automatically determine the `related_name` attribute of foreign keys

## [0.1]
Legacy release with examples, documentation and tests

[1.1.0 - unreleased]: https://github.com/beachmachine/django-changeset/compare/1.0.0...HEAD
[1.0.0]: https://github.com/beachmachine/django-changeset/compare/1.0rc3...1.0.0
[1.0rc4]: https://github.com/beachmachine/django-changeset/compare/1.0rc3...1.0rc4
[1.0rc3]: https://github.com/beachmachine/django-changeset/compare/1.0rc2...1.0rc3
[1.0rc2]: https://github.com/beachmachine/django-changeset/compare/1.0rc1...1.0rc2
[1.0rc1]: https://github.com/beachmachine/django-changeset/compare/0.7.1...1.0rc1
[0.7.1]: https://github.com/beachmachine/django-changeset/compare/0.7...0.7.1
[0.7]: https://github.com/beachmachine/django-changeset/compare/0.6.2...0.7
[0.6.2]: https://github.com/beachmachine/django-changeset/compare/0.6.1...0.6.2
[0.6.1]: https://github.com/beachmachine/django-changeset/compare/0.6.0...0.6.1
[0.6.0]: https://github.com/beachmachine/django-changeset/compare/0.5.1...0.6.0
[0.5.1]: https://github.com/beachmachine/django-changeset/compare/0.5...0.5.1
[0.5]: https://github.com/beachmachine/django-changeset/compare/0.4.4...0.5
[0.4.4]: https://github.com/beachmachine/django-changeset/compare/0.4.3...0.4.4
[0.4.3]: https://github.com/beachmachine/django-changeset/releases/tag/0.4.3
