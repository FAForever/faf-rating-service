# FA Forever - Rating Service

This is a draft of the [Forged Alliance Forever](http://www.faforever.com/) rating service.

## Installation

Install [docker](https://www.docker.com).

Follow the steps to get [faf-db](https://github.com/FAForever/db) setup, the following assumes the db container is called `faf-db` and the database is called `faf` and the root password is `banana`.

Additionally, the service needs a running RabbitMQ server, which can be started
via docker by running `ci/init-fabbitmq.sh`,
which starts a RabbitMQ server on vhost `/faf-lobby`.

## Setting up for development

First make sure you have instances of `faf-db` and RabbitMQ running as described in the
installation section. Then install the dependencies to a virtual environment
using pipenv:

    $ pipenv install --dev

You can start the service:

    $ pipenv run devserver

**Note** *The pipenv scripts are not meant for production deployment. For
deployment use `faf-stack`*

## Running the tests

Run

    $ pipenv run tests

## Other tools

You can check for possible unused code with `vulture` by running:

    $ pipenv run vulture

# License

GPLv3. See the [license](license.txt) file.
