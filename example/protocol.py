import codecs
import hashlib
import time
import requests
from twisted.internet import reactor
import unicodedata
from baseprotocol import BaseShoutboxWSProtocol, ValidationException
from messages.shout import Shout
from util import User, MessageLimiter

def verifyAuth(self, msg):
	if(msg == 'fdgdsfgfd'):
		return None

	# memberid|timestamp|hash
	if(not msg.count('|') == 2):
		raise ValidationException()

	memberid, timestamp, hash = msg.split('|')

	if(
		self.user != None or
		len(hash) != 128 or
		(time.time() - int(timestamp)) > 30
	):
		raise ValidationException()

	h = hashlib.sha512()
	h.update('%s|%s' % (memberid, timestamp))
	h.update('lol secret key')
	digest = h.hexdigest().lower()

	if(digest != hash):
		raise ValidationException()

	return memberid

def verifyMsg(self, data):
	if(
		self.user == None or
		len(data) > 500 or
		not self.limiter.check()
	):
		raise ValidationException()

	return data

def verifyRemove(self, data):
	if(self.user == None or '|' in data):
		raise ValidationException()

	try:
		return int(data)
	except:
		raise ValidationException()

def verifyEdit(self, msg):
	if(self.user == None or not msg.count('|') == 1):
		raise ValidationException()

	id,msg = msg.split('|',1)

	try:
		id = int(id)
	except:
		raise ValidationException()

	if(len(msg) > 500 or not self.editlimiter.check()):
		raise ValidationException()

	return id,msg

class ShoutboxWSProtocol(BaseShoutboxWSProtocol):
	def connectionMade(self, ws):
		self.user = None
		self.guest = False
		self.limiter = None

		self.registerHandler('auth', self.authenticate, verifyAuth.__get__(self, self.__class__))
		self.registerHandler('m', self.messageReceived, verifyMsg.__get__(self, self.__class__))
		self.registerHandler('rem', self.removeMessage, verifyRemove.__get__(self, self.__class__))
		self.registerHandler('edit', self.editMessage, verifyEdit.__get__(self, self.__class__))

		self.write(ws, '', raw='PLEASE_AUTH')
		
	def messageReceived(self, data, ws):
		data = data.decode('utf8')
		data = unicodedata.normalize('NFKD', data).encode('ascii','replace')

		m = '<%s> %s' % (self.user.username, data)
		print m

		if(data.startswith('/')):
			if(data == '/clear' and self.transaction.isMod(self.user.mid)):
				self.transaction.sendMessage('')
				self.transaction.buffer = []
				return

			return

		m = Shout(self.user, data)
		self.transaction.pushBuffer(m)
		self.transaction.sendMessage(m)

	def authenticate(self, memberid, ws):
		if(memberid == None):
			self.guest = True
			for x in self.transaction.buffer:
				self.write(ws, x)

			return

		self.user = User(int(memberid))

		try:
			self.user.update()
		except Exception as e:
			print 'API call failed: %r' % (e)
			reactor.stop()

		# if this user opened two tabs make sure we use the same MessageLimiter to stop flooding
		for proto in self.transaction.connections.keys():
			if(proto != self and proto.user != None and proto.user.mid == self.user.mid):
				self.limiter = proto.limiter

		if(self.limiter == None):
			self.limiter = MessageLimiter()

		self.editlimiter = MessageLimiter(0.2)

		for x in self.transaction.buffer:
			self.write(ws, x)

	def removeMessage(self, data, ws):
		m = self.transaction.getByID(data)

		if(m):
			if(self.transaction.isMod(self.user)):
				self.transaction.removeBuffer(m)
				self.transaction.sendMessage(data, raw='rem')
			else:
				self.disconnect()

	def editMessage(self, data, ws):
		m = self.transaction.getByID(data[0])

		if(m):
			if(m.user.mid == self.user.mid or self.transaction.isMod(self.user) or not isinstance(m, Shout)):
				m.edit(data[1])

				for proto, connection in self.transaction.connections.iteritems():
					proto.write(connection, '%s|%s' % (data[0], m.render(self.transaction, proto.user)), raw='edit')
			else:
				self.disconnect()