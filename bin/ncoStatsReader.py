#!/usr/bin/python

logFileTypes = { "eventreader", "eventprocessor", "masterstats", "triggerstats", "profilestats" }

import base64
#import urllib2
import threading
import json
import datetime
import signal
import time
import os
import sys
import re
import logging

try: 
    import urllib.request as urllib2
except ImportError:
    import urllib2

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
    endtm = starttm - datetime.timedelta(minutes=-5)
    startTimeStamp = starttm.strftime("%m%d%y-%H%M")
    endTimeStamp = endtm.strftime("%m%d%y-%H%M")

    tsDict["startTimeStamp"] = startTimeStamp
    tsDict["endTimeStamp"] = endTimeStamp
    return tsDict
    

############################
#
# Function to set up logging
#
############################

def setupLogging(myLoggingLevel):

   if(os.path.isdir(readerHome + "/log")):
      logHome = readerHome + "/log/"

      LOG_FILENAME=logHome + "ncoStatsReader.log"
      now = datetime.datetime.now()
      ts = now.strftime("%d/%m/%Y %H:%M:%S")
      print("opening log file " + logHome + "/ncoStatsReader.log")

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
         print("Logging level property 'loggingLevel' is not specified in the ncoStatsReader.props. Defaulting to 'INFO'")
         logging.basicConfig(level=logging.INFO, filename=LOG_FILENAME, filemode="w+",format="%(asctime)-15s %(levelname)-8s %(message)s")
         logging.info("WARNING: Unknown loggingLevel specified in ncoStatsReader.props. Must be one of 'INFO' or 'DEBUG'. Defaulting to 'INFO'")
   else:
      print("FATAL: unable to find log directory at " + readerHome + "log")
      sys.exit()

#################################################
#
# Generic function to load properties from a file
#
#################################################

def loadProperties(filepath, sep='=', comment_char='#'):
    """
    Read the file passed as parameter as a properties file.
    """
    props = {}
    with open(filepath, "rt") as f:
        for line in f:
            l = line.strip()
            if l and not l.startswith(comment_char):
                key_value = l.split(sep)
                key = key_value[0].strip()
                value = sep.join(key_value[1:]).strip().strip('"')
                props[key] = value
    return props

##########################
#
# Shutdown request handler
#
##########################

def shutdownHandler(*args):
   shutdownRequest = True
   raise SystemExit('Exiting')


#############################
#
# Reconfigure request handler
#
#############################

def reconfigHandler(*args):

   # Currently not implemented 

   logging.info("###############################################")
   logging.info("#                                             #")
   logging.info("# Re-reading datachannel configuration file.. #")
   logging.info("#                                             #")
   logging.info("###############################################")


######################################################################
#
# Function to read the files.conf file to obtain log files of interest
#
######################################################################

def getLogFileConfig(sep=',', comment_char='#'):

   global readerHome
   global readerBinDir

   props = {}
   pathname = os.path.dirname(sys.argv[0])
   readerBinDir = os.path.abspath(pathname) + "/" + sys.argv[0]
   readerHome = os.path.dirname(os.path.abspath(pathname)) 
   print("Starting stats collection at home " + readerHome)
   if( os.path.exists(readerHome + "/conf/files.conf")):
      with open(readerHome + "/conf/files.conf", "rt") as f:
           for line in f:
               l = line.strip()
               if l and not l.startswith("#") and "," in l:
                   key_value = l.split(",")
                   key = key_value[0].strip()
                   value = sep.join(key_value[1:]).strip().strip('"')
                   if(os.path.exists(key)):
                      if(value in logFileTypes):
                         props[key] = value
                      else:
                         print("Unknown log file type " + value + ". Should be one of " + str(logFileTypes))
                   else:
                      print("Unable to find configured file located at " + key)
   else:
       print("FATAL: Unable to find the log file configuration file located at " + readerHome + "/conf/files.conf")

   for entry in props:
       logging.debug(entry + "==" + props[entry])
   
   return(props)


