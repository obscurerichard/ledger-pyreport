FROM python:3.10-bullseye

ENV ledger_version=3.3.2
# Get ledger compiled & installed 
# Install prerequisites per per https://github.com/ledger/ledger#debian
RUN apt-get -q update && \
     apt-get -q install -y build-essential cmake autopoint texinfo python3-dev \
     zlib1g-dev libbz2-dev libgmp3-dev gettext libmpfr-dev \
     libboost-date-time-dev libboost-filesystem-dev \
     libboost-graph-dev libboost-iostreams-dev \
     libboost-python-dev libboost-regex-dev libboost-test-dev
RUN curl -L -s -O https://github.com/ledger/ledger/archive/refs/tags/v${ledger_version}.tar.gz &&  \
    tar xvfz v${ledger_version}.tar.gz && \
    cd ledger-${ledger_version} && \
    ./acprep update && \
    install ledger /usr/local/bin

# Get ledger_pyreport installed and configured
RUN addgroup app && adduser --no-create-home --ingroup app app
RUN mkdir -p /app/ledger_pyreport
COPY MANIFEST.in pyproject.toml /app
COPY ledger_pyreport /app/ledger_pyreport
RUN cd /app && pip3 install .

# Use the demo files by default. See the README.md file for
# instructions about running it with your config.yml and ledger files.
RUN mkdir -p /data
COPY demo/* /data
ENV FLASK_APP=ledger_pyreport
ENV LEDGER_PYREPORT_CONFIG=/data/config.yml
USER app
EXPOSE 5000
WORKDIR /data
# Thanks https://stackoverflow.com/a/7027113/424301 for the host tip
ENTRYPOINT ["python3", "-m", "flask", "run", "--host=0.0.0.0"]
