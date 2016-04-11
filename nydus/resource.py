from autobahn.twisted import WebSocketServerFactory
from six import PY3
from twisted.web.resource import NoResource, IResource
from twisted.web.server import NOT_DONE_YET
from zope.interface import implementer
from nydus.transaction import WebSocketConnection

@implementer(IResource)
class WebSocketResource(object):
	"""
	A Twisted Web resource for WebSocket.
	"""
	isLeaf = True

	def __init__(self, url, lookup, keyword=None):
		"""

		:param factory: An instance of :class:`autobahn.twisted.websocket.WebSocketServerFactory`.
		:type factory: obj
		:param lookup: a function that accepts the keyword query parameter and returns a Transaction, or throws an exception if one wasn't found
		:type lookup: func
		:param keyword: the query parameter used to locate transactions
		:type keyword: string or None
		"""
		self._factory = WebSocketServerFactory(url)
		
		# disable autobahn http response for when someone hits websocket URI with no upgrade header
		# we just want to reject them with HTTP STATUS 426 (Need Upgrade)
		self._factory.setProtocolOptions(webStatus=False)
		
		self._factory.protocol = WebSocketConnection
		self.lookup = lookup
		self.keyword = keyword

	# noinspection PyUnusedLocal
	def getChildWithDefault(self, name, request):
		"""
		This resource cannot have children, hence this will always fail.
		"""
		return NoResource("No such child resource.")

	def putChild(self, path, child):
		"""
		This resource cannot have children, hence this is always ignored.
		"""

	def render(self, request):
		"""
		Render the resource. This will takeover the transport underlying
		the request, create a :class:`autobahn.twisted.websocket.WebSocketServerProtocol`
		and let that do any subsequent communication.
		"""
		# Create Autobahn WebSocket protocol.
		#
		protocol = self._factory.buildProtocol(request.transport.getPeer())

		if(not protocol):
			# If protocol creation fails, we signal "internal server error"
			request.setResponseCode(500)
			return b""

		# locate the transaction
		try:
			transaction = self.lookup(request.args[self.keyword][0] if (self.keyword is not None and request.args.has_key(self.keyword)) else None)
		except:
			# failed to locate
			request.setResponseCode(400)
			return b""

		# Take over the transport from Twisted Web
		#
		transport, request.transport = request.transport, None

		transport.protocol = protocol
		protocol.makeConnection(transport)

		if(PY3):
			data = request.method + b' ' + request.uri + b' HTTP/1.1\x0d\x0a'

			for h in request.requestHeaders.getAllRawHeaders():
				data += h[0] + b': ' + b",".join(h[1]) + b'\x0d\x0a'

			data += b"\x0d\x0a"
			data += request.content.read()
		else:
			data = "%s %s HTTP/1.1\x0d\x0a" % (request.method, request.uri)

			for h in request.requestHeaders.getAllRawHeaders():
				data += "%s: %s\x0d\x0a" % (h[0], ",".join(h[1]))

			data += "\x0d\x0a"

		transaction.adoptWebSocket(protocol)

		protocol.dataReceived(data)

		return NOT_DONE_YET
