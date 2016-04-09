from twisted.internet import reactor
from nydus.transaction import WSProtocol
from util import MessageLimiter

class ValidationException(Exception):
	pass

class BaseShoutboxWSProtocol(WSProtocol):
	def __init__(self, transaction):
		WSProtocol.__init__(self, transaction)
		self.handlers = {}

	# raw is either None or the key to be used
	def write(self, ws, msg, raw=None):
		ret = msg if not hasattr(msg, 'render') else msg.render(self.transaction, self.user)
		ws.write('%s|%s' % (raw or msg.key, ret))

	def registerHandler(self, key, func, validate=None):
		self.handlers[key] = (func, validate)

	def dataReceived(self, ws, data, isBinary):
		if(not '|' in data):
			self.disconnect()
			return

		key, msg = data.split('|', 1)

		if(not key in self.handlers):
			self.disconnect()
			return

		func, validate = self.handlers[key]

		if(validate != None):
			try:
				func(validate(msg), ws)
			except ValidationException:
				self.disconnect()
				return
		else:
			func(msg, ws)

	def connectionEnd(self):
		pass