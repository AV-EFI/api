# AV-EFI API

## Project setup

This is the backend for the AV-EFI project. It uses [FastAPI][1] as a server framework and [Pytest][2] for unit test.
The backend code is under the `app` directory, while unit tests are under the `tests` one.

### Dependency management

[uv][4] is used for dependency management. Besides the main dependencies, the ones that required during development
only are put under the `dev` group. Please make sure to assign new dependencies to the proper group to reduce the
package size in production.

### GitLab CI

This project's pipeline runs tests only. Building and deployment are handled
by the separate
[`av-efi/api-deploy`](https://gitlab.gwdg.de/av-efi/api-deploy) repository.

### Changelog

The changelog of this project is stored in the [CHANGELOG.md](CHANGELOG.md) file. Please make sure to keep it up-to-date
with the development progress.

## Usage

The project is dockerized. To build and run it on your machine, make sure that
[Docker][6] is installed. For deployment at GWDG, see the separate
[`av-efi/api-deploy`](https://gitlab.gwdg.de/av-efi/api-deploy) repository.

In a local checkout of the repository, the easiest way to bring up the
server is via docker-compose using the developer file `docker-compose.dev.yml`.
First, copy the example config (the config directory is mounted read-only into
the container):

```console
$ cp config/config.ini.example config/config.ini
```

Then build the image from the current working directory:

```console
$ docker compose -f docker-compose.dev.yml build
```

And start the server:

```console
$ docker compose -f docker-compose.dev.yml up -d
```

### Ingest AVefi compliant JSON records into PID system

Again, the easiest way is to use docker-compose with the dedicated
`docker-compose.efi-agent.yml` file. In the root directory of a local checkout
of this project, build and run the `efi-agent` service:

```console
$ docker compose -f docker-compose.efi-agent.yml build
$ docker compose -f docker-compose.efi-agent.yml run --rm efi-agent push --help
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

[4]: https://docs.astral.sh/uv/

[6]: https://www.docker.com/

[7]: https://docs.astral.sh/uv/getting-started/installation/
