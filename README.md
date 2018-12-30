# opuscule
A client/server solution for audio appliances

# Introduction

This software is the server portion of a client/server solution for audio appliances. The server is fairly agnostic about UI: it models a simple audio appliance (with a text display, and various indicators), and provides that state to connected clients when something changes. Clients can make change to the appliance state by providing commands.

It is up the the clients to figure out how to display the data and generate the commands. Some example clients are available in the *test_clients* directory to offer a demonstration of this.

This is still very much software in progress: large portions of the code (preferences, settings, enhanced UI options, some components) remain undone. However; as of this writing, the software is useful enough to run comfortably on an SBC and put audio into the room. 

# TODO

- Online directory for streaming services
- Improve boodler component to be less of a hack
- Implement podcast component
- Support for sleeping/powering off/resetting an appliance


