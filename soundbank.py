from struct import *
import os
import glob
import sys


class Soundbank(object):

    file = None
    new_files = []
    pre_audio = 0
    after_audio = 0
    seek_audio = 0
    audio_data = []
    audio_len = 0
    wem_items = []
    output = 'changed.bnk'
    DIDX_PrePos = 0
    DIDXChunkLenPos = 0

    def __init__(self, file):
        if not os.path.isfile(sys.argv[1]):
            print("That is not a valid file")
            return False
        self.file = file

        arg_num = 2
        for item in sys.argv[arg_num:]:
            if os.path.isfile(item):
                if '.wem' in item:
                    item = item.replace('\\', '/')
                    self.new_files.append({
                        'file': item.split('/')[-1],
                        'path': item,
                        'found': None,
                        'patch': None,
                    })
            elif os.path.isdir(item):
                item = item.replace('\\', '/')
                if item[-1] != '/':
                    item += '/'
                for file in glob.glob(item + '*.wem'):
                    file = file.replace('\\', '/')
                    if '.wem' in file:
                        self.new_files.append({
                            'file': file.split('/')[-1],
                            'path': file,
                            'found': None,
                            'patch': None,
                        })
            elif '-o' in item or item == '-o':
                self.output = sys.argv[arg_num + 1]
                # if self.output.lower() == self.file.replace('/', '').lower():
                #     raise 'Can\'t set output soundbank to source soundbank.'

            arg_num += 1

        print('Output file set to', self.output)

        self.parse()

    def parse(self):

        print("Opening file... This may take a while depending on the size.")

        file = open(self.file, "r+b")

        # Header Info
        arrHeader = []
        arrHeader.append(unpack("<I", file.read(4))[0])  # magicNumber
        arrHeader.append(unpack("<I", file.read(4))[0])  # headerLength
        arrHeader.append(unpack("<I", file.read(4))[0])  # version
        arrHeader.append(unpack("<I", file.read(4))[0])  # soundbankid

        # some hack from old source of sbk-reader
        currentPos = 8
        while (currentPos < arrHeader[1]):
            arrHeader.append(unpack("<I", file.read(4))[0])  # Unknown
            currentPos = currentPos + 4

        self.DIDX_PrePos = file.tell()

        # DIDX Header
        arrDIDX = []
        arrDIDX.append(unpack("<I", file.read(4))[0])  # magicNumber
        self.DIDXChunkLenPos = file.tell()
        arrDIDX.append(unpack("<I", file.read(4))[0])  # chunkLength

        audio_length = 0
        if arrDIDX[1] > 0:
            self.audio_len = int(arrDIDX[1] / 12)
            for i in range(0, self.audio_len):
                self.wem_items.append([])

                fileID = [file.tell(), unpack("<I", file.read(4))[0]]
                offsetData = [file.tell(), unpack("<I", file.read(4))[0]]
                fileLength = [file.tell(), unpack("<I", file.read(4))[0]]

                audio_length += fileLength[1]

                for z in range(0, len(self.new_files)):
                    if str(fileID[1]) + '.wem' == self.new_files[z]['file']:
                        self.new_files[z]['found'] = i

                self.wem_items[i].append(fileID)  # fileID
                self.wem_items[i].append(offsetData)  # offsetData
                self.wem_items[i].append(fileLength)  # fileLength

        arrDATA = []
        arrDATA.append(unpack("<I", file.read(4))[0])  # magicNumber
        # dataChunkLenPos = file.tell()
        arrDATA.append(unpack("<I", file.read(4))[0])  # chunkLength

        self.seek_audio = file.tell()

        print('Sound items: ', self.audio_len)

        for i in range(0, self.audio_len):
            file.seek(self.seek_audio + self.wem_items[i][1][1])
            self.audio_data.append({
                'name': str(self.wem_items[i][0][1]),
                'content': file.read(self.wem_items[i][2][1]),
            })

        self.pre_audio = self.wem_items[0][1][1]
        self.after_audio = audio_length

        file.close()

    def extract(self, files=[]):
        for i in range(0, len(self.audio_data)):
            sound_name = str(self.audio_data[i]['name']) + '.wem'
            if files and sound_name not in files:
                continue
            print('Extracting', sound_name)
            f = open(sound_name, 'w+b')
            f.write(self.audio_data[i]['content'])
            f.close()

    def update(self, to_update=[]):
        if not self.new_files:
            print('New files are not selected. Ignoring replace command.')

        if not self.new_files[0]['patch']:
            self.load_replacements()

        with open(self.file, 'r+b') as file:

            with open(self.output, 'w+b') as outfile:

                DATA = b''
                DATA += pack('I', 0x41544144)
                AUDIO = b''
                items = []
                offset = 0
                for i in range(0, self.audio_len):
                    file.seek(self.seek_audio + self.wem_items[i][1][1])

                    audio = None
                    for z in range(0, len(self.new_files)):
                        if len(to_update) and self.new_files[z]['file'] not in to_update:
                            continue
                        if i == self.new_files[z]['found']:
                            audio = self.new_files[z]['patch']
                            file.seek(self.seek_audio + self.wem_items[i][1][1] + self.wem_items[i][2][1])
                    if not audio:
                        audio = file.read(self.wem_items[i][2][1])

                    items.append({
                        'len': len(audio),
                        'offset': offset
                    })

                    if i + 1 < self.audio_len:
                        size = len(audio)
                        while size % 16 != 0:
                            audio += b'\x00'
                            size = len(audio)
                    offset += len(audio)
                    AUDIO += audio
                DATA += pack('I', len(AUDIO))
                DATA += AUDIO

                FOOTER = file.read()

                DIDX = b''
                DIDX += pack('I', 0x58444944)
                DIDX_items = b''
                for i in range(0, self.audio_len):
                    DIDX_items += pack('I', self.wem_items[i][0][1])
                    DIDX_items += pack('I', items[i]['offset'])
                    DIDX_items += pack('I', items[i]['len'])
                DIDX += pack('I', len(DIDX_items))
                DIDX += DIDX_items

                HEADER = b''
                file.seek(0)
                HEADER += file.read(self.DIDX_PrePos)
                outfile.write(HEADER + DIDX + DATA + FOOTER)

    def load_replacements(self):
        for item in self.new_files:
            with open(item['path'], 'rb') as f:
                item['patch'] = f.read()

    def list(self):
        for i in range(0, item.audio_len):
            print(str(item.audio_data[i]['name']) + '.wem')


item = Soundbank(sys.argv[1])

if len(sys.argv) > 1:
    while True:
        command = input("Use command to continue:\r\n\
            'extract' to extract files from bank\r\n\
                -- use 'extract file1 file2' to extract some files\r\n \
            'replace' to replace old audio with new ones\r\n\
                -- use 'replace file1 file2' to replace some files\r\n \
            'list' to list all audio from bank\r\n\
            'exit' to finish\r\n\
        ")

        if command == 'exit':
            break
        if command == 'list':
            item.list()
            continue
        if 'extract' in command:
            items = command.split(' ')[1:]
            item.extract(items)
            continue
        if 'replace' in command:
            items = command.split(' ')[1:]
            item.update(items)
            continue
        print('Undefined command. Try again.')
else:
    print("Usage: python soundbank.py \"source soundbank\" \
        [file.wem file2.wem or dir/ with wem] [-o changed.bnk]\n\
        Please, don't use source file as output. That will not work.")