def initMetricDict(myLog, logfiletype):

    # set common attributes for our dictionary
    logFileName =  myLog.split('/')[-1]
    logStats[logFileName] = {}
    logStats[logFileName]["metrics"] = {}
    logStats[logFileName]["logFileType"] = logfiletype
    logStats[logFileName]["logFileFullPath"] = myLog
    logStats[logFileName]["inode"] = os.stat(myLog).st_ino
    logStats[logFileName]["rolled"] = False

    # set specific attributes for our dictionary, based on the log type
        
    if logfiletype == "eventreader":
        # attempt to identify the name of the impact server from logfile name
        impactServerName = myLog.split('/')[-1].split('_')[0]
        eventReaderName = myLog.split(impactServerName + "_")[-1]
        logStats[logFileName]["resourceNode"] = impactServerName
        logStats[logFileName]["resourceApp"] = eventReaderName.replace(".log", "")
    if logfiletype == "eventprocessor":
        impactServerName = myLog.split('/')[-1].split('_')[0]
        eventProcessorName = myLog.split(impactServerName + "_")[-1]
        logStats[logFileName]["resourceNode"] = impactServerName
        logStats[logFileName]["resourceApp"] = eventProcessorName.replace(".log", "")
    if logfiletype == "profilestats":
        omnibusServerName = logFileName.split('_profiler_report')[0]
        logStats[logFileName]["resourceNode"] = omnibusServerName
        logStats[logFileName]["resourceApp"] = ""
    if logfiletype == "triggerstats":
        omnibusServerName = logFileName.split('_trigger_stats')[0]
        logStats[logFileName]["resourceNode"] = omnibusServerName
        logStats[logFileName]["resourceApp"] = ""

def postMetricToWriter(myMetricDict):

     method = "POST"
     requestUrl = ncoStatsWriterUrl
   
     userAndPass = ncoStatsWriterUsername + ":" + ncoStatsWriterPassword
     authHeader = 'Basic ' + base64.b64encode(userAndPass.encode("utf-8")).decode()
  
     try:
        request = urllib2.Request(requestUrl, json.dumps(myMetricDict).encode("utf-8"))
        request.add_header("Content-Type",'application/json')
        request.add_header("Accept",'application/json')
        request.add_header("Authorization",authHeader)
        request.get_method = lambda: method
  
        response = urllib2.urlopen(request)
        xmlout = response.read()
        return 0
  
     except IOError as e:
        logging.info('Failed to open "%s".' % requestUrl)
        if hasattr(e, 'code'):
           logging.info('We failed with error code - %s.' % e.code)
           return e.code
        elif hasattr(e, 'reason'):
           logging.info("The error object has the following 'reason' attribute :")
           logging.info(e.reason)
           logging.info("This usually means the server doesn't exist, is down, or we don't have a network connection")
           return e.reason


def publisher():

   outputDir = "/home/ncoadmin/netcool-impact-omnibus-datachannel/csv"

   myTs = createTimeStamps()

   while True:
      if(datetime.datetime.now().minute % 5 == 0 and datetime.datetime.now().second == 0):
         myTimestamp = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
         # publish metrics - csv file, api, or kafka
         if(debug == True):
            logging.debug("##########################################")
            logging.debug(" PUBLISHING:                              ")
            logging.debug("##########################################")
         logStatsCopy = logStats.copy()
         #logStatsCopy[source]["startTimeStamp"] = myTs["startTimeStamp"]
         #logStatsCopy[source]["endTimeStamp"] = myTs["endTimeStamp"]
         for source in logStats:
            logStats[source]["startTimeStamp"] = myTs["startTimeStamp"]
            logStats[source]["endTimeStamp"] = myTs["endTimeStamp"]
            for metric in logStats[source]["metrics"]:
               logStats[source]["metrics"][metric]["resetCounter"] = True
         postMetricToWriter(logStatsCopy)
         time.sleep(1)
      time.sleep(0.1)

