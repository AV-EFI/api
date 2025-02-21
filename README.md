# AV-EFI API

## Project setup

This is the backend for the AV-EFI project. It uses [FastAPI][1] as a server framework and [Pytest][2] for unit test.
The backend code is under the `efi_api` directory, while unit tests are under the `tests` one.

### Dependency management

[Poetry][4] is used for dependency management. Besides the main dependencies, the ones that required during development
only are put under the `dev` group. Please make sure to assign new dependencies to the proper group to reduce the
package size in production.

### GitLab CI

This project is set up with GitLab CI. The configuration can be found at [`.gilab-ci.yml`](.gitlab-ci.yml). Currently,
for every commit:

1. If the commit is done on the non-default branch (not the `main` branch), a Docker image is built and has the same
   name as the branch name.
2. If the commit is done on the default branch (`main` branch), it means that a new version is available. Therefore, a
   release process will be triggered. This includes:
    1. Read the new version from the [`VERSION`](app/VERSION) file.
    2. Build a new Docker container and tag it with the `latest` tag and the version tag.
    3. Release a new version on GitLab. GitLab releases can be found [here][3].

:warning: :warning: :warning:

If a commit is done to the default branch without bumping to a new version in the [`VERSION`](app/VERSION)
file, the GitLab release step will throw an error due to the version conflict.

### Changelog

The changelog of this project is stored in the [CHANGELOG.md](CHANGELOG.md) file. Please make sure to keep it up-to-date
with the development progress. The content of this file is used as a release note for every GitLab release.

## Usage

The project is dockerized and its images are stored in the [project container registry][5]. To run it on your machine,
make sure that [Docker][6] is installed.

In a local checkout of the repository, the easiest way to bring up the
server is via docker-compose as follows:

```shell
$ docker-compose up -d
```

Alternatively, to start the server, execute the commands below:

```shell
# Log in to GitLab
$ docker login docker.gitlab.gwdg.de

# Download and run the server in the background
$ docker run --name efi-api --detach --publish 8000:8000 docker.gitlab.gwdg.de/av-efi/api:<tag or branch_name>
```

At the login step, provide your username and token for authentication. Then, make sure that you have enough right to
pull images from the project. Otherwise, an `Access Denied` error will be thrown.

## For developer

- Install [Poetry][4]. Make sure that it is **not** installed in the same virtual environment of this project, since it might
  cause some side effects. Please check the [documentation][7] for more information.
- Run `poetry install`.
- The project is ready for development.

## Index maintenance

A rebuild of search indices can be triggered manually by issuing the
following command:

```shell
$ poetry run rebuild_search_index
```

[1]: https://fastapi.tiangolo.com/

[2]: https://docs.pytest.org/en/8.0.x/

[3]: https://gitlab.gwdg.de/av-efi/api/-/releases

[4]: https://python-poetry.org/

[5]: https://gitlab.gwdg.de/av-efi/api/container_registry/3087

[6]: https://www.docker.com/

[7]: https://python-poetry.org/docs/
