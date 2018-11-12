#!/usr/bin/python

from zabbix_api import ZabbixAPI
import json
import yaml
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart 

# Certain things have been modified from the actual script to project business information

# Every server should be in at least 2 main hostgroups:
#	Main servers: Main_Linux_Servers + (either Prod_Linux_Servers or DEV/QA_Linux_Servers)
#	Alt Servers: Alt Linux servers + (either Alt Linux DEV/QA or Alt Linux PROD)

# login
zapi = ZabbixAPI('insert-url-here')
zapi.login('username','password')

ADD = 'No'

class ZabHost:
	def __init__(self, host):
		self.name = host			# DNS name
		self.id = ''
		self.env = ''
		self.currentGrp = []
		self.newGrp = []
		self.host = host			# host given by API
		self.count = 0
		self.updMsg = ''			# update msg for email

	def splitHost(self):			# some hosts that are returned have 2 names in the zappix name JSON
		if '/' in self.name:
			host1, host2 = host.split('/')
			self.name = (host1, host2)
		else:
			self.name = (host, 'N/A')

	def getEnv(self):			# gets the env of the server (production, QA, or Dev)
		with open('puppet file containing env information') as pupYaml:
			pupDB = yaml.load(pupYaml)
			env = ''
			for x in pupDB:
				if self.name[0] in x or self.name[1] in x:
					self.env = pupDB[x]["puppet_environment"]
				elif self.env == '':
					self.guessEnv()

	def guessEnv(self):			# if the information is not in the yaml file guess the env if the host has prod, dev, or QA in the name
		if 'prod' in self.name[0] or 'prod' in self.name[1]:
			self.env = 'production'
		elif 'dev' in self.name[0] or 'dev' in self.name[1]:
			self.env = 'dev'
		elif 'qa' in self.name[0] or 'qa' in self.name[1]:
			self.env = 'qa'
		else:
			self.env = 'Env Not Defined'

	def getHostID(self):		# get the host ID given by Zabbix
		secondHostName = ''
		if self.name[1] != 'N/A':
			self.count += 1
			secondHostName = self.name[1]


		temp = zapi.host.get({"output":"extend", "filter":{"host":self.name[0]} })		# pulls JSON containing group ID
		count = 0
		newHostName = ''
		checkReturn = checkIfEmpty(temp)			# check if JSON is empty

		if checkReturn == False:
			newHostName = self.name[0]				# if JSON is not empty place the first hostname in var newHostName

		while checkReturn == True:					# while JSON is empty try hostname with different extensions
			if count == 0:
				newHostName = changeExtension(self.name[0])
				temp = zapi.host.get({"output":"extend", "filter":{"host":newHostName} })
				checkReturn = checkIfEmpty(temp)
				count += 1
			elif count > 0:
				newHostName = changeExtension(newHostName)
				temp = zapi.host.get({"output":"extend", "filter":{"host":newHostName} })
				checkReturn = checkIfEmpty(temp)
				count += 1
				if count == 3:
					checkReturn = False

		if temp == '':			# if temp is empty reset newHostname to first hostname
			newHostName = self.name[0]

		if temp == []:			# if JSON is empty make self.id not available and first hostname = newHostname
			self.id = 'Not Available'
			self.name = newHostName			# tuple object does not support item assignment
		else:			# if JSON not empty set self.id and first hostname = newHostname
			self.id = temp[0]['hostid']
			self.name = newHostName			# tuple object does not support item assignment

		if self.id == 'Not Available' and self.count == 1:			# if id not available AND there is a second hostname
			self.name = secondHostName
			self.getHostID()

	def getGroups(self):			# get a list of the groups the host is currently a member of
		num = 0
		temp = zapi.host.get({"output": ["hostid"], "selectGroups": "extend", "filter": {"host": self.host}})

		if temp != []:
			groups = temp[0]['groups']
			for x in groups:
				num += 1
			for i in range(0, num):
				self.currentGrp.append(groups[i]['groupid'])

	def updateGroup(self, newGrp):		# update Zabbix with the new hostgroup its being added to
		num = 0
		for x in self.currentGrp:
			num += 1
		if num == 0:
			zapi.host.update({"hostid": self.id, "groups": [{"groupid": newGrp[0]}]})
			self.updMsg = "Added " + str(self.name) + " to groups: " + str(newGrp[1])
		elif num == 1:
			zapi.host.update({"hostid": self.id, "groups": [{"groupid": newGrp[0]}, {"groupid": self.currentGrp[0]}]})
			self.updMsg = "Added " + str(self.name) + " to groups: " + str(newGrp[1])
		elif num == 2:
			zapi.host.update({"hostid": self.id, "groups": [{"groupid": newGrp[0]}, {"groupid": self.currentGrp[0]}, {"groupid": self.currentGrp[1]}]})
			self.updMsg = "Added " + str(self.name) + " to groups: " + str(newGrp[1])
		elif num == 3:
			zapi.host.update({"hostid": self.id, "groups": [{"groupid": newGrp[0]}, {"groupid": self.currentGrp[0]}, {"groupid": self.currentGrp[1]}, {"groupid": self.currentGrp[2]}]})
			self.updMsg = "Added " + str(self.name) + " to groups: " + str(newGrp[1])
		elif num == 4:
			zapi.host.update({"hostid": self.id, "groups": [{"groupid": newGrp[0]}, {"groupid": self.currentGrp[0]}, {"groupid": self.currentGrp[1]}, {"groupid": self.currentGrp[2]}, {"groupid": self.currentGrp[3]}]})
			self.updMsg = "Added " + str(self.name) + " to groups: " + str(newGrp[1])
		else:
			self.updMsg = "Add groups to " + str(self.name) + " manually"


