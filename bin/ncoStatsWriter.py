#!/usr/bin/python2

import logging
import tempfile
import calendar
import os
import sys
import errno
import base64
import json
import datetime
import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

auth = ""

#######################################################
#
# Function to test if a dir is writable, using tempfile
#
#######################################################

def isWritable(path):
    try:
        testfile = tempfile.TemporaryFile(dir = path)
        testfile.close()
    except OSError as e:
        if e.errno == errno.EACCES:  # 13
            return False
        e.filename = path
        raise
    return True

############################
#
# Function to set up logging
#
############################

def setupLogging(myLoggingLevel):

   if(os.path.isdir(readerHome + "/log")):
      logHome = readerHome + "/log/"

      LOG_FILENAME=logHome + "ncoStatsWriter.log"
      now = datetime.datetime.now()
      ts = now.strftime("%d/%m/%Y %H:%M:%S")
      print("opening log file " + logHome + "/ncoStatsWriter.log")

      if True:
         if myLoggingLevel.upper() == "INFO" or loggingLevel.upper() == "DEBUG":
            if myLoggingLevel.upper() == "INFO":
               logging.basicConfig(level=logging.INFO, filename=LOG_FILENAME, filemode="w+",format="%(asctime)-15s %(levelname)-8s %(message)s")
            else:
               logging.basicConfig(level=logging.DEBUG, filename=LOG_FILENAME, filemode="w+",format="%(asctime)-15s %(levelname)-8s %(message)s")
         else:
            logging.basicConfig(level=logging.INFO, filename=LOG_FILENAME, filemode="w+",format="%(asctime)-15s %(levelname)-8s %(message)s")
            logging.info("WARNING: Unknown loggingLevel specified in ncoStatsReader.props. Must be one of 'INFO' or 'DEBUG'. Defaulting to 'INFO'")
         logging.info("Collection started at: " + ts + "\n")
         #print("FATAL: failed to start logging. Verify logging path available and disk space.")
         #exit()
      else:
         print("Logging level property 'loggingLevel' is not specified in the ncoStatsWriter.props. Defaulting to 'INFO'")
         logging.basicConfig(level=logging.INFO, filename=LOG_FILENAME, filemode="w+",format="%(asctime)-15s %(levelname)-8s %(message)s")
         logging.info("WARNING: Unknown loggingLevel specified in ncoStatsReader.props. Must be one of 'INFO' or 'DEBUG'. Defaulting to 'INFO'")
   else:
      print("FATAL: unable to find log directory at " + readerHome + "log")
      sys.exit()

###############################################
#
# Function to generate timestamp for publishing
#
###############################################

def createTimeStamps():

    tsDict = {}

    starttm = datetime.datetime.utcnow()
    #starttm = starttm - datetime.timedelta(minutes=-10)
    starttm = starttm - datetime.timedelta(minutes=starttm.minute % 5, seconds=starttm.second, microseconds = starttm.microsecond)
    starttm = starttm - datetime.timedelta(minutes=+5)
    endtm = starttm - datetime.timedelta(minutes=-+5)
    startTimeStamp = starttm.strftime("%m%d%y-%H%M")
    endTimeStamp = endtm.strftime("%m%d%y-%H%M")

    tsDict["startTimeStamp"] = startTimeStamp
    tsDict["endTimeStamp"] = endTimeStamp
    return tsDict


######################################################
#
# Function to load and validate datachannel properties
#
######################################################

def loadProperties(filepath, sep='=', comment_char='#'):

    # Read the file passed as parameter as a properties file.

    props = {}
    with open(filepath, "rt") as f:
        for line in f:
            l = line.strip()
            if l and not l.startswith(comment_char) and "=" in l:
                key_value = l.split(sep)
                key = key_value[0].strip()
                value = sep.join(key_value[1:]).strip().strip('"')
                props[key] = value

    return props

#####################################################################
#
# Function to process a metric dictionary passed from a reader client
#
#####################################################################