def processLine(myLog, logfiletype, line):

   logFileName =  myLog.split('/')[-1]

   if logfiletype == "eventreader":
      pattern = re.compile('.*? Read: (.*) .*New Read: (.*) .*Updates: (.*) .*OSQueue: (.*) .*ReadBuffer: (.*) .*NumReaderBuffer: (.*) .*?Time: (.*) .*Events Read/Sec: (.*) .*?New Events Read/Sec: (.*) .*Memory: (.*)$')
      vals = re.findall(pattern, line)
      eventReaderMetrics = [ "Read", "NewRead", "Updates", "OSQueue", "ReadBuffer", "NumReaderBuffer", "Time", "EventsReadSec", "NewEventsReadSec", "Memory" ]
      resourceAll = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + logStats[logFileName]["resourceApp"].replace(":", "-")
      if(len(vals) > 0):
         metricsRead = vals[0]
         if(len(metricsRead) == 10):
            for position in range(10):
               resourceAndMetric = resourceAll + ":" + eventReaderMetrics[position]
               if( resourceAndMetric not in logStats[logFileName]["metrics"]):
                  logStats[logFileName]["metrics"][resourceAndMetric] = {}
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = 0
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
               if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] is True):
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = int(float(metricsRead[position]))
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
               else:
                  currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = (currentMetricValue + int(float(metricsRead[position]))) / 2
            if(debug == True):
               logging.debug("here are the metrics after this read: " + str(logStats[logFileName]))

   elif logfiletype == "eventprocessor":
      logFileName =  myLog.split('/')[-1]
      eventProcessorMetrics = [ "CurrentQueueSize", "DeltaQueue", "EventRatePerMinute", "ProcessingThreads" ]
      pattern = re.compile('.*? Current Queue Size: (.*) .*Delta Queue: (.*) .*Rate: (.*) events/min.*Number of Processing Threads: (.*)$') 
      vals = re.findall(pattern, line)

      resourceAll = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + logStats[logFileName]["resourceApp"].replace(":", "-")
      if(len(vals) > 0):
         metricsRead = vals[0]
         if(len(metricsRead) == len(eventProcessorMetrics)):
            for position in range(len(eventProcessorMetrics)):
               resourceAndMetric = resourceAll + ":" + eventProcessorMetrics[position]
               if( resourceAndMetric not in logStats[logFileName]["metrics"]):
                  logStats[logFileName]["metrics"][resourceAndMetric] = {}
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = 0
               if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] == True):    # or logStats[logFileName]["metrics"][eventReaderMetrics[position]].get("value") is None):
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = int(float(metricsRead[position]))
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
               else:
                  currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = (currentMetricValue + int(float(metricsRead[position]))) / 2
            #if(debug == True):
            logging.debug("here are the metrics for this read: " + str(logStats[logFileName]))


   elif logfiletype == "masterstats":
       logging.debug("processing master stats line - not implemented yet")
   elif logfiletype == "triggerstats":
       # Wed Jul 12 14:52:44 2023:     Trigger time for 'resync_finished': 0.000000s
       # Wed Jul 12 14:52:44 2023: Time for all triggers in report period (60s): 0.015309s
       #logging.debug("processing trigger stats line - not implemented yet")
       logFileName = myLog.split('/')[-1]
       profileMetrics = [ "TotalTriggersIducTime" ]
       pattern = re.compile('.*Time for all triggers in report .*\: (.*)s$')
       vals = re.findall(pattern, line)
       if(len(vals) > 0):
          resourceAndMetric = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + ":TotalTriggersIducTime"
          if(logStats[logFileName]["metrics"].get(resourceAndMetric) is None):
             logStats[logFileName]["metrics"][resourceAndMetric] = {}
             logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
          for value in vals:
              if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] == True):
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round(float(value), 6)
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
              else:
                  currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round((currentMetricValue + float(value)) / 2, 6)
          #print(str(logStats[logFileName]))
       else:
           profileMetric = "TriggerIducTime" 
           pattern = re.compile('.*Trigger time for \'(.*)\'\: (.*)s$')
           vals = re.findall(pattern, line)
           if(len(vals) > 0):
              # we got a match
              for value in vals:
                  application = value[0] 
                  execTime = round(float(value[1]), 6)
                  resourceAndMetric = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + application.replace(":", "-") + ":" + profileMetric.replace(":", "-")
                  if(logStats[logFileName]["metrics"].get(resourceAndMetric) is None):
                     # first time we're seeing this resource, so lets initialize the dictionary for this objectserver/application
                     logStats[logFileName]["metrics"][resourceAndMetric] = {}
                     logStats[logFileName]["metrics"][resourceAndMetric]["value"] = 0
                     logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
                  if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] == True):
                      logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round(float(value[1]), 6)
                      logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
                  else:
                      currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                      logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round((currentMetricValue + execTime ) / 2, 6)
                  logging.debug(str(logStats[logFileName]))
   elif logfiletype == "profilestats":
       logFileName = myLog.split('/')[-1]
       profileMetrics = [ "TotalIducTime" ]
       pattern = re.compile('.*Total time in the .*\: (.*)s$')
       vals = re.findall(pattern, line)
       if(len(vals) > 0):
          resourceAndMetric = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + ":TotalIducTime"
          if(logStats[logFileName]["metrics"].get(resourceAndMetric) is None):
             logStats[logFileName]["metrics"][resourceAndMetric] = {}
             logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
          for value in vals:
              if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] == True):
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round(float(value), 6)
                  logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
              else:
                  currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                  logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round((currentMetricValue + float(value)) / 2, 6)
          #print(str(logStats[logFileName]))
       else:
           profileMetric = "AppIducTime" 
           pattern = re.compile('.*Execution time for all connections whose application name is \'(.*)\'\: (.*)s$')
           vals = re.findall(pattern, line)
           if(len(vals) > 0):
              # we got a match
              for value in vals:
                  application = value[0] 
                  execTime = round(float(value[1]), 6)
                  resourceAndMetric = logStats[logFileName]["resourceNode"].replace(":", "-") + ":" + application.replace(":", "-") + ":" + profileMetric.replace(":", "-")
                  if(logStats[logFileName]["metrics"].get(resourceAndMetric) is None):
                     # first time we're seeing this resource, so lets initialize the dictionary for this objectserver/application
                     logStats[logFileName]["metrics"][resourceAndMetric] = {}
                     logStats[logFileName]["metrics"][resourceAndMetric]["value"] = 0
                     logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = True
                  if(logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] == True):
                      logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round(float(value[1]), 6)
                      logStats[logFileName]["metrics"][resourceAndMetric]["resetCounter"] = False
                  else:
                      currentMetricValue = logStats[logFileName]["metrics"][resourceAndMetric]["value"]
                      logStats[logFileName]["metrics"][resourceAndMetric]["value"] = round((currentMetricValue + execTime ) / 2, 6)
                  logging.debug(str(logStats[logFileName]))
              logging.debug(str(logStats[logFileName]))

   else:
       logging.info("No processor for log file type " + logfiletype)

