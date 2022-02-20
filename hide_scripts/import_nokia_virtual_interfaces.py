from django.utils.text import slugify

from dcim.models import Device, Site, Interface
from ipam.models import Prefix, IPAddress
from extras.scripts import *
import pandas as pd

'''
    This script consumes exported CSV data from Nokia NSP Network Resource>IP Addresses
    
    Example CSV format:
        Site ID,Site Name,Interface Name,IP Address,Prefix Length,IP Address Type,Object Type
        192.168.51.247,ODCX7750A,VZ-TEST,1.1.1.1,32,IPv4,VPRN  L 3   Access  Interface
        192.168.51.249,WEDO7750A,VZ-TEST,1.1.1.2,32,IPv4,VPRN  L 3   Access  Interface
        192.168.51.246,ODCX7750B,management,10.10.10.3,28,IPv4,Network  Interface
        192.168.51.247,ODCX7750A,ATT-EPS,10.11.7.130,30,IPv4,VPRN  L 3   Access  Interface
        192.168.51.249,WEDO7750A,ATT-EPS,10.11.7.134,30,IPv4,VPRN  L 3   Access  Interface
        192.168.51.162,TGMX-R-LAB,EPS-METER,10.11.9.1,29,IPv4,VPRN  L 3   Access  Interface

    This script can easily be adjusted to handle similar data from other tools.
    
'''


class MyScript(Script):
    
    class Meta:
        name = "Import Nokia IP interfaces"
        description = "import CSV file exported from Nokia NSP (device must already exist in NetBox)"
        commit_default = False
    

    domain_suffix = StringVar(
        description="Enter the domain suffix"
    )


    csvfile = FileVar(
        description="Name of CSV formatted file to import",
        required=True
    )

    def run(self, data, commit):

        # function build address/prefix string
        def make_address(row):
            return(f"{row['IP Address']}/{row['Prefix Length']}")

        # function to lookup and return the device id
        def get_device_id(row):
            #self.log_info(f"Looking up device {row['device']}")
            device=Device.objects.get(name=row['device'])
            return device.id

        # function to construct a new interface object and save it to Netbox
        def create_interface(row):
            # get the device
            device=Device.objects.get(name=row['device'])
            #self.log_info(f"Checking {device} {row['name']} to see if it already exists")
            
            # before creating check if interface exists
            result=Interface.objects.filter(device=device, name=row['name'])

            # if interface was not found (count=0)
            if result.count() == 0:
                # create new interface
                interface = Interface(
                    device=device,
                    name=row['name'],
                    type=row['type'],
                    description=f"{device} {row['name']}_DUP imported from NSP ({row['Object Type']})"
                )
            else:
                self.log_warning(f"Interface name already exists: {device}={device.id} {result[0].id} {result[0].name} count={result.count()}")
                # create a *unique* interface to avoid conflict using a slugified IP address to make name unique
                interface = Interface(
                    device=device,
                    name=row['name']+"_DUP_"+slugify(row['address']),
                    type=row['type'],
                    description=f"{device} {row['name']}_DUP imported from NSP ({row['Object Type']})"
                )
            interface.save()
            self.log_debug(f"New interface saved: {device} {interface}")
            
            return interface.id


        # assign the IP address to each interface in NetBox and saves it
        def assign_address_to_interface(row):
            # get the device
            device=Device.objects.get(name=row['device'])

            # get the interface
            interface=Interface.objects.get(pk=row['interface_id'])            
            
            # create dns name
            if interface.name=='system':
                dns_name=f"{slugify(device)}.{data['domain_suffix']}"
            else:
                dns_name=f"{slugify(device)}-{slugify(interface)}.{data['domain_suffix']}"
                
            # create IP address
            address=IPAddress(
                address=row['address'],
                status='active',
                description=f"{device} {interface} imported from NSP ({row['Object Type']})",
                dns_name=dns_name
            )
            # self.log_debug(f"{device} {interface} {address} {address.dns_name} {row['Object Type']}")
            address.save()

            # If system interface Make this the primary IP for the Nokia device
            if interface.name == 'system':
                device.primary_ip4 = address
                device.save()

            # add ip address to interface
            interface.ip_addresses.add(address)
            
            return address.id


        self.log_info(f"Importing file: {data['csvfile']}")
        
        self.log_info(f"Assumes all devices exist in NetBox, and will skip any interfaces that already exist")

        df = pd.read_csv(data['csvfile'])
        
        self.log_success(f"CSV file read")
        
        # make up new column headers and rename for netbox to understand
        new_columns={
                "Site Name": "device",
                "Interface Name": "name"
        }
        df.rename(columns=new_columns, inplace=True)

        # make a new column containing interface address/mask
        df['address'] = df.apply(make_address, axis='columns')

        # add required interface types
        df['type'] = 'virtual'

        self.log_info(f"Dataframe headers morphed successfully")

        # this does a device lookup to make sure devices in CSV data exist in NetBox
        df['device_id'] = df.apply(get_device_id, axis='columns')
        
        self.log_success(f"All devices were found in NetBox, thus good to go for now :P")

        # creates new interface and adds the interface id to the existing data frame
        # note: existing interfaces are skipped
        df['interface_id'] = df.apply(create_interface, axis='columns')
        
        self.log_success(f"All interfaces from CSV data created!")

        # assigns the address to interfaces and adds the address id to the existing data frame
        df['address_id'] = df.apply(assign_address_to_interface, axis='columns')
        
        self.log_success(f"All address assigned from CSV data!")

        # drop columns not needed before exporting to CSV
        df = df.drop(columns=['Site ID', 'IP Address Type', 'IP Address', 'Prefix Length', 'Object Type'])
        
        # this will output the resulting data frame for informational purposes only
        return df.to_csv(index=False)

