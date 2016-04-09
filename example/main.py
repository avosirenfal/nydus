import codecs
import hashlib
import os, sys
import re
import flask
import time
from jinja2 import FileSystemLoader
from jinja2 import Environment
import pickle
import requests
import unicodedata
from twisted.internet.endpoints import SSL4ServerEndpoint
from OpenSSL import SSL
from twisted.internet.ssl import DefaultOpenSSLContextFactory
from nydus.resource import WebSocketResource
from nydus.transaction import Transaction, WSProtocol, TransactionManager
from twisted.web.static import File
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from twisted.python import log
from twisted.web.resource import Resource
import msgpack as json
from protocol import ShoutboxWSProtocol
from util import SimpleSerializable, Serializer

class ShoutboxTransaction(Transaction):
	def initialize(self):
		self.env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
		self.buffer = []
		self.messageid = 0

	def isMod(self, user):
		# 6 is moderator usergroup
		return user != None and (user.mid == 1 or 6 in user.usergroups)

	def getByID(self, id):
		for x in self.buffer:
			if(getattr(x, 'messageid', None) == id):
				return x

		return None

	def pushBuffer(self, m):
		self.messageid += 1
		m.messageid = self.messageid
		self.buffer.append(m)

		if(len(self.buffer) > 25):
			self.buffer.pop(0)

	def removeBuffer(self, m):
		self.buffer.remove(m)

	def sendMessage(self, msg, skip=None, raw=None):
		for proto, connection in self.connections.iteritems():
			if(proto.user == None and proto.guest == False):
				continue

			if(skip != None and proto in skip):
				continue

			proto.write(connection, msg, raw=raw)

if(__name__ == '__main__'):
	log.startLogging(sys.stdout)

	chatstate = ShoutboxTransaction(ShoutboxWSProtocol)
	# static transaction, use TransactionManager instead
	# tm = TransactionManager(chatstate)
	# resource = WebSocketResource('wss://somesite.com/shoutboxws', tm)
	resource = WebSocketResource('wss://somesite.com/shoutboxws', lambda x: chatstate)

	root = Resource()
	root.putChild("shoutboxws", resource)

	site = Site(root)

	reactor.listenTCP(12500, site, interface='0.0.0.0')
	#reactor.listenSSL(12500, site, DefaultOpenSSLContextFactory('/home/shoutbox/keys/privkey1.pem', '/home/shoutbox/keys/fullchain1.pem', SSL.TLSv1_2_METHOD))
	reactor.run()
