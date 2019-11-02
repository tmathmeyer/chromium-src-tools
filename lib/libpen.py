
import struct

BIG_ENDIAN = object()
LITTLE_ENDING = object()
SIGNED = object()
UNSIGNED = object()


class ByteBuffer(object):
  def __init__(self, ByteString):
    self._bytes = ByteString
    self._index = 0
    self._size = len(ByteString)

  def Take(self, count):
    ending = self._index + count
    if ending > self._size:
      raise ValueError(f'Read out of range {ending} >= {ending}')
    start = self._index
    self._index = ending
    return self._bytes[start:ending]

  def Left(size):
    return self._size - self._index

  @classmethod
  def GetFormat(self, byteCount, signed, endian):
    def _Letter():
      if signed == SIGNED:
        return {1:'b', 2:'h', 4:'i', 8:'q'}[byteCount]
      if signed == UNSIGNED:
        return {1:'B', 2:'H', 4:'I', 8:'Q'}[byteCount]
      return 'X'
    return f'{">" if endian is BIG_ENDIAN else "<"}{_Letter()}'

  def ReadInteger(self, byteCount, signed=SIGNED, endian=LITTLE_ENDING):
    return struct.unpack(
      self.GetFormat(byteCount, signed, endian),
      self.Take(byteCount))[0]


class PenEncoded(object):
  def __init__(self, ip='0.0.0.0', port=0, gaiaid=0, protocol=0):
    self.ip = ip
    self.port = port
    self.gaiaid = gaiaid
    self.protocol = protocol

  def __str__(self):
    return str(self.__dict__)

  def __repr__(self):
    return str(self)

  def WithIP(self, ip):
    return PenEncoded(ip, self.port, self.gaiaid, self.protocol)

  def WithPort(self, port):
    return PenEncoded(self.ip, port, self.gaiaid, self.protocol)

  def WithGaiaId(self, gaiaid):
    return PenEncoded(self.ip, self.port, gaiaid, self.protocol)

  def WithProtocol(self, protocol):
    return PenEncoded(self.ip, self.port, self.gaiaid, protocol)

  def EncodeIP(self):
    v4str = self.ip.split('.')
    if len(v4str):
      ipbytes = b''
      for num in v4str:
        ipbytes += struct.pack(
          ByteBuffer.GetFormat(1, UNSIGNED, LITTLE_ENDING), int(num))
      return 'a', ipbytes
    else:
      return 'b', b'0000000000000000'

  def Encode(self):
    isv4, ipbytes = self.EncodeIP()
    portbytes = struct.pack(
      ByteBuffer.GetFormat(2, UNSIGNED, BIG_ENDIAN), self.port)
    gaiabytes = struct.pack(
      ByteBuffer.GetFormat(8, UNSIGNED, BIG_ENDIAN), self.gaiaid)
    protobytes = struct.pack(
      ByteBuffer.GetFormat(1, UNSIGNED, BIG_ENDIAN), self.protocol)
    exportbytes = ipbytes+portbytes+gaiabytes+protobytes
    return isv4 + exportbytes.hex()


  @classmethod
  def FromEncoded(cls, encoded):
    # ipv4 or ipv6?
    IPByteLength = (4 if encoded[0] == 'a' else 16)
    buf = ByteBuffer(bytearray.fromhex(encoded[1:]))
    ipstring = '.'.join(str(i) for i in buf.Take(IPByteLength))
    port = buf.ReadInteger(2, UNSIGNED, BIG_ENDIAN)
    gaiaid = buf.ReadInteger(8, UNSIGNED, BIG_ENDIAN)
    protocol = buf.ReadInteger(1, UNSIGNED, BIG_ENDIAN)
    return PenEncoded(ipstring, port, gaiaid, protocol)
