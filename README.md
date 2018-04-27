# CLinesHadu
GUI tool used to test servers for Card Sharing and convert them into a configuration you can use with Hadu plugin (http://hadu-cccam-dvb-plugin.blogspot.it/).

##### Terminology
Card sharing is a method that allows multiple clients to access a digital TV subscription.
A C-line or CCCAM is a string that describes where to gain that access. It is basically composed of a server address, a port, a user name and a password.
Various specialized sites provide C-lines. Hadu is a plugin for DVB Dream or DVBViewer that enables the use of c-lines with those programs.
https://en.wikipedia.org/wiki/Card_sharing

## Usage
Download all files and execute `clines-hadu.py` with python. This will open a window where you can paste your clines (e.g. what you find on sites like Testious, etc.). Recognized c-lines will be processed and a server connection will be attempted for each of those. Those c-lines that lead to a successful server login and communication will later be listed, in an Hadu-plugin format.
You can copy the result and directly append it to you `hadu.ini` file.

##### Note
Reasons for c-lines server testing failure can ba various: bad server address, server down, server not responding or slamming the connection in your face. As well as bad user name or password. A server test might succeed in a certain moment and fail a minute later, or vice versa.

##### Windows
I have tried building an executable for windows users, have a look at https://github.com/brigantino2/clines-hadu/tree/master/build/clines-hadu.exe

##### Credits
Thanks to `gavazquez` for inspiration and providing the code for block encryption and decryption. https://github.com/gavazquez/CLineTester
