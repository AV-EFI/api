# AV-EFI API

## Project setup

This is the backend for the AV-EFI project. It uses [FastAPI][1] as a server framework and [Pytest][2] for unit test.
The backend code is under the `app` directory, while unit tests are under the `tests` one.

### Dependency management

[uv][4] is used for dependency management. Besides the main dependencies, the ones that required during development
only are put under the `dev` group. Please make sure to assign new dependencies to the proper group to reduce the
package size in production.

### GitLab CI

This project is set up with GitLab CI. The configuration can be found at [`.gilab-ci.yml`](.gitlab-ci.yml). Currently,
for every commit:

1. If the commit is done on the non-default branch (not the `main` branch), a Docker image is built and has the same
   name as the branch name.
2. For commits on the default branch (`main`), only tests are executed
   but no Docker image is built except when a new version is released.
   The latter should be done by executing the [`release.sh`
   script](./release.sh). This will bump and commit the version
   locally, add the corresponding tag and push it, hence triggering
   the release pipeline which includes:
    1. Read the new version by means of `uv version --show`.
    2. Build a new Docker container and tag it with the `latest` tag and the version tag.
    3. Release a new version on GitLab. GitLab releases can be found [here][3].

Please note that executing the `release.sh` script requires a
developer setup as described further down in this README.

### Changelog

The changelog of this project is stored in the [CHANGELOG.md](CHANGELOG.md) file. Please make sure to keep it up-to-date
with the development progress. The content of this file is used as a release note for every GitLab release.

## Usage

The project is dockerized and its images are stored in the [project container registry][5]. To run it on your machine,
make sure that [Docker][6] is installed.

In a local checkout of the repository, the easiest way to bring up the
server is via docker-compose. First, log into the container registry
and pull the latest image:

```console
$ docker login docker.gitlab.gwdg.de
$ docker-compose pull
```

Alternatively, you can build the image locally:

```console
$ docker-compose build
```

Then start the server:

```console
$ docker-compose up -d
```

Alternatively, to start the server, execute the commands below:

```shell
# Log in to GitLab
$ docker login docker.gitlab.gwdg.de

# Download and run the server in the background
$ docker run --name efi-api --detach --publish 8000:8000 docker.gitlab.gwdg.de/av-efi/api:<tag or branch_name>
```

### Ingest AVefi compliant JSON records into PID system

Again, the easiest way is to use docker-compose. In the root directory
of a local checkout of this project, pull the image from the container
registry:

```console
# Log in to GitLab
$ docker login docker.gitlab.gwdg.de
# Pull image
$ docker-compose pull
```



```console
$ efi-agent push --help
Usage: efi-agent push [OPTIONS] INPUT_FILE

  Push AVefi records to the handle system, updating or creating PIDs.

Options:
  -j, --journal FILE  Journal where actions on PIDs are to be recorded.
  -p, --profile FILE  Profile for the described_by slot in the AVefi schema.
  --prefix TEXT       Prefix to be used when generating handles.
  --suffix TEXT       Suffix to be used when generating handles.
  --help              Show this message and exit.
```

The profile parameter determines who will be recorded as data provider
in the described_by slots of the generated PIDs. It should be a JSON
file similar to this:

```yaml
{
  "has_issuer_id": "https://w3id.org/isil/DE-89",
  "has_issuer_name": "Technische Informationsbibliothek (TIB)",
}
```

This is specified as part of the [AVefi schema][].

[AVefi schema]: https://av-efi.github.io/av-efi-schema/


## For developers

- [Install uv][7]. Make sure that it is **not** installed in the same
  virtual environment of this project, since it might cause some side
  effects.
- Run `uv sync --no-python-downloads` initially, a simple `uv sync` is
  sufficient for subsequent updates.
- In order to ensure coding style consistency, please also
  activate pre-commits as follows:
  ```console
  $ pipx install pre-commit
  $ pre-commit install
  ```
- The project is ready for development.

Please note that the ruff code formatter fails to strictly comply with
the max-line-length limit sometimes. Since this makes the checker fail
on subsequent runs, ether reformatting or checking has to be prevented
by means of appropriate pragma comments. Here are examples of the two
options:

```python
def imagine_very_long_function_name(with_long_argument_names):  # noqa: E501 (disable length limit check on this line)
    return {
        "long_key_name_for_a_url":  # fmt: skip (prevent reformatting)
        "https://www.example.invalid/just/some/longish/demo/url/"
    }
```

## Index maintenance

A rebuild of search indices can be triggered manually by issuing the
following command:

```shell
$ uv run rebuild_search_index
```

[1]: https://fastapi.tiangolo.com/

[2]: https://docs.pytest.org/en/8.0.x/

[3]: https://gitlab.gwdg.de/av-efi/api/-/releases

[4]: https://docs.astral.sh/uv/

[5]: https://gitlab.gwdg.de/av-efi/api/container_registry/3087

[6]: https://www.docker.com/

[7]: https://docs.astral.sh/uv/getting-started/installation/
