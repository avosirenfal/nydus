from autobahn.twisted import WebSocketServerProtocol
from twisted.internet.defer import Deferred
import string
from random import choice

class WebSocketConnection(WebSocketServerProtocol):
	def __init__(self):
		WebSocketServerProtocol.__init__(self)
		self.finished = Deferred()

	def write(self, payload):
		self.sendMessage(bytes(payload), isBinary=False)

	def onConnect(self, request):
		pass
		#print("Client connecting: {0}".format(request.peer))

	def onOpen(self):
		self.inner.connectionMade(self)
		#print("WebSocket connection open.")

	def onMessage(self, payload, isBinary):
		# if isBinary:
		# 	print("Binary message received: {0} bytes".format(len(payload)))
		# else:
		# 	print("Text message received: {0}".format(payload.decode('utf8')))
		#
		# # echo back message verbatim
		# self.sendMessage(payload, isBinary)
		self.inner.dataReceived(self, payload, isBinary)

	def onClose(self, wasClean, code, reason):
		self.finished.callback((wasClean, code, reason))
		#self.inner.connectLost(wasClean, code, reason)
		#print("WebSocket connection closed: {0}".format(reason))

class WSProtocol(object):
	def __init__(self, transaction):
		# note-- this is a circular reference, which is probably acceptable since a transaction shouldn't
		# ever be disposed while it still has connections associated with it, however keep in mind this
		# means the transaction/protocols will be stuck in scope if a protocol ever leaks
		self.transaction = transaction

	def connectionMade(self, ws):
		pass

	# def onOpen(self):
	# 	self.connectionMade(request)

	def dataReceived(self, ws, data, isBinary):
		pass

	def connectionEnd(self):
		pass

	def disconnect(self):
		self.transaction.connections[self].transport.abortConnection()

class Transaction(object):
	def __init__(self, protocol, reverseProxyHeader=None):
		self.protocol = protocol
		# map of protocol: underlying ws connection
		self.connections = {}

		self.finished = Deferred()
		self.reverseProxyHeader = reverseProxyHeader

		self.initialize()

	# convenience method to avoid having to call parent __init__
	def initialize(self):
		pass

	def _proto_disconnected(self, ws, proto):
		# is ws even available for writing here? this connection is presumably already terminated
		proto.connectionEnd()
		del self.connections[proto]

	def adoptWebSocket(self, protocol):
		p = self.protocol(self)
		self.connections[p] = protocol

		protocol.inner = p
		protocol.finished.addCallback(self._proto_disconnected, p)

		#p.connectionMade(protocol)

		return protocol

	def finish(self):
		for connection in self.connections.values():
			connection.transport.loseConnection()

		self.connections = {}

		self.finished.callback(self)

class TransactionNotFoundException(Exception):
	pass

transaction_charset = string.letters+string.digits

class TransactionManager(object):
	def __init__(self):
		self.transactions = {}

	def addTransaction(self, transaction, rstr=None):
		if rstr is None:
			rstr = ''.join([choice(transaction_charset) for _ in xrange(32)])
		self.transactions[rstr] = transaction
		def finish_transaction(data):
			del self.transactions[rstr]
			return data
		transaction.finished.addCallback(finish_transaction)
		return rstr

	def hasTransaction(self, key):
		return self.transactions.has_key(key)

	def __call__(self, secretKey):
		if not self.transactions.has_key(secretKey):
			raise TransactionNotFoundException()

		return self.transactions[secretKey]
