# About

_Script used to import stuff into NetBox using YAML documents_

The **yaml-to-netbox** script parses through a YAML document representing network infrastructure and creates all the associated objects in NetBox. The intended use case is to import a full network design into NetBox versus leveraging web interface to add everything manually. The YAML document used to import all data would initially be created by a network engineer.  From the YAML document this script will import an entire network topology for one or more sites complete with racks, devices, interfaces, and cabling.

The script supports creating these object types:
- Site
- Device
- Interface
- Rack
- Circuits
- Cables

## Document structure
The YAML document structure is straight forward using dictionaries and lists. There are only two levels currently.

### First level keys
- vars
- sites
- devices
- circuits
- cables

### Second level keys
Sites
- Racks

Devices
- Interfaces

## YAML document variables
### Vars
A special first level key called "vars" is used to convey miscellaneous information/logic to the script.  Currently two variables are used:
- **schema_verison**: this just tells the script what YAML schema is used as this will be helpful as the YAML structure evolves
- **debug**: **use with extreme caution** and only set to "True" when doing testing and development on a non-production instance of NetBox as this mode will literally delete the site(s) specified in the YAML document in order to start fresh.

### Globals
Within the **vars** key there is another key used called **globals**.  This is where any global variable can be defined and utilized by the script.
- **tenant**: If no tenant name is specified the script will create all the new objects with no tenant assignment. However, if a tenant name is provided (and the tenant name must already exist in NetBox), the script will associate any created objects (Site, Rack, Device, Circuit and Cable) with that tenant.

## How it works
The script's first task is importing the YAML document into a dictionary called **result**. Once this is done **results** is further parsed out by the first level keys into individual dictionaries, one dict for each first level key.  After that each specific dict is processed following predetermined logic to ensure everything is created in the proper sequence. The order placement of the top-level YAML keys does not matter as the script logic will always attempt to process the dict keys in the proper logical order of Vars, Sites, Devices, Circuits, and Cables. This ensures the parent objects such as a site will be created in NetBox before any attempt to create a child object such as a rack.

## Limitations and rules
Always refer to the comments within the example YAML files for additional syntax requirements. Below are a few notables.
1. Many models referenced are assumed to already exist in NetBox which include:
    - CircuitType 
    - DeviceRole
    - DeviceType
    - Manufacturer
    - Provider
    - ProviderNetwork
    - RackRole
    - Tenant
2. Some keys must exist, but they should be left blank/empty depending on the situation.
3. Everything in the YAML document will attempt to be created in NetBox, thus any object in the YAML document cannot have the same name as an object already exist in NetBox or the script will fail with duplicate key errors.
4. If the script seems to be running forever, this is likely caused from a syntax or schema error in the YAML document, so double check that.


## Testing
This script and example files can be tested with the netbox-demo-data
https://github.com/netbox-community/netbox-demo-data


## Contributing
As there is no YAML document structure that has been proposed by the NetBox community (as far as I know) for importing many types of objects in one step, I decided to develop a simple one. The structure should be simple enough for any novice network engineer to easily create and/or interpret. For anyone wishing to contribute, please share ideas in ways to further improve the YAML structure or perhaps work on adding support for more models.

## Future considerations
- Support for interface/port templates and port number ranges, thus reduce YAML document size for repetitive data
- Develop an export feature (Report?) to generate the YAML representation of everything within a site, location, or rack
- Optional support for the Locations model
- Add in extra logic to update an object, if it already exist


_God Bless (Romans 8:28)_


