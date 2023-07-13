# netcool-stats-collector

This project collects performance metrics from Netcool/OMNIbus and Netcool/Impact and centralizes
the metrics as CSV files so that Predictive Insights can read them and analyze them.

## How it works

There are two components to this solution: a reader component (ncoStatsReader) and a writer
component (ncoStatsWriter).

The reader component attaches itself to the specified log files and obtains performance metrics.
It aggregates the performance metrics and sends them via http to the writer component running on 
the Predictive Insights server. The writer component then writes the metrics to a CSV file at a
location specified by its configuration.

In general, there will be a reader component for each Impact and OMNIbus server in the environment
that all report to a single writer component running on the Predictive Insights server.

## Obtaining the solution

Either clone the repository using git:

git clone https://github.com/jason-p-cress/netcool-stats-collector.git

Or download from the GitHub landing page and copy the zip file to the servers where the readers
and writers will run.

## Requirements

Python 2 or Python 3 must be available on the systems that will be running the solution.

The user used to run the solution must have read access to the log files.

The TCP port used by the writer component must be available to the reader components.

## Configuring the reader component

Two files must be configured for the reader component.

### ncoStatsReader.conf

The configuration file located at conf/ncoStatsReader.conf must be configured with the following
properties:

ncoStatsWriterUrl: This will be the URL of where the writer process is running

ncoStatsWriterUsername: username for writer authentication, must match the writer configuration

ncoStatsWriterPassword: password for writer authentication

loggingLevel: set the logging level, either INFO or DEBUG

### files.conf

The files.conf file contains the path and the log file type. The following log file types are
currently supported:

eventprocessor: Impact event processor log
eventreader: Impact event reader log
profilestats: OMNIbus profiler log (use the log file ending in .log1)
triggerstats: OMNIbus trigger stats log (use the log file ending in .log1)


### Running the reader component

Once the reader is configured, you can run the Python script located at bin/ncoStatsReader.py

```
$ bin/ncoStatsReader.py &
```

Note that you may need to modify the first line to specify the location of Python, if it is
not in the default location ( /usr/bin/python ).

## Configuring the writer component

The configuration file located at conf/ncoStatsWriter.conf must be configured with the following
properties:

listeningPort: the TCP port that the writer component will listen on for updates from readers

ncoStatsWriterUsername: the username required for reader authentication

ncoStatsWriterPassword: the password required for reader authentication

csvLocation: the location where the writer will write out the CSV files for PI

loggingLevel: either "INFO" or "DEBUG" - note that DEBUG will create a lot of messages

## Running the writer component

Once the writer is configured, you can run the Python script located at bin/ncoStatsWriter.py:

```
$ bin/ncoStatsWriter.py &
```