def logReader(filepath, logfiletype):
    '''generator function that yields new lines in a file
    '''
    thefile = open(filepath, 'r')
    # seek the end of the file
    thefile.seek(0, os.SEEK_END)
    logFileName =  filepath.split('/')[-1]
    
    # start infinite loop
    logging.debug("Starting read loop for " + filepath)
    while(shutdownRequest == False):
        if(logStats[logFileName]["rolled"] == True):
            logging.debug("log file rolled, closing old and reopening")
            thefile.close()
            logStats[logFileName]["inode"] = os.stat(logStats[logFileName]["logFileFullPath"]).st_ino
            thefile = open(filepath, 'r')
            thefile.seek(0, os.SEEK_END)
            logStats[logFileName]["rolled"] = False
        # read last line of file
        line = thefile.readline()
        # sleep if file hasn't been updated
        if not line:
            time.sleep(1)
            continue
        else:
           processLine(filepath, logfiletype, line)


#if __name__ == '__main__':

# BEGINS HERE

global debug
logStats = {}

debug = True
# Set up signal handlers for interrupt signal (e.g. CTRL-C) and HUP signal

signal.signal(signal.SIGINT, shutdownHandler)
signal.signal(signal.SIGHUP, reconfigHandler)


global myFiles
global resetCounter

