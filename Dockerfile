FROM python:3.7-slim

# Need git for installing aiomysql
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
        git && \
    apt-get clean
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /code/
COPY Pipfile.lock Pipfile.lock
COPY Pipfile Pipfile

RUN python3 -m pip install pipenv
RUN pipenv install --ignore-pipfile --system --deploy

COPY . /code/

ARG TRAVIS_TAG
ENV VERSION=$TRAVIS_TAG
RUN python3 -m pip install -e .

# Main entrypoint and the default command that will be run
CMD ["/usr/local/bin/python3", "service.py"]

RUN python3 -V