def checkToAdd(hostID):			# option for adding the new groups or if a report showing which changes wouldve been made is used
	if ADD == 'Yes' and hostID != 'Not Available':
		return True
	else:
		return False

def checkIfEmpty(temp):
	if temp == []:
		return True
	else:
		return False

def changeExtension(hostname):
	if '.' not in hostname:
		hostname = hostname + '.host.com'
	elif '.host.com' in hostname and 'example1' not in hostname:
		hostname = hostname[:-12]
		hostname = hostname + '.example1.sherwin.com'
	elif 'example1' in hostname:
		hostname = hostname[:-21]
		hostname = hostname + '.devhost.com'
	return hostname

def runProcess(host, newProd_Grp, newQD_Grp):
	t = ZabHost(host)
	t.splitHost()
	t.getEnv()
	t.getHostID()
	t.getGroups()

	check = checkToAdd(t.id)
	if check == True:
		if t.env == "production":
			t.updateGroup(newProd_Grp)
		elif t.env == "qa" or t.env == "dev":
			t.updateGroup(newQD_Grp)
		else:
			noChange =  "No changes made, env not available"
			t.updMsg = noChange
	elif check == False:
		if t.env == "production":
			noChange = "Would have added " + str(t.name) + " to group: " + str(newProd_Grp[1])
			t.updMsg = noChange
		elif t.env == "qa" or t.env == "dev":
			noChange = "Would have added " + str(t.name) + " to group: " + str(newQD_Grp[1])
			t.updMsg = noChange
		else:
			noChange = "No changes would have been made, env not available"
			t.updMsg = noChange
	return t

def runProcess2(host, newGrp):
	t = ZabHost(host)
	t.splitHost()
	t.getEnv()
	t.getHostID()
	t.getGroups()

	check = checkToAdd(t.id)
	if check == True:
		t.updateGroup(newGrp)
	elif check == False:
		noChange = "Would have added " + str(t.name) + " to group: " + str(newGrp[1])
		t.updMsg = noChange
	return t

def compileMessage(zabObj):
	msg = "-------------------------------------------------------------------------------" + '\n'
	msg += zabObj.name + ' env: ' + zabObj.env + ' id: ' + str(zabObj.id) + '\n' + 'Current Groups:' + ' '

	if zabObj.currentGrp == []:
		msg += 'None' + '\n'
	else:
		for grp in zabObj.currentGrp:
			msg += str(grp) + ' ' + '\n'

	msg += zabObj.updMsg
	return msg