def processMetrics(metricsDict):

    myTs = createTimeStamps()
    
    #print("Processing this set of metrics for PI interval " + startTime + " - " + endTime + ", unix timestamp is " +myUnixTimeStamp)
    for file in metricsDict:
        myFile = csvLocation + "/" + "netcoolStats__" + myTs["startTimeStamp"]  + "__" + myTs["endTimeStamp"] + ".csv"
        logging.debug("Opening file: " + myFile)
        if not os.path.isfile(myFile):
            myFh = open(myFile, "a")
            myFh.write("Timestamp,Node,Resource,MetricName,MetricValue\n")
            myFh.close()
        myFh = open(myFile, "a")
        for resourceAndMetric in metricsDict[file]["metrics"]:
            logging.debug("Need to write line for:" + resourceAndMetric )
            node = resourceAndMetric.split(":")[0]
            resource = resourceAndMetric.split(":")[1]
            metricName = resourceAndMetric.split(":")[-1]
            metricValue = metricsDict[file]["metrics"][resourceAndMetric]["value"]
            myFh.write(myTs["startTimeStamp"] + "," + node + "," + resource + "," + metricName + "," + str(metricValue) + "\n")
    myFh.close()


class AuthHandler(SimpleHTTPRequestHandler):
    ''' Main class to present webpages and authentication. '''
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self.send_response(204)
        self.end_headers()
        return

    def do_POST(self):

        global auth

        ctype = self.headers.getheader('Content-type')

        if ctype != 'application/json':
            #print("Wrong content-type (must be application/json)")
            self.send_response(400)
            self.end_headers()
            return

        if self.headers.getheader('Authorization') == "Basic " + auth:

            length = int(self.headers.getheader('content-length'))
            message = self.rfile.read(length)

            logging.debug("received the following: " + message)
            try:
                metricsDict = json.loads(message)
            except ValueError as e:
                logging.info("unable to parse json payload sent. Payload: " + str(message))
                logging.info("Error: " + str(e))
                self.send_response(400)
                self.end_headers()
                return
            processMetrics(metricsDict)
            self.send_response(200)
            self.end_headers()
            return

        else:
            self.send_response(401)
            self.end_headers()
            return


if __name__ == '__main__':
        # determine datapump home

    global httpPort
    global readerHome

    pathname = os.path.dirname(sys.argv[0])
    mediatorBinDir = os.path.abspath(pathname) + "/" + sys.argv[0]
    mediatorHome = os.path.dirname(os.path.abspath(pathname))
    readerHome = mediatorHome

    # Read properties

    if(os.path.exists(mediatorHome + "/conf/ncoStatsWriter.conf")):
       props = loadProperties(mediatorHome + "/conf/ncoStatsWriter.conf")
    else:
       print("FATAL: Properties file " + mediatorHome + "/conf/ncoStatsWriter.conf is missing.")
       exit()

    globals().update(props)
    datachannelProps = (props)
    globals().update(datachannelProps)
    port = int(listeningPort)

    # Validate properties


    if 'ncoStatsWriterUsername' not in globals():
       logging.info("FATAL: ncoStatsWriterUsername is not configured")
       exit()
    if 'ncoStatsWriterPassword' not in globals():
       logging.info("FATAL: ncoStatsWriterUsername is not configured")
       exit()
    if 'csvLocation' not in globals():
       logging.info("FATAL: csvLocation is not configured")
       exit()
    if 'loggingLevel' in globals():
       if loggingLevel in [ "INFO", "DEBUG" ]:
          print("Configuring logging at level " + loggingLevel)
          setupLogging(loggingLevel)
       else:
          print("Logging level not defined in ncoStatsReader.conf. Defaulting to INFO")
          loggingLevel = "INFO"
          setupLogging(loggingLevel)

    # Validate CSV file location

    if(os.path.isdir(csvLocation)):
        if not isWritable(csvLocation):
            print("csvLocation (" + csvLocation + ") is not writable!")
            exit()

    auth = base64.b64encode(ncoStatsWriterUsername + ":" + ncoStatsWriterPassword)

    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class(('', port), AuthHandler)
    httpd.serve_forever()
