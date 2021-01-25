CODES = """
  kOk = 0,

  // Decoder Errors: 0x01
  kDecoderInitializeNeverCompleted = 0x00000101,
  kDecoderFailedDecode = 0x00000102,
  kDecoderUnsupportedProfile = 0x00000103,
  kDecoderUnsupportedCodec = 0x00000104,
  kDecoderUnsupportedConfig = 0x00000105,
  kEncryptedContentUnsupported = 0x00000106,
  kClearContentUnsupported = 0x00000107,
  kDecoderMissingCdmForEncryptedContent = 0x00000108,
  kDecoderFailedInitialization = 0x00000109,
  kDecoderCantChangeCodec = 0x0000010A,
  kDecoderFailedCreation = 0x0000010B,
  kInitializationUnspecifiedFailure = 0x0000010C,

  // Windows Errors: 0x02
  kWindowsWrappedHresult = 0x00000201,
  kWindowsApiNotAvailible = 0x00000202,
  kWindowsD3D11Error = 0x00000203,

  // D3D11VideoDecoder Errors: 0x03
  kCantMakeContextCurrent = 0x00000301,
  kCantPostTexture = 0x00000302,
  kCantPostAcquireStream = 0x00000303,
  kCantCreateEglStream = 0x00000304,
  kCantCreateEglStreamConsumer = 0x00000305,
  kCantCreateEglStreamProducer = 0x00000306,
  kCannotCreateTextureSelector = 0x00000307,
  kCannotQueryID3D11Multithread = 0x00000308,
  kCannotGetDecoderConfigCount = 0x00000309,
  kCannotGetDecoderConfig = 0x0000030A,

  // MojoDecoder Errors: 0x04
  kMojoDecoderNoWrappedDecoder = 0x00000401,
  kMojoDecoderStoppedBeforeInitDone = 0x00000402,
  kMojoDecoderUnsupported = 0x00000403,
  kMojoDecoderNoConnection = 0x00000404,
  kMojoDecoderDeletedWithoutInitialization = 0x00000405,

  // Chromeos Errors: 0x05
  kChromeOSVideoDecoderNoDecoders = 0x00000501,
  kV4l2NoDevice = 0x00000502,
  kV4l2FailedToStopStreamQueue = 0x00000503,
  kV4l2NoDecoder = 0x00000504,
  kV4l2FailedFileCapabilitiesCheck = 0x00000505,
  kV4l2FailedResourceAllocation = 0x00000506,
  kV4l2BadFormat = 0x00000507,
  kV4L2FailedToStartStreamQueue = 0x00000508,
  kVaapiReinitializedDuringDecode = 0x00000509,
  kVaapiFailedAcceleratorCreation = 0x00000510,

  // Encoder Error: 0x06
  kEncoderInitializeNeverCompleted = 0x00000601,
  kEncoderInitializeTwice = 0x00000602,
  kEncoderFailedEncode = 0x00000603,
  kEncoderUnsupportedProfile = 0x00000604,
  kEncoderUnsupportedCodec = 0x00000605,
  kEncoderUnsupportedConfig = 0x00000606,
  kEncoderInitializationError = 0x00000607,

  // Special codes
  kGenericErrorPleaseRemove = 0x79999999,
  kCodeOnlyForTesting = std::numeric_limits<StatusCodeType>::max(),
  kMaxValue = kCodeOnlyForTesting,
"""

def parse_line(line):
  name, value = line.split('=')
  name = name.strip()[1:]  # drop k
  value = value.strip()[:-1]  # drop comma
  try:
    value = int(value, 16)
    code = value & 255
    group = (value >> 8) & 255
    return (name, group, code)
  except:
    return (name, 0, 0)


def parse_codes(codes):
  for line in codes.split('\n'):
    line = line.strip()
    if line and not line.startswith('//'):
      yield parse_line(line)


def generate_xml(codes):
  groups = {}
  for (name, group, code) in parse_codes(codes):
    if group:
      if group not in groups:
        groups[group] = []
      groups[group].append((name, code))

  for group, values in groups.items():
    yield f'<group name="FILLTHISIN" code="{group}">'
    for value in values:
      yield f'  <code name="{value[0]}"> {value[1]} </code>'
    yield '</group>\n'


def generate_defn(codes):
  groups = {}
  grouplengths = {}
  for (name, group, code) in parse_codes(codes):
    if group:
      if group not in groups:
        groups[group] = []
        grouplengths[group] = 0
      grouplengths[group] = max(grouplengths[group], len(name))
      groups[group].append((name, code))

  yield 'groups:'
  for group, values in groups.items():
    yield f'  FILLTHISIN = {group}:'
    for value in values:
      spaces = (grouplengths[group] - len(value[0])) * ' '
      yield f'    {value[0]}{spaces} = {value[1]}'
    yield ''



def main(args):
  codes = {
    'xml': generate_xml,
    'def': generate_defn
  }[args[0]](CODES)
  with open(args[1], 'w') as f:
    f.write('\n'.join(codes))


if __name__ == '__main__':
  import sys
  main(sys.argv[1:])