def concatenateMsg(msgList):
	newMsg = ''

	for x in msgList:
		newMsg += x + '\n'
	return newMsg

def sendEmail(newMsg):		# sends email to team to inform of changes made or changes that should be made
	smtpObj = smtplib.SMTP('smtp.host.com')
	msg = MIMEMultipart('related')
	rcpt = 'recipient@host.com'
	msg['subject'] = 'Servers not in correct Zabbix Groups'
	msg['From'] = 'sender@host.com'
	msg['To'] = rcpt
	body = newMsg
	msg.attach(MIMEText(body, 'plain'))
	smtpObj.sendmail(msg['From'], msg['To'], msg.as_string())
	smtpObj.quit()
	print "Email Sent"

# Host Group ID
Main_Linux_Servers = (1, 'Main_Linux_Servers')
Prod_Linux_Servers = (2, 'Prod_Linux_Servers')
DevQA_Linux_Servers = (3, 'DevQA_Linux_Servers')
Alt_Servers = (4, 'Alt_Servers')
Alt_DevQA = (5, 'Alt_DevQA')
Alt_Prod = (6, 'Alt_Prod')

Linux = []
corpProd = []
corpQD = [] 

altServers = []
altProd = []
altQD = []

separator = '-------------------------------------------------------------------------------'
space = '\n\n'

for host in zapi.host.get({"output":"extend","groupids": Main_Linux_Servers[0]}):
	linux.append(host['name'])

for host in zapi.host.get({"output":"extend","groupids": Prod_Linux_Servers[0]}):
	corpProd.append(host['name'])

for host in zapi.host.get({"output":"extend","groupids": DevQA_Linux_Servers[0]}):
	corpQD.append(host['name'])

for host in zapi.host.get({"output":"extend","groupids": Prod_Servers[0]}):
	altServers.append(host['name'])

for host in zapi.host.get({"output":"extend","groupids": Alt_Prod[0]}):
	altProd.append(host['name'])

for host in zapi.host.get({"output":"extend","groupids": Alt_DevQA[0]}):
	altQD.append(host['name'])

# main
msgList = []
category = 'MAIN_LINUX SERVERS NOT IN CORP_PROD OR CORP_DEV/QA:'
msgList.append(category)

for host in linux:
	if host not in corpProd and host not in corpQD:
		temp = runProcess(host, Prod_Linux_Servers, DevQA_Linux_Servers)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

msgList.append(separator)
msgList.append(space)
category = "ONLY IN CORP_PROD GROUP:"
msgList.append(category)

for host in corpProd:
	if host not in linux:
		temp = runProcess2(host, Main_Linux_Servers)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

msgList.append(separator)
msgList.append(space)
category =  "ONLY IN CORP_DEV/QA GROUP:"
msgList.append(category)

for host in corpQD:
	if host not in linux:
		temp = runProcess2(host, Main_Linux_Servers)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

msgList.append(separator)
msgList.append(space)
category = "ALT SERVERS NOT IN ALT PROD OR ALT DEV/QA:"
msgList.append(category)

for host in altServers:
	if host not in altProd and host not in altQD:
		temp = runProcess(host, Linux_Prod, Linux_DevQA)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

msgList.append(separator)
msgList.append(space)
category = "ONLY IN ALT PROD GROUP"
msgList.append(category)

for host in altProd:
	if host not in altServers:
		temp = runProcess2(host, Linux_Servers)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

msgList.append(separator)
msgList.append(space)
category =  "ONLY IN ALT DEV/QA GROUP"
msgList.append(category)

for host in altQD:
	if host not in altServers:
		temp = runProcess2(host, Linux_Servers)
		nextItem = compileMessage(temp)
		msgList.append(nextItem)

if msgList != []:
	newMsg = concatenateMsg(msgList)
	print newMsg
	sendEmail(newMsg)
else:
	print "No corrections needed"