resetCounter = True

# Get configuration options

readerBinDir = os.path.dirname(os.path.abspath(__file__))
extr = re.search("(.*)bin", readerBinDir)
if extr:
   readerHome = extr.group(1)
   #print "Mediator home is: " + readerHome
else:
   logging.info("FATAL: unable to find mediator home directory. Is it installed properly? bindir = " + readerBinDir)
   exit()

if(os.path.isdir(readerHome + "log")):
   logHome = extr.group(1)
else:
   print("FATAL: unable to find log directory at " + readerHome + "log")
   exit()

if(os.path.isfile(readerHome  + "/conf/ncoStatsReader.conf")):
   props = loadProperties(readerHome + "/conf/ncoStatsReader.conf")
else:
   print("FATAL: Properties file " + mediatorHome + "/conf/ncoStatsReader.conf is missing.")
   exit()

globals().update(props)

if 'ncoStatsWriterUrl' not in globals():
   logging.info("FATAL: ncoStatsWriterUrl is not configured")
   exit()
if 'ncoStatsWriterUrl' not in globals():
   logging.info("FATAL: ncoStatsWriterUrl is not configured")
   exit()
if 'ncoStatsWriterUsername' not in globals():
   logging.info("FATAL: ncoStatsWriterUsername is not configured")
   exit()
if 'ncoStatsWriterPassword' not in globals():
   logging.info("FATAL: ncoStatsWriterUsername is not configured")
   exit()
if 'loggingLevel' in globals():
   if loggingLevel in [ "INFO", "DEBUG" ]:
      print("Configuring logging at level " + loggingLevel)
      setupLogging(loggingLevel)
   else:
      print("Logging level not defined in ncoStatsReader.conf. Defaulting to INFO")
      loggingLevel = "INFO"
      setupLogging(loggingLevel)

myFiles = getLogFileConfig()

# Next, spawn threads to tail these files, collect metrics, and collect a running average
shutdownRequest = False
logFileThread = {}
threadCount = 0
for file in myFiles:
   if os.path.exists(file):
      logging.info("initializing log file structure: " + file)
      initMetricDict(file, myFiles[file] )
      logFileThread[file] = threading.Thread(target=logReader, args=(file, myFiles[file]))
      logFileThread[file].daemon = True 
      logFileThread[file].start() 
      threadCount += 1
   else:
      logging.info("configured log file " + file + " does not exist. Ignoring this log file entry.")

if threadCount == 0:
   print("No valid log files find, exiting")
   exit()
# Finally, spawn a thread to write out data to csv, kafka, or watson API every 5 minutes

publisherThread = threading.Thread(target=publisher)
publisherThread.daemon = True
publisherThread.start()
   

while threading.active_count() > 0:

   # main processing loop, wakes up every 30 seconds to verify that the log file hasn't rolled over

   for logEntry in logStats:
      currInode = os.stat(logStats[logEntry]["logFileFullPath"]).st_ino
      if logStats[logEntry]["inode"] != currInode:
         logStats[logEntry]["rolled"] = True
         logging.debug("#################################################")
         logging.info("#              log file rolled                  #")
         logging.debug("# logStats has " + str(logStats[logEntry]["inode"]) + " disk inode is: " + str(currInode) + " #")
         logging.debug("#################################################")

   time.sleep(30)



